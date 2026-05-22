# 03 — Testing Strategy

How we know a change is safe to deploy. Four layers: unit, integration, manual smoke, regression. None of them are optional for production-bound changes.

## Layer 1 — Unit tests

**Scope:** Pure functions, isolated logic. No network, no Catalyst SDK, no real database.

**Frameworks:**
- Node (api function): use `vitest` (preferred) or `jest`. Test runner: `npm test` from the function directory.
- Python (eliss-generator, eliss-heavy-generator): `pytest`. Test runner: `python -m pytest` from each function directory.

**What to cover:**
- `lib/db.js::fetchAll` paginates correctly (mock the ZCQL response).
- `lib/auth.js::loadRole` self-heals when `user_roles` row is missing.
- `lib/parser.js` extracts the right scoring fields from an uploaded HTML.
- `lib/featureFlags.js::isHeavyAllowed` returns false for non-allowlisted users.
- `lib/synth.py::synthesize` retries on JSON parse failure.
- `lib/depth_lint.py::depth_lint` flags HOT-tier shortfalls correctly.

**Anti-pattern to avoid:** mocking the database to "test" data-store interactions. See Layer 2 — integration tests own those.

## Layer 2 — Integration tests

**Scope:** Function code talking to **the real dev environment's** Catalyst services. Not unit tests pretending to be integration.

The dev environment (`60066539659`) is the integration target. Production is never used for tests.

**Setup:**
- Test user account: `dwaipayan.g@zohotest.com` (per memory rule `reference_lead_insight_hub_test_credentials`).
- Hit the dev URL directly: `https://lead-insight-hub-60066539659.development.catalystserverless.in/server/api/...`.
- Use a test data prefix in any inserted rows (e.g., `lead_name="TEST-{timestamp}"`) so test rows are easy to clean up.

**What to cover:**
- Login → `/me` returns the expected user + role.
- `POST /dossiers/generate` with a known-good intake → row inserted, job dispatched, eventually reaches `succeeded` or `partial`.
- `GET /leads` honors filters (tier, ICP rating, search).
- Admin routes return 403 for non-admin users.
- Stratus signed URL returns 200 within the TTL and 403 after.

**What to avoid:**
- Long-running synthesis tests in CI — the test would take 5+ minutes and burn Anthropic credits. Instead, mock at the `synthesize()` boundary for these.
- Tests that depend on a specific live RocketReach response — RR data changes. Snapshot the response shape, not the specific values.

## Layer 3 — Manual smoke tests

**Scope:** End-to-end happy paths in a browser. The 10-minute "did anything obvious break?" sweep run before promoting to production.

The smoke pack lives at `tests/full-app-test-report.md` (already in the repo). Updated 2026-05-22 in `tests/login-functional-regression-2026-05-22.md` for auth-related changes.

**Standard pre-deploy smoke pack:**
1. **Health check** — `GET https://<env>/server/api/health` returns `{ok: true, build: <expected BUILD_ID>}`.
2. **Sign in** — load the SPA, sign in with test credentials, verify dashboard renders.
3. **Generate a dossier (light)** — submit a known prospect; verify the request row appears in the active-requests pill; wait for `done`; open the lead detail page and verify the iframe loads.
4. **Generate a dossier (heavy)** — 5-tap the modal title, submit; verify `eliss-heavy-generator` was dispatched (check `catalyst_job_id` matches a heavy job in Catalyst console).
5. **Lead list filters** — switch tier filters, search by company name; verify counts make sense.
6. **Admin panel** (admin user only) — list users, change a test user's role, restore it.
7. **Sign-up** — open `/signup` in an incognito window, submit a throwaway email, verify confirmation email arrives.
8. **Mobile sanity** — DevTools mobile emulation: verify nav drawer, score summary card, sheet close button work.

If any step fails, **do not promote** — investigate first. Treat smoke as the last "I trust this build" gate.

## Layer 4 — Regression tests

**Scope:** Re-running smoke whenever a UI-impacting change ships, plus targeted re-runs of any test that previously caught a bug.

Keep failing-then-fixed test cases in `tests/` so the failure mode is recorded. Examples already in repo:
- `tests/login-functional-regression-2026-05-22.md` — login regression after a session-cookie change.
- `tests/user-management-report.md` — admin role-change UX checks.

## CI/CD

**Current state (v1.0.0):** No CI/CD pipeline. All testing is manual or developer-machine-driven.

**Recommended next step:** Catalyst Pipelines (see `references/pipelines.md` in the zoho-catalyst skill). A minimal `catalyst-pipelines.yaml` would:
1. On push to `main`: run `npm test` in `functions/api/` and the SPA, plus `pytest` in both generators.
2. On tag `v*.*.*`: build the SPA, deploy to production with the non-interactive command.

Until pipelines land, manual deploy from a developer machine is authoritative. Adding pipelines is a backlog item; do not block v1.0.0 on it.

## Token-burn discipline

Tests that hit Anthropic or RocketReach cost real money. Two rules:

1. **Never test against production keys.** Dev environment uses development-tier keys with budget caps.
2. **Mock the LLM call boundary in unit tests.** `lib/synth.py::synthesize` is mockable via dependency injection — pass a fake `client` parameter.

A run-away test that loops calling `/dossiers/generate` will burn $20-50 of token budget in 30 minutes. The Catalyst Job Pool's 15-minute timeout caps individual runs, but not the loop. Watch for tight `while` loops in test scripts.

## Cross-references

- The smoke pack the runbook references → `tests/full-app-test-report.md` (in repo root)
- Existing regression evidence → `qa-audit-2026-05-15/FOLLOWUPS.md` (in repo root)
- How a CR ties test artifacts to a deploy → [`01-change-request-process.md`](./01-change-request-process.md)
- Where smoke failures escalate → [`02-issue-triage.md`](./02-issue-triage.md)
