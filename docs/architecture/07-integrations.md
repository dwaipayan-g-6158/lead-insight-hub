# 07 — Integrations

Every external system the application touches. One section per integration: what it does, where it's called, the env var that authenticates it, and the failure modes.

## Anthropic Claude

**Purpose:** Core LLM. Generates the dossier JSON (Light: one synthesis call; Heavy: 4 parallel subagents + parent consolidation).

**Env vars:**
- `ANTHROPIC_API_KEY` — required by both generators.
- `ANTHROPIC_MODEL` — Light only. Default `claude-sonnet-4-6`.
- `ANTHROPIC_SUBAGENT_MODEL` — Heavy only. Default `claude-sonnet-4-6`.
- `ANTHROPIC_PARENT_MODEL` — Heavy only. Default `claude-sonnet-4-6`.

**Where called:**
- `functions/eliss-generator/lib/synth.py` — Light synthesis with `web_search` (max_uses=4).
- `functions/eliss-heavy-generator/lib/fanout.py` — Heavy fan-out (4 subagents, max_uses=10 each) + parent consolidation (no tools).

**SDK:** `anthropic` Python package (the official one). Installed via each function's `requirements.txt`.

**Failure modes:**
- 401 — bad/rotated key. Surfaces as `synthesis failed: ...` on the request row. Rotate per [`maintenance/07-credentials-and-rotation.md`](../maintenance/07-credentials-and-rotation.md).
- 429 — rate limit. Often transient; Light retries automatically inside synth (one retry). Heavy does not retry the whole fan-out.
- 529 (overloaded) — Anthropic infrastructure issue. Retry the request after 5-10 min.
- Non-JSON output — handled by `JSONDecoder.raw_decode` at the first `{` to tolerate trailing narration (per memory rule `feedback_llm_json_trailing_content`).

**Cost discipline:** Light averages ~6-10K input + ~4-6K output tokens. Heavy averages ~25-40K input + ~15-25K output tokens (parent + four subagents). Token counts land on `dossier_requests.tokens_input` / `tokens_output` for billing reconciliation.

**Direct API only** — do **not** route through OpenRouter. OpenRouter doesn't relay the Anthropic Messages API (it serves OpenAI-compatible `/chat/completions`), and the application depends on Anthropic-only features like server `web_search`. Source: memory rule `feedback_openrouter_no_anthropic_messages_relay`.

## RocketReach (RR)

**Purpose:** Premium B2B contact and firmographic data. Drives the baseline enrichment that runs before parallel dispatch on every dossier.

**Env var:**
- `RR_API_KEY` — **required**. Without it, both generators write `status=failed, error_message="RR_API_KEY not set"` and exit. There is no "no-RR" fallback at the function level.

**Where called:**
- `functions/eliss-generator/skill/scripts/rocketreach_client.py` (and the heavy sibling).
- Invoked from each generator's `_run_pipeline()` at the `rocketreach` stage.

**Endpoints used (8 total):**
1. `GET /account/` — free health check.
2. `GET /company/lookup/{company_id}` — firmographics (1 `company_export` credit).
3. `POST /searchCompany` — search by criteria (1 `company_search` credit).
4. `GET /person/lookup/{person_id}` — person enrichment (1 `person_export` credit).
5. `POST /person/search` — search by criteria (1 `person_search` credit).
6. `GET /profile-company/lookup/{profile_id}` — person + company combined (1 `person_export`).
7. `POST /bulkLookup` — bulk person lookup, 1 credit per profile, up to 100 per batch.
8. `GET /person/checkStatus` — poll async lookup status (free).

**Baseline enrichment sequence:**
```
account()  →  lookup_company(domain)  →  person_search(execs)
            →  bulk_lookup(top-N execs)  →  profile_company_lookup(contact)
```

Light uses `max_bulk_profiles=10` (~12 person_export per dossier). Heavy uses `max_bulk_profiles=20` (~22 person_export). The exact count lands on `dossier_requests.rr_calls`.

**Coverage gaps are normal.** RR doesn't index every organization. When `lookup_company` returns no firmographics (common for `.gov`, `.edu`, smaller nonprofits), the client swallows the 404 and the generator sets `rr_degraded=true` with reason `rr_full_miss` (or `rr_company_miss` if it has people but no company). This is not a failure — the synthesis stage proceeds with an OSINT-only banner in the rendered HTML.

**Failure modes:**
- `RocketReachAuthError` → 401. Rotate key.
- `RocketReachRateLimited` → 429. Wait or upgrade plan.
- `RocketReachError` (generic) → unexpected response. Investigate.

All three close the job with `status=failed` and put the message in `error_message`.

## AlienVault OTX

**Purpose:** Threat-intelligence pulses. Used by the preflight script to detect whether the prospect's domain or IPs appear in any active threat pulses, and to scan the prospect's industry for recent campaigns.

**Env var:**
- `OTX_API_KEY` — **optional**. When unset, the preflight skips the OTX probe and proceeds. Set to the free community tier key from https://otx.alienvault.com.

**Where called:** `functions/eliss-generator/skill/scripts/preflight.py::probe_otx()`.

**Endpoints:**
- `GET /api/v1/indicators/domain/{domain}/general` — pulse hits on prospect domain.
- `GET /api/v1/indicators/IPv4/{ip}/general` — pulse hits on each DNS-resolved IP (first 3).
- `GET /api/v1/search/pulses?q={industry}` — sector pulses (only when `--industry` flag set; currently always off in Catalyst port).

**Failure mode:** Fail-soft. Network errors don't raise; the probe records `{checked: False, reason: "..."}` and the rest of the pipeline continues.

## XposedOrNot

**Purpose:** Public breach catalog. Surfaces whether the prospect's domain or the named contact's email appears in any disclosed breach.

**Env var:** None — uses free public endpoints.

**Where called:** `preflight.py::probe_xposedornot()`.

**Endpoints:**
- `GET /v1/breaches?domain={domain}` — always runs.
- `GET /v1/check-email/{lead_email}` — runs only when intake had `email`.
- `GET /v1/breach-analytics?email={lead_email}` — same gating.

**Rate limit:** 1 req/sec documented; one dossier issues at most 3 calls so never hit.

## HaveIBeenPwned

**Purpose:** Breach catalog (alternative to XposedOrNot, with broader coverage).

**Env var:** `HIBP_API_KEY` — **optional**. When empty, the probe is skipped.

**Where called:** `preflight.py::probe_hibp_domain()`.

## Catalyst Stratus

**Purpose:** Object storage for rendered HTML dossiers.

**Env vars:**
- `STRATUS_BUCKET` — bucket name. Default: `dossiers`. Set in `catalyst-config.json` for each function.
- `SIGNED_URL_TTL_SECONDS` — pre-signed GET URL lifetime. Default 3600 (1 hour). Set on the API function only.

**Where called:**
- `functions/api/lib/stratus.js` — generates signed URLs for the iframe (`signUrl`) and accepts uploaded HTML from the legacy upload flow (`putHtml`).
- `functions/eliss-generator/lib/store_lead.py` — uploads the generated HTML.

**Bucket:** `dossiers`. Created 2026-05-12. URL pattern: `https://dossiers-development.zohostratus.in/<key>`. Versioning, encryption, and audit are all **disabled** in development. Production posture is the same as of the v1.0.0 baseline.

**Key naming convention:** `dossiers/<user_id>/ELISS_<Company>_<Last>_<YYYY-MM-DD>.html` — the prefix `dossiers/` is the bucket name; subsequent segments are the object path.

**Critical gotcha — no in-place overwrite.** `putObject` with an existing key returns 409 `key_already_exists`. A `delete + put` sequence silently wipes data and *still* fails the put. The only safe write pattern is **write to a new key + update the FK column** (`leads.storage_path`). Per memory rule `feedback_catalyst_stratus_no_overwrite`.

**Failure modes:**
- 409 on duplicate key — never expected because each generation creates a new lead row with a fresh timestamp.
- 5xx during upload — patched as `store_lead failed: ...` on the dossier_requests row.

## Catalyst Native Auth

**Purpose:** User identity, session management, signup confirmation, password resets.

**Env vars:** None — auth is configured at the project level in the Catalyst console (Authentication settings).

**Where called:**
- `functions/api/lib/auth.js` — `attachCatalyst` initialises the SDK per-request; `requireUser` reads the session cookie.
- `functions/api/routes/signup.js` — calls `app.userManagement().registerWithDetails(...)` to create accounts.
- `functions/api/lib/mailer.js` — sends the post-signup confirmation email via Catalyst Mail.

**Session cookie:** Set on the project's primary domain. Cross-subdomain (e.g., the Stratus bucket origin) does NOT see the cookie, which is why the iframe loads its HTML via pre-signed URLs rather than direct GET.

**Roles:**
- Catalyst's project-user roles are `App Administrator` and `App User`. These are **infrastructure-level** roles for the Catalyst console — they don't auto-grant application-level admin powers.
- The application's RBAC lives in the `user_roles` table with `role IN ('admin', 'user')`. App Admin / app `role` are two separate concepts. See [10-security-and-rbac.md](./10-security-and-rbac.md).

**Failure modes:**
- 401 from `requireUser` — no/expired session cookie. Frontend redirects to the hosted login.
- Signup failures — Catalyst returns specific reasons (`user_exists`, `invalid_email`, `weak_password`); `signup.js` forwards them to the SPA verbatim.

## Catalyst Data Store

**Purpose:** Relational tables for `leads`, `lead_signals`, `user_roles`, `dossier_requests`.

**Env vars:** None — handled by the SDK on a per-request basis.

**Where called:** Anywhere a route or job needs to read/write rows. The two helpers are:
- `functions/api/lib/db.js::fetchAll` — paginated ZCQL helper (the 300-row silent cap is real; always paginate).
- `functions/eliss-generator/lib/db.py::select_one`, `catalyst_datetime` — server-side wrappers.

**Bigint precision rule (FK columns):** ROWID values that travel as JSON numbers lose their last digit (17-digit ID > 2^53). Always pass FK column values as strings. Per memory rule `feedback_catalyst_bigint_json_precision`.

## Catalyst Job Scheduling

**Purpose:** Dispatch `eliss-generator` / `eliss-heavy-generator` jobs from the API.

**Env vars:** None.

**Where called:** `functions/api/routes/dossiers.js::POST /generate` calls `app.jobScheduling().jobPool('elissgenpool').submitJob(...)`.

**Job Pool:** `elissgenpool` — Function-type, 1536 MB memory ceiling. Created 2026-05-15. Defined in the Catalyst console; not in `catalyst.json`.

**Failure modes:**
- Pool full — submission queues until a slot opens. The dispatcher is non-blocking, so this only delays job start, not the API response.
- Function code crash before stage 1 — `dossier_requests` row stays at `stage=queued, status=pending` indefinitely. The 15-min timeout is per-execution, not per-request — the API has no internal "stale request" cleanup. Frontend treats >5 min in `queued` as suspicious.

## Catalyst Mail

**Purpose:** Outbound email — signup confirmations, password resets, admin notifications.

**Env vars:** None.

**Where called:** `functions/api/lib/mailer.js`. Catalyst's `mail()` SDK handles the SMTP layer transparently.

**Sender:** Configured in Catalyst console → Mail Service. Production sender domain must be DNS-verified before user emails will deliver reliably; for development, the project's default sender works.

## Cross-references

- Env-var deploy discipline (the OVERWRITE-on-deploy gotcha) → [08-catalyst-deployment.md](./08-catalyst-deployment.md)
- Per-secret rotation cadence → [`maintenance/07-credentials-and-rotation.md`](../maintenance/07-credentials-and-rotation.md)
- Why the iframe pattern is used (cross-origin Stratus) → [02-frontend-vite-react.md](./02-frontend-vite-react.md)
- The full skill-level explanation of how Anthropic + RR + preflight interact → [09-eliss-skill-explained.md](./09-eliss-skill-explained.md)
