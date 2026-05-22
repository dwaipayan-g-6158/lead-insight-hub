#!/usr/bin/env python3
"""
ELISS v7.3.0 RocketReach API Client — full premium-account surface.

Wraps all 8 public RocketReach v2 endpoints with per-endpoint session caps
sized for a premium account. Every call logs to a per-instance audit trail
so callers can populate `meta.rocketreach_budget` in the dossier JSON and
render the ᴿᴿ provenance pill on every RR-sourced value.

=== SECURITY ===
API key is read from the `RR_API_KEY` environment variable. It is never
hardcoded, logged, written to disk, serialized into repr(), or included
in error messages.

=== CREDIT DISCIPLINE (v7.1+) ===
Per-dossier caps — each endpoint is independently budgeted so a single
runaway dossier cannot exhaust monthly quota. Tuned for a premium account
(unlimited premium_lookup, 55K+ person_export, 62K+ company_export):

    * Max 1 account health check per session (no credits)
    * Max 5 company lookups per dossier      (was 1)
    * Max 10 company searches per dossier    (new — Firmographic/intent/news sweeps)
    * Max 40 person lookups per dossier      (was 5)
    * Max 30 person searches per dossier     (new — DMU enumeration / incumbent detection)
    * Max 10 profile-company combined lookups (new)
    * Max 1 bulk-lookup batch per dossier    (up to 100 profiles in one call)
    * Max 20 check-status polls per dossier  (no credits)

Total credit spend per HOT dossier: ≈150 person_export + 15 company_export —
well under 0.5% of monthly quota.

=== TIER LABELING ===
All RocketReach responses are Tier-B per ELISS scoring rules (reputable
secondary, not authoritative). Even verified emails with RR grade "A" remain
Tier-B because RocketReach is an aggregator, not an issuing authority. The
rendered dossier surfaces this via an inline ᴿᴿ pill on every RR-sourced value.

=== RATE LIMITING ===
429 responses surface as RocketReachRateLimited; callers should degrade to
free-OSINT for the affected lookup rather than retrying.

=== API ENDPOINTS (8) ===
    GET  /account/                       health + remaining credits (no credits)
    GET  /company/lookup/                company firmographics (1 company_export)
    POST /searchCompany                  company search by criteria (1 company_search)
    GET  /person/lookup                  person enrichment (1 person_export per hit)
    POST /person/search                  person search by criteria (1 person_search)
    GET  /profile-company/lookup         combined person+company (1 person_export)
    POST /bulkLookup                     bulk person lookup (1 person_export per profile)
    GET  /person/checkStatus             poll bulk/async lookup status (no credits)

Auth header: `Api-Key: <key>`
Docs:        https://docs.rocketreach.co/reference
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

API_BASE = "https://api.rocketreach.co/api/v2"
DEFAULT_TIMEOUT = 20  # seconds per request

# Per-dossier session caps (tuned for a premium account).
DEFAULT_MAX_ACCOUNT_CHECKS = 1
DEFAULT_MAX_COMPANY_LOOKUPS = 5
DEFAULT_MAX_COMPANY_SEARCHES = 10
DEFAULT_MAX_PERSON_LOOKUPS = 40
DEFAULT_MAX_PERSON_SEARCHES = 30
DEFAULT_MAX_PROFILE_COMPANY = 10
DEFAULT_MAX_BULK_BATCHES = 1
DEFAULT_MAX_CHECK_STATUS_POLLS = 20
DEFAULT_BULK_BATCH_SIZE = 100  # RocketReach API max

# Credit pools — maps endpoint → which balance it debits.
# Used by budget_summary() to roll up credits_consumed per pool.
CREDIT_POOL_BY_ENDPOINT = {
    "account": None,               # free
    "company_lookup": "company_export",
    "company_search": "company_search",
    "person_lookup": "person_export",
    "person_search": "person_search",
    "profile_company_lookup": "person_export",
    "bulk_lookup": "person_export",  # per-profile
    "check_status": None,            # free
}


class RocketReachError(Exception):
    """Base exception for RocketReach client errors."""


class RocketReachAuthError(RocketReachError):
    """401 Unauthorized — invalid/missing API key."""


class RocketReachRateLimited(RocketReachError):
    """429 Too Many Requests — caller should degrade to free OSINT."""


class RocketReachCapExceeded(RocketReachError):
    """Session-level cap reached; further calls rejected to protect credits."""


class RocketReachNotFound(RocketReachError):
    """404 — no match for the provided query."""


@dataclass
class CreditBudget:
    """Tracks per-endpoint call counts + a timestamped audit trail within one ELISS run."""

    # Usage counters — one per endpoint type.
    account_checks_used: int = 0
    company_lookups_used: int = 0
    company_searches_used: int = 0
    person_lookups_used: int = 0
    person_searches_used: int = 0
    profile_company_used: int = 0
    bulk_batches_used: int = 0
    check_status_polls_used: int = 0

    # Caps (may be overridden via constructor).
    max_account_checks: int = DEFAULT_MAX_ACCOUNT_CHECKS
    max_company_lookups: int = DEFAULT_MAX_COMPANY_LOOKUPS
    max_company_searches: int = DEFAULT_MAX_COMPANY_SEARCHES
    max_person_lookups: int = DEFAULT_MAX_PERSON_LOOKUPS
    max_person_searches: int = DEFAULT_MAX_PERSON_SEARCHES
    max_profile_company: int = DEFAULT_MAX_PROFILE_COMPANY
    max_bulk_batches: int = DEFAULT_MAX_BULK_BATCHES
    max_check_status_polls: int = DEFAULT_MAX_CHECK_STATUS_POLLS

    # Rolling audit trail — one entry per successful API call.
    # Shape: {ts_iso, endpoint, credit_pool, credits_consumed, request_id, elapsed_ms, note}
    audit_trail: list[dict[str, Any]] = field(default_factory=list)

    def record(self, endpoint: str, meta: dict[str, Any] | None = None) -> None:
        """Append a call record with UTC timestamp + credit-pool attribution."""
        entry = {
            "ts_iso": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "endpoint": endpoint,
            "credit_pool": CREDIT_POOL_BY_ENDPOINT.get(endpoint),
            **(meta or {}),
        }
        self.audit_trail.append(entry)


class RocketReachClient:
    """Env-var-driven RocketReach API client. Never stores or logs the API key."""

    def __init__(
        self,
        *,
        env_var: str = "RR_API_KEY",
        timeout: int = DEFAULT_TIMEOUT,
        budget: CreditBudget | None = None,
        max_account_checks: int | None = None,
        max_company_lookups: int | None = None,
        max_company_searches: int | None = None,
        max_person_lookups: int | None = None,
        max_person_searches: int | None = None,
        max_profile_company: int | None = None,
        max_bulk_batches: int | None = None,
        max_check_status_polls: int | None = None,
    ) -> None:
        api_key = os.environ.get(env_var, "").strip()
        if not api_key:
            raise RocketReachAuthError(
                f"{env_var} environment variable not set. Export your "
                f"RocketReach API key before running: export {env_var}='...'. "
                f"ELISS will run on free OSINT only without this."
            )
        self._api_key = api_key
        self._timeout = timeout

        def _pick(kw, default):
            return kw if kw is not None else default

        self.budget = budget or CreditBudget(
            max_account_checks=_pick(max_account_checks, DEFAULT_MAX_ACCOUNT_CHECKS),
            max_company_lookups=_pick(max_company_lookups, DEFAULT_MAX_COMPANY_LOOKUPS),
            max_company_searches=_pick(max_company_searches, DEFAULT_MAX_COMPANY_SEARCHES),
            max_person_lookups=_pick(max_person_lookups, DEFAULT_MAX_PERSON_LOOKUPS),
            max_person_searches=_pick(max_person_searches, DEFAULT_MAX_PERSON_SEARCHES),
            max_profile_company=_pick(max_profile_company, DEFAULT_MAX_PROFILE_COMPANY),
            max_bulk_batches=_pick(max_bulk_batches, DEFAULT_MAX_BULK_BATCHES),
            max_check_status_polls=_pick(max_check_status_polls, DEFAULT_MAX_CHECK_STATUS_POLLS),
        )

    # Defensive: never leak the key through repr/str.
    def __repr__(self) -> str:
        return (
            f"RocketReachClient(budget={self.budget!r}, "
            f"timeout={self._timeout}, api_key=***REDACTED***)"
        )

    # -------------------------------------------------------------------------
    # Low-level request helpers — not public API
    # -------------------------------------------------------------------------

    def _request(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        method: str = "GET",
        json_body: Any = None,
    ) -> tuple[dict[str, Any] | list[Any], dict[str, str]]:
        """Issue a GET or POST against RocketReach. Returns (parsed_body, response_headers)."""
        url = f"{API_BASE}{path}"
        if params and method == "GET":
            clean = {k: v for k, v in params.items() if v not in (None, "", [])}
            if clean:
                url = f"{url}?{urllib.parse.urlencode(clean, doseq=True, quote_via=urllib.parse.quote)}"

        body_bytes: bytes | None = None
        headers = {
            "Api-Key": self._api_key,
            "Accept": "application/json",
            "User-Agent": "ELISS/7.1.0 (ManageEngine AD360/Log360 sales intelligence)",
        }
        if json_body is not None:
            body_bytes = json.dumps(json_body, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                resp_headers = {k: v for k, v in resp.headers.items()}
                parsed = json.loads(body) if body else {}
                return parsed, resp_headers
        except urllib.error.HTTPError as e:
            code = e.code
            try:
                detail = e.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                detail = ""
            if code == 401:
                raise RocketReachAuthError(
                    f"401 Unauthorized at {path}. API key invalid or revoked. "
                    f"Check RR_API_KEY and rotate if needed."
                ) from e
            if code == 404:
                raise RocketReachNotFound(f"404 Not Found at {path}: {detail}") from e
            if code == 429:
                raise RocketReachRateLimited(
                    f"429 Rate limit at {path}. Degrade to free OSINT for remaining calls."
                ) from e
            raise RocketReachError(f"HTTP {code} at {path}: {detail}") from e
        except urllib.error.URLError as e:
            raise RocketReachError(f"Network error calling {path}: {e.reason}") from e

    def _elapsed_ms(self, started_at: float) -> int:
        return int((time.monotonic() - started_at) * 1000)

    # -------------------------------------------------------------------------
    # Public API (8 endpoints)
    # -------------------------------------------------------------------------

    def account(self) -> dict[str, Any]:
        """Health-check the API key. Free (no credits consumed). Capped at 1/session."""
        if self.budget.account_checks_used >= self.budget.max_account_checks:
            raise RocketReachCapExceeded(
                f"Account-check cap reached "
                f"({self.budget.account_checks_used}/{self.budget.max_account_checks})."
            )
        started = time.monotonic()
        data, resp_headers = self._request("/account/")
        self.budget.account_checks_used += 1
        self.budget.record(
            "account",
            {"elapsed_ms": self._elapsed_ms(started), "ok": True},
        )
        return data  # type: ignore[return-value]

    def lookup_person(
        self,
        *,
        name: str | None = None,
        current_employer: str | None = None,
        current_title: str | None = None,
        linkedin_url: str | None = None,
        email: str | None = None,
        title: str | None = None,
        lookup_type: str | None = None,
        npi_number: int | None = None,
        return_cached_emails: bool | None = None,
        webhook_id: int | None = None,
    ) -> dict[str, Any]:
        """Person enrichment — 1 person_export credit per verified hit. Capped at 40/dossier.

        Provide at least one of {linkedin_url, email, (name AND current_employer)}.
        lookup_type values: 'standard', 'premium', 'premium (feeds disabled)',
        'bulk', 'phone', 'enrich'.
        """
        if self.budget.person_lookups_used >= self.budget.max_person_lookups:
            raise RocketReachCapExceeded(
                f"Person-lookup cap reached "
                f"({self.budget.person_lookups_used}/{self.budget.max_person_lookups})."
            )
        if not (linkedin_url or email or (name and current_employer) or npi_number):
            raise RocketReachError(
                "lookup_person needs one of: linkedin_url, email, "
                "(name AND current_employer), or npi_number."
            )
        params: dict[str, Any] = {}
        for k, v in {
            "name": name,
            "current_employer": current_employer,
            "current_title": current_title,
            "linkedin_url": linkedin_url,
            "email": email,
            "title": title,
            "lookup_type": lookup_type,
            "npi_number": npi_number,
            "webhook_id": webhook_id,
        }.items():
            if v is not None:
                params[k] = v
        if return_cached_emails is not None:
            params["return_cached_emails"] = "true" if return_cached_emails else "false"

        started = time.monotonic()
        data, resp_headers = self._request("/person/lookup", params)
        self.budget.person_lookups_used += 1
        self.budget.record(
            "person_lookup",
            {
                "elapsed_ms": self._elapsed_ms(started),
                "credits_consumed": 1 if data else 0,
                "request_id": resp_headers.get("RR-Request-ID"),
                "returned": bool(data),
                "status": (data or {}).get("status"),
            },
        )
        return data  # type: ignore[return-value]

    def lookup_company(
        self,
        *,
        domain: str | None = None,
        name: str | None = None,
        linkedin_url: str | None = None,
        ticker: str | None = None,
        company_id: int | None = None,
    ) -> dict[str, Any]:
        """Company firmographics (num_employees, revenue, industry, techstack, etc.).

        1 company_export credit per call. Capped at 5/dossier.
        """
        if self.budget.company_lookups_used >= self.budget.max_company_lookups:
            raise RocketReachCapExceeded(
                f"Company-lookup cap reached "
                f"({self.budget.company_lookups_used}/{self.budget.max_company_lookups})."
            )
        if not (domain or name or linkedin_url or ticker or company_id):
            raise RocketReachError(
                "lookup_company needs one of: domain, name, linkedin_url, ticker, company_id."
            )
        params: dict[str, Any] = {}
        for k, v in {
            "domain": domain,
            "name": name,
            "linkedin_url": linkedin_url,
            "ticker": ticker,
            "id": company_id,
        }.items():
            if v is not None:
                params[k] = v
        started = time.monotonic()
        data, _headers = self._request("/company/lookup/", params)
        self.budget.company_lookups_used += 1
        self.budget.record(
            "company_lookup",
            {
                "elapsed_ms": self._elapsed_ms(started),
                "credits_consumed": 1 if data else 0,
                "domain": domain,
                "returned": bool(data),
            },
        )
        return data  # type: ignore[return-value]

    def company_search(
        self,
        *,
        query: dict[str, Any],
        start: int = 1,
        page_size: int = 25,
        order_by: str = "popularity",
    ) -> list[dict[str, Any]]:
        """POST /searchCompany — find companies by firmographic/intent/news filters.

        Uses company_search credit pool (separate from company_export). One query = 1 credit,
        regardless of result count (up to 100 per page). Capped at 10/dossier.

        Useful query keys: domain, name, industry, techstack, revenue, employees,
        growth ('5-30::Engineering,six_months'), job_posting_signal, news_signal,
        publicly_traded, naics_code, sic_code, geo, location.
        """
        if self.budget.company_searches_used >= self.budget.max_company_searches:
            raise RocketReachCapExceeded(
                f"Company-search cap reached "
                f"({self.budget.company_searches_used}/{self.budget.max_company_searches})."
            )
        if not query:
            raise RocketReachError("company_search requires a non-empty query dict.")
        page_size = max(1, min(100, page_size))
        start = max(1, min(10000, start))
        body = {"start": start, "page_size": page_size, "query": query, "order_by": order_by}
        started = time.monotonic()
        data, _headers = self._request(
            "/searchCompany", method="POST", json_body=body
        )
        self.budget.company_searches_used += 1
        results = data if isinstance(data, list) else []
        self.budget.record(
            "company_search",
            {
                "elapsed_ms": self._elapsed_ms(started),
                "credits_consumed": 1,
                "result_count": len(results),
                "query_keys": sorted(query.keys()),
            },
        )
        return results

    def person_search(
        self,
        *,
        query: dict[str, Any],
        start: int = 1,
        page_size: int = 25,
        order_by: str = "popularity",
    ) -> list[dict[str, Any]]:
        """POST /person/search — find people by title / employer / skills / job-change signals.

        Uses person_search credit pool (separate from person_export). Returns teasers
        without contact info — use bulk_lookup() or lookup_person() to materialize contacts.
        Capped at 30/dossier.

        Useful query keys: current_employer, current_title, management_levels,
        department, current_or_previous_title, previous_employer, skills, keyword,
        geo, city, state, job_change_signal, contact_method, email_grade,
        company_id, company_industry, years_experience, employer.
        """
        if self.budget.person_searches_used >= self.budget.max_person_searches:
            raise RocketReachCapExceeded(
                f"Person-search cap reached "
                f"({self.budget.person_searches_used}/{self.budget.max_person_searches})."
            )
        if not query:
            raise RocketReachError("person_search requires a non-empty query dict.")
        page_size = max(1, min(100, page_size))
        start = max(1, min(10000, start))
        body = {"start": start, "page_size": page_size, "query": query, "order_by": order_by}
        started = time.monotonic()
        data, _headers = self._request(
            "/person/search", method="POST", json_body=body
        )
        self.budget.person_searches_used += 1
        results = data if isinstance(data, list) else []
        self.budget.record(
            "person_search",
            {
                "elapsed_ms": self._elapsed_ms(started),
                "credits_consumed": 1,
                "result_count": len(results),
                "query_keys": sorted(query.keys()),
            },
        )
        return results

    def profile_company_lookup(
        self,
        *,
        name: str | None = None,
        current_employer: str | None = None,
        linkedin_url: str | None = None,
        email: str | None = None,
        title: str | None = None,
        person_id: int | None = None,
        lookup_type: str = "premium",
        return_cached_emails: bool | None = None,
        webhook_id: int | None = None,
    ) -> dict[str, Any]:
        """GET /profile-company/lookup — one call returning person + full employer company.

        Consumes 1 person_export credit. Use instead of separate person+company calls
        when both sides are needed. Capped at 10/dossier.
        """
        if self.budget.profile_company_used >= self.budget.max_profile_company:
            raise RocketReachCapExceeded(
                f"Profile-company-lookup cap reached "
                f"({self.budget.profile_company_used}/{self.budget.max_profile_company})."
            )
        if not (linkedin_url or email or person_id or (name and current_employer)):
            raise RocketReachError(
                "profile_company_lookup needs one of: linkedin_url, email, "
                "id, or (name AND current_employer)."
            )
        params: dict[str, Any] = {}
        for k, v in {
            "name": name,
            "current_employer": current_employer,
            "linkedin_url": linkedin_url,
            "email": email,
            "title": title,
            "id": person_id,
            "lookup_type": lookup_type,
            "webhook_id": webhook_id,
        }.items():
            if v is not None:
                params[k] = v
        if return_cached_emails is not None:
            params["return_cached_emails"] = "true" if return_cached_emails else "false"

        started = time.monotonic()
        data, resp_headers = self._request("/profile-company/lookup", params)
        self.budget.profile_company_used += 1
        self.budget.record(
            "profile_company_lookup",
            {
                "elapsed_ms": self._elapsed_ms(started),
                "credits_consumed": 1 if data else 0,
                "request_id": resp_headers.get("RR-Request-ID"),
                "status": (data or {}).get("status") if isinstance(data, dict) else None,
                "returned": bool(data),
            },
        )
        return data  # type: ignore[return-value]

    def bulk_lookup(
        self,
        queries: list[dict[str, Any]],
        *,
        profile_list: str = "ELISS Bulk",
        webhook_id: int | None = None,
    ) -> dict[str, Any]:
        """POST /bulkLookup — up to 100 person lookups in a single request.

        Consumes 1 person_export credit per profile on completion. Capped at 1 batch/dossier.
        Each query dict should contain at least one of: linkedin_url, email,
        (name AND current_employer), id, npi_number.

        For async handling, use poll_until_complete() with the returned profile IDs.
        """
        if self.budget.bulk_batches_used >= self.budget.max_bulk_batches:
            raise RocketReachCapExceeded(
                f"Bulk-lookup batch cap reached "
                f"({self.budget.bulk_batches_used}/{self.budget.max_bulk_batches})."
            )
        if not queries or not isinstance(queries, list):
            raise RocketReachError("bulk_lookup requires a non-empty list of query dicts.")
        if len(queries) > DEFAULT_BULK_BATCH_SIZE:
            raise RocketReachError(
                f"bulk_lookup accepts at most {DEFAULT_BULK_BATCH_SIZE} queries per batch; "
                f"got {len(queries)}."
            )
        body: dict[str, Any] = {"queries": queries, "profile_list": profile_list}
        if webhook_id is not None:
            body["webhook_id"] = webhook_id

        started = time.monotonic()
        data, _headers = self._request(
            "/bulkLookup", method="POST", json_body=body
        )
        self.budget.bulk_batches_used += 1
        self.budget.record(
            "bulk_lookup",
            {
                "elapsed_ms": self._elapsed_ms(started),
                "credits_consumed": len(queries),
                "batch_size": len(queries),
                "profile_list": profile_list,
            },
        )
        return data  # type: ignore[return-value]

    def check_status(self, ids: list[int]) -> list[dict[str, Any]]:
        """GET /person/checkStatus?ids=... — poll status of a person/bulk lookup. Free."""
        if self.budget.check_status_polls_used >= self.budget.max_check_status_polls:
            raise RocketReachCapExceeded(
                f"Check-status poll cap reached "
                f"({self.budget.check_status_polls_used}/{self.budget.max_check_status_polls})."
            )
        if not ids:
            raise RocketReachError("check_status requires a non-empty list of profile ids.")
        started = time.monotonic()
        data, _headers = self._request("/person/checkStatus", {"ids": list(ids)})
        self.budget.check_status_polls_used += 1
        self.budget.record(
            "check_status",
            {
                "elapsed_ms": self._elapsed_ms(started),
                "ids_requested": len(ids),
            },
        )
        return data if isinstance(data, list) else []

    def poll_until_complete(
        self,
        ids: list[int],
        *,
        max_polls: int | None = None,
        delay_seconds: float = 3.0,
    ) -> list[dict[str, Any]]:
        """Poll check_status() until all ids reach a terminal status or max_polls hit.

        Terminal statuses: 'complete', 'failed'. Default max 20 polls × 3s = 60s upper bound.
        Returns the most recent snapshot (even if not all IDs completed).
        """
        limit = max_polls or self.budget.max_check_status_polls
        snapshot: list[dict[str, Any]] = []
        terminal = {"complete", "failed"}
        for _ in range(limit):
            snapshot = self.check_status(ids)
            statuses = {r.get("status") for r in snapshot}
            # If every row is terminal, we're done.
            if statuses and statuses.issubset(terminal):
                return snapshot
            time.sleep(delay_seconds)
        return snapshot

    # -------------------------------------------------------------------------
    # ELISS integration helpers
    # -------------------------------------------------------------------------

    def run_baseline_enrichment(
        self,
        *,
        domain: str,
        company_name: str | None = None,
        contact_name: str | None = None,
        contact_linkedin: str | None = None,
        contact_email: str | None = None,
        management_levels: list[str] | None = None,
        max_bulk_profiles: int = 20,
    ) -> dict[str, Any]:
        """Canonical per-dossier RocketReach baseline sweep (ELISS v7.1.2+).

        Runs on EVERY ELISS research path — fresh fan-out, refresh on an
        existing lead, single-session COOL/COLD run — whenever RR_API_KEY is
        set. This is the structural hook that guarantees RocketReach data
        flows into every dossier regardless of whether the parallel-subagent
        dispatch fires. Subagents remain free to call the client on top
        of this baseline for layer-specific depth (CISO-change detection,
        techstack confirmation, ghost-stakeholder discovery, etc.).

        Sequence (≈22 person_export + 1 company_export + 1 person_search):
          1. account()                          — health check, free
          2. lookup_company(domain)             — authoritative firmographics
                                                   (num_employees, revenue, industry,
                                                   techstack, competitors, growth)
                                                   1 company_export credit
          3. person_search(current_employer, management_levels)
                                                — enumerate exec DMU, 1 person_search
          4. bulk_lookup(top N ids)             — materialize full profiles with
                                                   verified emails/phones/job_history
                                                   N person_export credits
          5. profile_company_lookup(contact)    — named contact's combined person+company
                                                   (only if contact signal provided)
                                                   1 person_export credit

        Every call is wrapped in try/except — a single endpoint failure
        degrades the affected slot to None and keeps the rest of the sweep
        going. The returned dict shape is stable so callers can always
        merge it into the dossier without None-checking every field.

        Returns:
            {
                "account":            {...} | None,
                "company":            {...} | None,  # full lookup_company payload
                "exec_dmu_search":    [...] | None,  # person_search teasers
                "exec_dmu_enriched":  {...} | None,  # bulk_lookup response
                "named_contact":      {...} | None,  # profile_company_lookup response
                "budget_summary":     {...},         # self.budget_summary() snapshot
                "errors":             [...],         # per-step error strings (empty if all OK)
            }
        """
        if management_levels is None:
            management_levels = ["Director", "VP", "C-Suite"]

        result: dict[str, Any] = {
            "account": None,
            "company": None,
            "exec_dmu_search": None,
            "exec_dmu_enriched": None,
            "named_contact": None,
            # v7.1.6 — when profile_company_lookup misses but person_search
            # surfaces 2+ same-name candidates, the analyst gets the teaser
            # list here for manual disambiguation. None when there's only
            # one candidate (auto-resolved into named_contact) or zero.
            "named_contact_candidates": None,
            # v7.1.6 — provenance for the named_contact slot. One of:
            # "profile_company_lookup_linkedin" | "profile_company_lookup_email" |
            # "profile_company_lookup_name_employer" |
            # "person_search_name_employer" | "person_search_name_employer_ambiguous" |
            # "person_search_name_only_ambiguous" | None
            "named_contact_resolution_path": None,
            "errors": [],
        }

        # Step 1 — account health check
        try:
            result["account"] = self.account()
        except RocketReachError as e:
            result["errors"].append(f"account: {e}")

        # Step 2 — company firmographics
        company_id = None
        try:
            co = self.lookup_company(domain=domain, name=company_name)
            result["company"] = co
            if isinstance(co, dict):
                company_id = co.get("id")
        except RocketReachError as e:
            result["errors"].append(f"lookup_company: {e}")

        # Step 3 — exec DMU search (prefer filtering by the RR company_id when we got one;
        # fall back to company_name / current_employer string).
        try:
            query: dict[str, Any] = {"management_levels": management_levels}
            if company_id is not None:
                query["company_id"] = [str(company_id)]
            elif company_name:
                query["current_employer"] = [company_name]
            else:
                # No reliable employer anchor — skip rather than waste a search credit.
                raise RocketReachError(
                    "cannot run exec-DMU person_search without company_id or company_name"
                )
            result["exec_dmu_search"] = self.person_search(
                query=query, page_size=max_bulk_profiles, order_by="popularity"
            )
        except RocketReachError as e:
            result["errors"].append(f"person_search: {e}")

        # Step 4 — bulk-lookup the top N exec DMU results to get verified contact data.
        ids: list[int] = []
        if result["exec_dmu_search"]:
            for row in result["exec_dmu_search"][:max_bulk_profiles]:
                rid = row.get("id") if isinstance(row, dict) else None
                if isinstance(rid, int):
                    ids.append(rid)
        if ids:
            try:
                result["exec_dmu_enriched"] = self.bulk_lookup(
                    [{"id": i} for i in ids],
                    profile_list=f"ELISS baseline {domain}",
                )
            except RocketReachError as e:
                result["errors"].append(f"bulk_lookup: {e}")

        # Step 5 — named contact profile+company lookup (only if we have at least one signal).
        #
        # v7.1.6 — RETRY LADDER. Prior versions stopped after a single
        # `profile_company_lookup` attempt; if RR's strict-match endpoint
        # returned 404 (e.g. junior employee whose corporate email isn't in
        # RR's index), the contact was declared unverified even though a
        # `person_search` against the same (name, current_employer) tuple
        # would have surfaced a teaser hit. The ladder below tries the
        # strict path first (cheapest credit + most precise), then falls
        # through to two progressively-broader `person_search` paths,
        # recording which path resolved the contact in
        # `named_contact_resolution_path` so downstream renderers can
        # display provenance.
        if contact_name or contact_linkedin or contact_email:
            # ---- Path 1: profile_company_lookup (strict, original behavior) ----
            kwargs: dict[str, Any] = {}
            if contact_linkedin:
                kwargs["linkedin_url"] = contact_linkedin
            elif contact_email:
                kwargs["email"] = contact_email
            elif contact_name and company_name:
                kwargs["name"] = contact_name
                kwargs["current_employer"] = company_name
            if kwargs:
                try:
                    pcl_result = self.profile_company_lookup(**kwargs)
                    if pcl_result:
                        result["named_contact"] = pcl_result
                        # Record which key we hit on. Provenance helps the rep
                        # know how confident to be in the match.
                        if "linkedin_url" in kwargs:
                            result["named_contact_resolution_path"] = "profile_company_lookup_linkedin"
                        elif "email" in kwargs:
                            result["named_contact_resolution_path"] = "profile_company_lookup_email"
                        else:
                            result["named_contact_resolution_path"] = "profile_company_lookup_name_employer"
                except RocketReachError as e:
                    result["errors"].append(f"profile_company_lookup: {e}")

            # ---- Path 2: person_search(name + current_employer with aliases) ----
            # Only fire if Path 1 did not produce a hit AND we have a name.
            # Aliases include the operator-typed company_name AND the
            # RR-canonical name from step 2's lookup_company payload (so
            # 'Remington Hotels' typed AND 'Remington Hospitality' canonical
            # both go into the query). person_search returns teasers (no
            # contact info, just IDs + name + title); a single-hit result
            # is treated as a named-contact resolution, multi-hit results
            # are surfaced as `named_contact_candidates` for analyst
            # disambiguation.
            if not result["named_contact"] and contact_name:
                try:
                    employer_aliases: list[str] = []
                    if company_name:
                        employer_aliases.append(company_name)
                    rr_canonical_name = (result.get("company") or {}).get("name")
                    if rr_canonical_name and rr_canonical_name not in employer_aliases:
                        employer_aliases.append(rr_canonical_name)
                    if employer_aliases:
                        ps_query: dict[str, Any] = {
                            "name": [contact_name],
                            "current_employer": employer_aliases,
                        }
                        ps_results = self.person_search(query=ps_query, page_size=10)
                        # person_search returns a list directly (teaser shape).
                        if isinstance(ps_results, list) and len(ps_results) == 1:
                            result["named_contact"] = ps_results[0]
                            result["named_contact_resolution_path"] = "person_search_name_employer"
                        elif isinstance(ps_results, list) and ps_results:
                            # 2+ candidates with same name at same employer
                            # — surface for analyst disambiguation, do NOT
                            # auto-resolve.
                            result["named_contact_candidates"] = ps_results[:10]
                            result["named_contact_resolution_path"] = "person_search_name_employer_ambiguous"
                except RocketReachError as e:
                    result["errors"].append(f"person_search(name+employer): {e}")

            # ---- Path 3: person_search(name only, last resort) ----
            # Fires only when Paths 1 and 2 both miss AND no linkedin_url was
            # originally provided. Always treated as ambiguous (different
            # people sharing a name at different companies are not a
            # "resolution"); the result populates `named_contact_candidates`
            # so the analyst can manually disambiguate. Cap candidate-list
            # at 5 — beyond that the contact is too generic to be useful.
            if (not result["named_contact"]
                    and not result.get("named_contact_candidates")
                    and contact_name
                    and not contact_linkedin):
                try:
                    ps_results = self.person_search(
                        query={"name": [contact_name]}, page_size=5
                    )
                    if isinstance(ps_results, list) and ps_results:
                        result["named_contact_candidates"] = ps_results[:5]
                        result["named_contact_resolution_path"] = "person_search_name_only_ambiguous"
                except RocketReachError as e:
                    result["errors"].append(f"person_search(name only): {e}")

        result["budget_summary"] = self.budget_summary()
        return result

    def to_eliss_person_record(self, rr_person: dict[str, Any]) -> dict[str, Any]:
        """
        Transform a RocketReach person/profile payload into the ELISS dossier
        record shape. Marks every field with a per-field `_rocketreach: true`
        flag so the renderer can surface the inline ᴿᴿ pill (Rule 7, v7.1+).

        v7.1.3 — expanded coverage. Prior versions mapped only 9 fields
        (name, title, company, location, linkedin, email, email_grade, phone,
        skills) and silently dropped ~60% of what `/person/lookup` returns.
        This revision also propagates: rr_id, profile_url/rr_profile_url,
        job_history (for competitive-incumbent mining), education
        (personalization), social links (twitter/github/facebook/links[]),
        granular geo (city/state/country/region), current_employer_domain +
        current_employer_linkedin_url, a `verified_emails[]` list with grades
        for A-/A- triage, and `verified_phones[]` so ghost-DMU rendering can
        show every reachable number, not just the recommended one.
        """
        if not rr_person:
            return {}
        emails = rr_person.get("emails") or []
        phones = rr_person.get("phones") or []
        recommended_email = (
            rr_person.get("recommended_email")
            or rr_person.get("recommended_professional_email")
            or rr_person.get("current_work_email")
            or (emails[0].get("email") if emails else None)
        )
        primary_phone = None
        for p in phones:
            if p.get("recommended"):
                primary_phone = p.get("number")
                break
        if not primary_phone and phones:
            primary_phone = phones[0].get("number")

        # Grade comes from the email object (A / A- / B).
        email_grade = None
        if emails:
            email_grade = emails[0].get("grade")

        # v7.1.3 — keep the full list so renderers can show secondary emails
        # (e.g. personal backup inbox) with their individual grades.
        verified_emails = [
            {
                "email": e.get("email"),
                "grade": e.get("grade"),
                "type": e.get("type"),
                "last_validation_check": e.get("last_validation_check"),
            }
            for e in emails if e.get("email")
        ]
        verified_phones = [
            {
                "number": p.get("number"),
                "type": p.get("type"),
                "is_premium": p.get("is_premium"),
                "recommended": p.get("recommended"),
            }
            for p in phones if p.get("number")
        ]

        # Collapse the social-profile block into a single `social_links` dict so
        # renderers don't have to probe each url field individually.
        social_links: dict[str, str] = {}
        for key in ("linkedin_url", "twitter_url", "facebook_url", "github_url",
                    "angellist_url", "aboutme_url", "youtube_url"):
            v = rr_person.get(key)
            if v:
                social_links[key.replace("_url", "")] = v
        # `links` is an array of typed social entries in the RR response
        for link in rr_person.get("links") or []:
            if not isinstance(link, dict):
                continue
            t = (link.get("type") or "").lower()
            u = link.get("url")
            if t and u and t not in social_links:
                social_links[t] = u

        # Job history — keep top 5 for context; trim payload size.
        job_history = rr_person.get("job_history") or []
        if isinstance(job_history, list):
            job_history_trim = [
                {
                    "title": h.get("title"),
                    "employer": h.get("company_name") or h.get("employer"),
                    "start_date": h.get("start_date"),
                    "end_date": h.get("end_date"),
                    "description": (h.get("description") or "")[:300],
                    "is_current": h.get("is_current"),
                }
                for h in job_history[:5] if isinstance(h, dict)
            ]
        else:
            job_history_trim = []

        # Education — keep top 3.
        education = rr_person.get("education") or []
        if isinstance(education, list):
            education_trim = [
                {
                    "degree": e.get("degree"),
                    "institution": e.get("school") or e.get("institution"),
                    "start_date": e.get("start_date"),
                    "end_date": e.get("end_date"),
                    "field_of_study": e.get("field_of_study"),
                }
                for e in education[:3] if isinstance(e, dict)
            ]
        else:
            education_trim = []

        rec = {
            "name": rr_person.get("name", ""),
            "_rocketreach_name": True,
            "title": (
                rr_person.get("current_title", "")
                or rr_person.get("job_title", "")
            ),
            "_rocketreach_title": True,
            "company": rr_person.get("current_employer", ""),
            "_rocketreach_company": bool(rr_person.get("current_employer")),
            "location": rr_person.get("location", ""),
            "_rocketreach_location": bool(rr_person.get("location")),
            "linkedin_url": rr_person.get("linkedin_url", ""),
            "_rocketreach_linkedin_url": bool(rr_person.get("linkedin_url")),
            "email": recommended_email,
            "_rocketreach_email": bool(recommended_email),
            "email_grade": email_grade,
            "phone": primary_phone,
            "_rocketreach_phone": bool(primary_phone),
            "skills": rr_person.get("skills") or [],
            "_rocketreach_skills": bool(rr_person.get("skills")),
            "verified_email": bool(emails),
            "verified_phone": bool(phones),
            "source": "RocketReach API",
            "source_tier": "B",
            "confidence": "MEDIUM",
            "source_access_method": "rocketreach_api",
            "_rocketreach": True,  # whole-record flag for simpler renderers
            # v7.1.3 — extended person fields (high-signal data previously dropped)
            "rr_id": rr_person.get("id"),
            "_rocketreach_rr_id": bool(rr_person.get("id")),
            "rr_profile_url": rr_person.get("profile_url") or rr_person.get("rr_profile_url"),
            "_rocketreach_rr_profile_url": bool(
                rr_person.get("profile_url") or rr_person.get("rr_profile_url")
            ),
            "profile_pic": rr_person.get("profile_pic"),
            "city": rr_person.get("city"),
            "state": rr_person.get("state"),
            "country": rr_person.get("country"),
            "region": rr_person.get("region"),
            "current_employer_domain": rr_person.get("current_employer_domain"),
            "current_employer_website": rr_person.get("current_employer_website"),
            "current_employer_linkedin_url": rr_person.get("current_employer_linkedin_url"),
            "current_employer_id": rr_person.get("current_employer_id"),
            "job_history": job_history_trim,
            "_rocketreach_job_history": bool(job_history_trim),
            "education": education_trim,
            "_rocketreach_education": bool(education_trim),
            "social_links": social_links,
            "_rocketreach_social_links": bool(social_links),
            "verified_emails": verified_emails,
            "verified_phones": verified_phones,
            "current_work_email": rr_person.get("current_work_email"),
            "current_personal_email": rr_person.get("current_personal_email"),
            "recommended_professional_email": rr_person.get("recommended_professional_email"),
            "recommended_personal_email": rr_person.get("recommended_personal_email"),
            "normalized_emails": rr_person.get("normalized_emails") or [],
            "job_start_date": rr_person.get("job_start_date"),
            "npi_number": rr_person.get("npi_number"),
        }
        return rec

    def budget_summary(self) -> dict[str, Any]:
        """
        Return a structured budget summary suitable for `meta.rocketreach_budget`.
        Shape matches the dossier template v7.1+.
        """
        audit = self.budget.audit_trail
        endpoints_called: dict[str, int] = {}
        credits_consumed: dict[str, int] = {}
        for entry in audit:
            ep = entry.get("endpoint", "unknown")
            endpoints_called[ep] = endpoints_called.get(ep, 0) + 1
            pool = entry.get("credit_pool")
            cc = entry.get("credits_consumed", 0) or 0
            if pool and cc:
                credits_consumed[pool] = credits_consumed.get(pool, 0) + int(cc)

        first_call = audit[0]["ts_iso"] if audit else None
        last_call = audit[-1]["ts_iso"] if audit else None

        return {
            "endpoints_called": endpoints_called,
            "credits_consumed": credits_consumed,
            "session_totals": {
                "account_checks": self.budget.account_checks_used,
                "company_lookups": self.budget.company_lookups_used,
                "company_searches": self.budget.company_searches_used,
                "person_lookups": self.budget.person_lookups_used,
                "person_searches": self.budget.person_searches_used,
                "profile_company_lookups": self.budget.profile_company_used,
                "bulk_batches": self.budget.bulk_batches_used,
                "check_status_polls": self.budget.check_status_polls_used,
            },
            "first_call_at": first_call,
            "last_call_at": last_call,
            "total_calls": len(audit),
        }


# =============================================================================
# CLI smoke test — python rocketreach_client.py <subcommand>
# =============================================================================


def _cli():
    """Minimal CLI. Never logs the API key."""
    args = sys.argv[1:]
    if not args:
        print(
            "Usage: python rocketreach_client.py "
            "<account|person|company|person-search|company-search|profile-company> [...]",
            file=sys.stderr,
        )
        sys.exit(2)

    try:
        client = RocketReachClient()
    except RocketReachAuthError as e:
        print(f"[eliss-rr] {e}", file=sys.stderr)
        sys.exit(3)

    cmd = args[0].lower()
    try:
        if cmd == "account":
            data = client.account()
            redacted = {
                k: ("***REDACTED***" if "key" in k.lower() or "token" in k.lower() else v)
                for k, v in (data or {}).items()
            }
            print(json.dumps(redacted, indent=2, default=str))
        elif cmd == "person":
            if len(args) < 3:
                print(
                    'Usage: python rocketreach_client.py person "<name>" "<employer>"',
                    file=sys.stderr,
                )
                sys.exit(2)
            data = client.lookup_person(name=args[1], current_employer=args[2])
            print(json.dumps(data, indent=2, default=str))
        elif cmd == "company":
            if len(args) < 2:
                print("Usage: python rocketreach_client.py company <domain>", file=sys.stderr)
                sys.exit(2)
            data = client.lookup_company(domain=args[1])
            print(json.dumps(data, indent=2, default=str))
        elif cmd == "person-search":
            if len(args) < 3:
                print(
                    'Usage: python rocketreach_client.py person-search '
                    '"<current_employer>" "<current_title>"',
                    file=sys.stderr,
                )
                sys.exit(2)
            results = client.person_search(
                query={"current_employer": [args[1]], "current_title": [args[2]]}
            )
            print(json.dumps(results, indent=2, default=str))
        elif cmd == "company-search":
            if len(args) < 2:
                print(
                    'Usage: python rocketreach_client.py company-search "<domain>"',
                    file=sys.stderr,
                )
                sys.exit(2)
            results = client.company_search(query={"domain": [args[1]]})
            print(json.dumps(results, indent=2, default=str))
        elif cmd == "profile-company":
            if len(args) < 3:
                print(
                    'Usage: python rocketreach_client.py profile-company '
                    '"<name>" "<employer>"',
                    file=sys.stderr,
                )
                sys.exit(2)
            data = client.profile_company_lookup(
                name=args[1], current_employer=args[2]
            )
            print(json.dumps(data, indent=2, default=str))
        else:
            print(f"Unknown command: {cmd}", file=sys.stderr)
            sys.exit(2)
    except RocketReachError as e:
        print(f"[eliss-rr] {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        print(
            f"[eliss-rr] budget: {json.dumps(client.budget_summary(), default=str)}",
            file=sys.stderr,
        )


if __name__ == "__main__":
    _cli()
