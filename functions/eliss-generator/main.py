"""eliss-generator — Catalyst Python 3.9 Job Function entry point.

Receives a job param `request_id` (the ROWID of a dossier_requests row).
Runs the 6-stage ELISS pipeline server-side:

    queued → preflight → rocketreach → synthesis → rendering → lint → upload

Each stage transition patches the dossier_requests row so the frontend
poller can show progress. Terminal states write status=succeeded |
status=partial | status=failed and completed_at.

Signature confirmed against zoho-catalyst skill reference.txt §
"Python Job Function Boilerplate" — args are (job_request, context),
order matters.
"""
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import zcatalyst_sdk

# Vendored eliss-light scripts live under skill/scripts/. They were written
# as standalone CLI tools; we import them as modules where possible (preflight,
# rocketreach_client) and subprocess them where their argparse + sys.exit make
# in-process invocation awkward (generate_report).
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE / "skill" / "scripts"))

import preflight  # noqa: E402  (skill-vendored)
from rocketreach_client import (  # noqa: E402
    RocketReachAuthError,
    RocketReachClient,
    RocketReachError,
    RocketReachRateLimited,
)

from lib.db import catalyst_datetime, select_one  # noqa: E402
from lib.depth_lint import depth_lint  # noqa: E402
from lib.store_lead import store_lead  # noqa: E402
from lib.synth import synthesize  # noqa: E402


LOG = logging.getLogger("eliss-generator")
if not LOG.handlers:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                        format="[%(asctime)s] %(levelname)s %(message)s")


class _BlockingError(Exception):
    """Raised after the dossier_requests row has been patched to 'failed'.

    Top-level handler catches this and calls context.close_with_failure
    without re-patching. Avoids double-writes when an inner stage already
    surfaced the failure reason to the user.
    """


def handler(job_request, context):
    """Catalyst Job Function entry — (job_request, context) per docs."""
    request_id = job_request.get_job_param("request_id")
    if not request_id:
        LOG.error("missing request_id in job params; closing as failure")
        context.close_with_failure()
        return

    try:
        app = zcatalyst_sdk.initialize()
    except Exception as e:
        LOG.exception("zcatalyst_sdk.initialize failed: %s", e)
        context.close_with_failure()
        return

    LOG.info("starting pipeline for request_id=%s", request_id)
    try:
        _run_pipeline(app, str(request_id))
        context.close_with_success()
    except _BlockingError as e:
        LOG.error("pipeline blocked for request_id=%s: %s", request_id, e)
        context.close_with_failure()
    except Exception as e:
        LOG.exception("unexpected error in pipeline for request_id=%s", request_id)
        try:
            _patch_request(app, request_id,
                           status="failed", stage="error",
                           error_message=str(e)[:9999])
        except Exception:
            pass
        context.close_with_failure()


# ────────────────────────────────────────────────────────────────────────────
#  Request row helpers
# ────────────────────────────────────────────────────────────────────────────

def _patch_request(app, request_id, **fields):
    """Update one or more columns on a dossier_requests row.

    Terminal-state writes (succeeded/failed/partial/cancelled) auto-stamp
    completed_at if the caller didn't provide it.
    """
    if not fields:
        return
    row = dict(fields)
    if row.get("status") in ("succeeded", "failed", "partial", "cancelled"):
        row.setdefault("completed_at", catalyst_datetime())
    row["ROWID"] = int(request_id)
    app.datastore().table("dossier_requests").update_row(row)


def _load_request(app, request_id):
    zcql = app.zcql()
    row = select_one(
        zcql,
        (
            "SELECT ROWID, user_id, intake_name, intake_email, "
            "intake_linkedin_url, intake_company_url, intake_notes "
            f"FROM dossier_requests WHERE ROWID = {int(request_id)}"
        ),
        "dossier_requests",
    )
    if not row:
        # Patch is pointless if the row doesn't exist — surface upstream.
        raise _BlockingError(f"dossier_requests row {request_id} not found")
    return {
        "user_id": row.get("user_id"),
        "intake": {
            "name": row.get("intake_name"),
            "email": row.get("intake_email"),
            "linkedin_url": row.get("intake_linkedin_url"),
            "company_url": row.get("intake_company_url"),
            "notes": row.get("intake_notes"),
        },
    }


# ────────────────────────────────────────────────────────────────────────────
#  Intake helpers
# ────────────────────────────────────────────────────────────────────────────

def _derive_domain(intake):
    """Email > company_url > linkedin (no path). Mirrors skill STEP 1."""
    email = intake.get("email")
    if email and "@" in email:
        return email.split("@", 1)[1].lower().strip()
    company_url = intake.get("company_url")
    if company_url:
        url = company_url.lower().strip()
        url = re.sub(r"^https?://", "", url)
        return url.split("/", 1)[0].lstrip("www.")
    raise _BlockingError(
        "cannot derive domain — provide email or company_url; linkedin_url alone is insufficient"
    )


def _company_name_guess(domain, intake):
    """Cheap fallback when the LLM hasn't yet enriched."""
    if not domain:
        return None
    label = domain.split(".")[0]
    if not label:
        return None
    return label.replace("-", " ").replace("_", " ").title()


# ────────────────────────────────────────────────────────────────────────────
#  Render — subprocess generate_report.py
# ────────────────────────────────────────────────────────────────────────────

def _slug(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", str(s)).strip("_") or "Unknown"


_OSINT_BANNER_REASONS = {
    "rr_full_miss": "RocketReach has no record of this organization.",
    "rr_company_miss": "RocketReach returned partial data — firmographics missing.",
}


def _inject_osint_banner(html, reason):
    """Prepend an OSINT-only banner div to the rendered HTML.

    Direct HTML injection rather than a markdown callout because the
    callout pipeline runs inside generate_report.py (subprocess); by
    the time we have `html` here, markdown is already rendered. The
    banner div uses inline styles to survive whatever stylesheet the
    renderer emitted.
    """
    detail = _OSINT_BANNER_REASONS.get(reason, "RocketReach data unavailable for this lead.")
    banner = (
        '<div class="eliss-osint-banner" role="status" '
        'style="background:#fef3c7;border:1px solid #f59e0b;'
        'border-left-width:4px;padding:12px 16px;margin:16px;'
        'border-radius:6px;font-family:system-ui,-apple-system,sans-serif;'
        'font-size:13px;color:#78350f;line-height:1.5;">'
        '<strong style="display:block;margin-bottom:4px;">'
        'OSINT-only dossier (no RocketReach baseline)</strong>'
        f'{detail} All values sourced from web search and preflight only. '
        'Confidence is lower than a standard RR-backed dossier — '
        'review carefully before sending outreach.'
        '</div>'
    )
    m = re.search(r"(<body[^>]*>)", html, re.IGNORECASE)
    if m:
        return html[: m.end()] + banner + html[m.end():]
    return banner + html


def _render(dossier_dict, request_id):
    """Write dossier JSON to temp dir, subprocess generate_report.py.

    Subprocess (not in-process import) because the script's main() ends in
    sys.exit() and reads sys.argv via argparse — both are awkward to
    monkey-patch reliably from a long-running Job Function.

    Returns (html_path, json_path) for cleanup.
    """
    tmp = Path(tempfile.gettempdir())
    ts = int(time.time() * 1000)
    json_path = tmp / f"eliss_dossier_{request_id}_{ts}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(dossier_dict, f, indent=2, default=str)

    script = _HERE / "skill" / "scripts" / "generate_report.py"
    if not script.exists():
        raise _BlockingError(f"generate_report.py missing at {script}")

    # Snapshot HTML files in tmp before the render so we can identify the new one.
    pre = set(tmp.glob("ELISS_*.html"))

    result = subprocess.run(
        [
            sys.executable, str(script), str(json_path),
            "--output-dir", str(tmp),
            "--format", "html",
            "--cleanup-input-json",
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=120,
    )
    if result.returncode != 0:
        stderr_tail = (result.stderr or "")[-500:]
        raise _BlockingError(
            f"generate_report.py exit {result.returncode}: {stderr_tail}"
        )

    new = sorted(tmp.glob("ELISS_*.html"), key=lambda p: p.stat().st_mtime, reverse=True)
    new = [p for p in new if p not in pre] or new
    if not new:
        raise _BlockingError("generate_report.py produced no HTML output")
    return str(new[0]), str(json_path)


# ────────────────────────────────────────────────────────────────────────────
#  Pipeline
# ────────────────────────────────────────────────────────────────────────────

def _run_pipeline(app, request_id):
    # ---- preflight ----------------------------------------------------------
    _patch_request(app, request_id,
                   status="running", stage="preflight",
                   started_at=catalyst_datetime())
    req = _load_request(app, request_id)
    intake = req["intake"]
    user_id = req["user_id"]
    if not user_id:
        _patch_request(app, request_id,
                       status="failed",
                       error_message="request row missing user_id")
        raise _BlockingError("request row missing user_id")

    try:
        domain = _derive_domain(intake)
    except _BlockingError as e:
        _patch_request(app, request_id, status="failed", error_message=str(e))
        raise

    company_guess = _company_name_guess(domain, intake)
    LOG.info("preflight: domain=%s company=%s", domain, company_guess)
    try:
        preflight_data = preflight.run_preflight(
            domain, company=company_guess, timeout=10, log=sys.stderr,
            lead_email=intake.get("email"),
        )
    except Exception as e:
        _patch_request(app, request_id, status="failed",
                       error_message=f"preflight failed: {str(e)[:500]}")
        raise _BlockingError(f"preflight failed: {e}")

    # ---- rocketreach baseline (auto-degrade on coverage gap) ---------------
    # RR_API_KEY missing and RocketReachAuthError/RateLimited/other-RocketReachError
    # are GENUINE FAILURES — hard-fail so the operator sees them. An empty
    # `company` slot in the returned baseline is a COVERAGE GAP (RR doesn't
    # have firmographics for this org — common for .gov/.edu/non-profits)
    # and is NOT a failure: the pipeline auto-degrades to OSINT-only synthesis.
    _patch_request(app, request_id, stage="rocketreach")
    if not os.environ.get("RR_API_KEY"):
        _patch_request(app, request_id,
                       status="failed",
                       error_message="RR_API_KEY not set — required for server-side generation")
        raise _BlockingError("RR_API_KEY missing")

    rr_call_count = 0
    rr_baseline = None
    rr_degraded = False
    rr_degradation_reason = None
    try:
        client = RocketReachClient()
        rr_baseline = client.run_baseline_enrichment(
            domain=domain,
            company_name=company_guess,
            contact_name=intake.get("name"),
            contact_linkedin=intake.get("linkedin_url"),
            contact_email=intake.get("email"),
            max_bulk_profiles=10,
        )
        rr_call_count = client.budget_summary().get("total_calls", 0) or 0
    except RocketReachAuthError as e:
        _patch_request(app, request_id, status="failed",
                       error_message=f"RocketReach auth error: {str(e)[:500]}")
        raise _BlockingError(f"RR auth: {e}")
    except RocketReachRateLimited as e:
        _patch_request(app, request_id, status="failed",
                       error_message=f"RocketReach rate-limited: {str(e)[:500]}")
        raise _BlockingError(f"RR rate-limited: {e}")
    except RocketReachError as e:
        _patch_request(app, request_id, status="failed",
                       error_message=f"RocketReach baseline failed: {str(e)[:500]}")
        raise _BlockingError(f"RR baseline failed: {e}")

    # Coverage-gap detection — when RR has no firmographics, the client
    # swallows /company/lookup/ 404s into rr_baseline['errors'] and returns
    # the dict with company=None. That's the degradation signal, NOT a failure.
    has_company = bool(rr_baseline and rr_baseline.get("company"))
    has_named_contact = bool(rr_baseline and rr_baseline.get("named_contact"))
    has_exec_dmu = bool(rr_baseline and rr_baseline.get("exec_dmu_enriched"))

    if not has_company:
        rr_degraded = True
        if not has_named_contact and not has_exec_dmu:
            rr_degradation_reason = "rr_full_miss"
            rr_baseline_for_synth = None
        else:
            rr_degradation_reason = "rr_company_miss"
            rr_baseline_for_synth = rr_baseline
        LOG.info("rr coverage gap (%s) — degrading to OSINT-augmented synthesis",
                 rr_degradation_reason)
        _patch_request(app, request_id,
                       rr_degraded=True,
                       rr_degradation_reason=rr_degradation_reason)
    else:
        rr_baseline_for_synth = rr_baseline

    # ---- synthesis ----------------------------------------------------------
    # Patch rr_calls upfront so a synthesis failure still leaves the observability
    # field populated (previously this only landed after synthesis succeeded).
    _patch_request(app, request_id, stage="synthesis", rr_calls=rr_call_count)
    LOG.info("synthesis: calling Anthropic with web_search (rr_degraded=%s)", rr_degraded)
    try:
        dossier_dict, usage = synthesize(
            intake, preflight_data, rr_baseline_for_synth,
            rr_degraded=rr_degraded,
            rr_degradation_reason=rr_degradation_reason,
        )
    except Exception as e:
        _patch_request(app, request_id, status="failed",
                       error_message=f"synthesis failed: {str(e)[:500]}")
        raise _BlockingError(f"synthesis failed: {e}")

    tokens_in = int(usage.get("input", 0) or 0)
    tokens_out = int(usage.get("output", 0) or 0)

    # ---- rendering ----------------------------------------------------------
    _patch_request(app, request_id, stage="rendering",
                   tokens_input=tokens_in, tokens_output=tokens_out,
                   rr_calls=rr_call_count)
    html_path, json_path = _render(dossier_dict, request_id)
    html = Path(html_path).read_text(encoding="utf-8")
    if rr_degraded:
        html = _inject_osint_banner(html, rr_degradation_reason)

    # ---- lint gate (one retry on blocking) ----------------------------------
    _patch_request(app, request_id, stage="lint")
    tier = (dossier_dict.get("scoring") or {}).get("tier")
    lint_result = depth_lint(html, tier, rr_degraded=rr_degraded)
    LOG.info("depth_lint: %s", lint_result)
    if lint_result["blocking"]:
        LOG.warning("blocking lint hits — regenerating once: %s", lint_result["hits"])
        # Use a distinct "synthesis_retry" stage so the UI can label this
        # second pass differently ("Researching (2nd pass)") and explain
        # the extra wait time to the user.
        _patch_request(app, request_id, stage="synthesis_retry")
        try:
            dossier_dict, usage2 = synthesize(
                intake, preflight_data, rr_baseline_for_synth,
                rr_degraded=rr_degraded,
                rr_degradation_reason=rr_degradation_reason,
            )
        except Exception as e:
            _patch_request(app, request_id, status="failed",
                           error_message=f"synthesis retry failed: {str(e)[:500]}")
            raise _BlockingError(f"synthesis retry failed: {e}")
        tokens_in += int(usage2.get("input", 0) or 0)
        tokens_out += int(usage2.get("output", 0) or 0)
        _patch_request(app, request_id, stage="rendering",
                       tokens_input=tokens_in, tokens_output=tokens_out)
        # Best-effort cleanup of the first attempt's HTML.
        try:
            Path(html_path).unlink(missing_ok=True)
        except Exception:
            pass
        html_path, json_path = _render(dossier_dict, request_id)
        html = Path(html_path).read_text(encoding="utf-8")
        if rr_degraded:
            html = _inject_osint_banner(html, rr_degradation_reason)
        _patch_request(app, request_id, stage="lint")
        lint_result = depth_lint(
            html, (dossier_dict.get("scoring") or {}).get("tier"),
            rr_degraded=rr_degraded,
        )

    # ---- upload -------------------------------------------------------------
    _patch_request(app, request_id, stage="upload")
    company_name = ((dossier_dict.get("company") or {}).get("name") or "Unknown")
    last_name = ((intake.get("name") or "").strip().split(" ") or ["Lead"])[-1]
    date_str = time.strftime("%Y-%m-%d")
    filename = f"ELISS_{_slug(company_name)}_{_slug(last_name)}_{date_str}.html"

    try:
        result = store_lead(app, user_id, filename, html, dossier_dict)
    except Exception as e:
        _patch_request(app, request_id, status="failed",
                       error_message=f"store_lead failed: {str(e)[:500]}")
        raise _BlockingError(f"store_lead failed: {e}")

    # ---- terminal -----------------------------------------------------------
    # Partial = some empty-state literals survived even after the retry,
    # but only the non-blocking ones (otherwise we'd have raised above).
    # rr_degraded ALSO forces partial regardless of lint outcome — an
    # OSINT-only dossier is by definition lower confidence than RR-backed,
    # and the UI uses the partial badge to surface that to the user.
    terminal_status = "partial" if (lint_result["hits"] or rr_degraded) else "succeeded"
    # lead_id is a Catalyst ROWID (17-digit bigint > 2^53). Pass as STRING
    # so JSON-number precision loss doesn't drop the last digit on the
    # server side. Sending int(result["id"]) silently becomes off-by-one
    # because the platform parses bigints with JS-Number precision.
    _patch_request(app, request_id,
                   status=terminal_status,
                   stage="done",
                   lead_id=str(result["id"]))

    LOG.info("pipeline complete: request_id=%s lead_id=%s status=%s tokens=%s/%s rr_calls=%s",
             request_id, result["id"], terminal_status, tokens_in, tokens_out, rr_call_count)

    # Cleanup temp files (json was --cleanup-input-json'd by the renderer, but
    # the HTML still sits in tmp).
    for p in (html_path,):
        try:
            Path(p).unlink(missing_ok=True)
        except Exception:
            pass
