# 04 — Deployment Runbook

The exact commands to deploy the application. This document is the single source of truth — never type a deploy command from memory.

## Prerequisites (one-time, per developer machine)

Before your first deploy, confirm:

- [ ] **Catalyst CLI installed** — `catalyst --version` returns ≥ a recent version. Install via `npm i -g zcatalyst-cli`.
- [ ] **Logged in** — `catalyst login` complete; credentials in `%APPDATA%\zcatalyst-cli-nodejs\Config\zcatalyst-cli.json`.
- [ ] **Python 3.9 installed** — `py -3.9 --version` returns `Python 3.9.x`. Required for deploying Python Job functions (CLI spawns local Python to resolve `requirements.txt`). Per memory rule `feedback_catalyst_python_function_deploy_needs_local_python39`.
- [ ] **Node 18+** — `node --version` returns ≥ 18.
- [ ] **`catalyst-config.json` files in place** — copy from `*.example.json` and fill in real keys for each function:
  - `functions/api/catalyst-config.json`
  - `functions/eliss-generator/catalyst-config.json`
  - `functions/eliss-heavy-generator/catalyst-config.json`
- [ ] **`.gitignore` lists `catalyst-config.json`** — confirm before committing.

## Pre-deploy checks

Before running any deploy command:

- [ ] Latest changes pulled from the development branch.
- [ ] The CR is approved (per [`01-change-request-process.md`](./01-change-request-process.md)).
- [ ] Unit tests pass locally.
- [ ] If SPA changed: `cd app; npm install; npm run build` — verify `app/dist/index.html` was just regenerated.
- [ ] If `catalyst-config.json` changed: confirm secrets are correct AND that nothing about to be deployed will overwrite a Console-set value. (Per the top Catalyst gotcha, the deploy will overwrite the function's env var set.)

## Standard deploys

> **Always use the non-interactive form.** Claude Code's PowerShell is non-TTY; a bare `catalyst deploy` will hang silently waiting for confirmation prompts. The pattern below works in any shell. Per memory rule `reference_catalyst_cli_noninteractive_deploy`.

### A. Full deploy to development (functions + client)

Use when both backend and frontend changed.

```powershell
# From the project root
cd app; npm run build; cd ..

catalyst deploy `
    -p 31210000000133001 `
    --org 60066539659 `
    --dc in `
    < NUL
```

Flag semantics:
- `-p` — Project ID.
- `--org` — Environment ID (**not** ZAID). Dev: `60066539659`. Prod: `50042142947`.
- `--dc` — Data center: `in`.
- `< NUL` — PowerShell-safe redirection of stdin to NUL so the CLI doesn't wait for confirmation prompts.

Output: progress logs per function and per client asset. Final line `DEPLOYMENT SUCCESSFUL` or an error trace.

### B. Client-only redeploy (after a UI-only change)

After editing `app/src/...`:

```powershell
cd app; npm run build; cd ..

catalyst deploy --only client `
    -p 31210000000133001 `
    --org 60066539659 `
    --dc in `
    < NUL
```

`--only client` skips the function deploy entirely. Faster (no zip of `functions/`). Per memory rule `feedback_catalyst_client_deploy_split` — `--only functions` does NOT ship the SPA, so after `app/` changes you must either rebuild + bare `catalyst deploy` or rebuild + `--only client`.

### C. Single-function deploy

Use when you changed exactly one function and want to skip the others — especially useful to avoid the local Python 3.9 dependency resolve when the change is in `functions/api/` only:

```powershell
catalyst deploy --only functions:api `
    -p 31210000000133001 `
    --org 60066539659 `
    --dc in `
    < NUL
```

For the Python generators:

```powershell
catalyst deploy --only functions:eliss-generator `
    -p 31210000000133001 `
    --org 60066539659 `
    --dc in `
    < NUL

catalyst deploy --only functions:eliss-heavy-generator `
    -p 31210000000133001 `
    --org 60066539659 `
    --dc in `
    < NUL
```

You can chain multiple `--only` flags by repeating: `--only functions:api --only client`.

### D. Promote dev → prod

After dev validation passes, the prod-promoter (different person from the CR Owner — see [`01-change-request-process.md`](./01-change-request-process.md)) runs:

```powershell
# Rebuild the client (defensive — the dev build may differ from main)
cd app; npm run build; cd ..

catalyst deploy `
    -p 31210000000133001 `
    --org 50042142947 `
    --dc in `
    < NUL
```

Only `--org` changes between environments. The build output and function code are identical; the env-var files in each function's `catalyst-config.json` must be the production version (separate secrets!).

> **Each environment needs its own `catalyst-config.json`.** Common pattern: keep `catalyst-config.dev.json` and `catalyst-config.prod.json` alongside the example, gitignored both. Before each environment-specific deploy, copy the appropriate one to `catalyst-config.json`.

## Post-deploy verification

Every deploy ends with this 5-minute check sequence. Don't skip.

### 1. Health endpoint

```powershell
Invoke-RestMethod "https://lead-insight-hub-60066539659.development.catalystserverless.in/server/api/health"
```

Expected: `{ok: True, ts: <iso>, build: "<expected BUILD_ID>"}`. If `build` doesn't match what's in `functions/api/index.js`, the function image didn't update. Investigate before believing the deploy succeeded.

### 2. SPA loads

Open the public URL in a browser. The dashboard should render. Open DevTools → Console; verify no red 4xx/5xx in the Network tab.

### 3. Smoke pack

Run the smoke checklist from [`03-testing-strategy.md`](./03-testing-strategy.md). At minimum:
- Sign in.
- Generate one light dossier and watch it through to `done`.
- Open the resulting lead detail page; iframe loads.

### 4. Function logs

Catalyst Console → Functions → each function → Logs tab. Look for unhandled exceptions in the last 15 minutes. Especially check `eliss-generator` and `api` since they're the high-traffic functions.

### 5. (Production only) Customer comms

If this was a customer-impacting prod deploy, post a "deploy complete" note in the team's channel with the commit SHA and the smoke pack outcome.

## Common failures

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `ZIPSANITIZER_FILES_COUNT_EXCEEDED` | Client `source` points at a directory containing `node_modules/` | Verify `catalyst.json::client.source = "app/dist"` |
| `DEPLOYMENT SUCCESSFUL` but `/health` returns old BUILD_ID | `catalyst.json` missing `"functions"` section | Verify both `functions` and `client` sections present |
| `python3.9: command not found` during Python function build | Python 3.9 not installed locally | Install Python 3.9 from python.org with "Add to PATH" |
| Function still has old env vars after deploy | `catalyst-config.json` not pulled before deploy | Confirm the right `catalyst-config.json` is present locally; re-deploy |
| Stage `queued` request never starts | Job Pool memory exhausted or no `catalyst_job_id` set | Check `dossier_requests.catalyst_job_id`; if null, the API didn't dispatch; check API logs |
| Deploy hangs forever | Bare `catalyst deploy` without `< NUL` in non-TTY shell | Cancel; re-run with `< NUL` |

## When **not** to deploy

- During the team's stand-up (causes interrupted deploys).
- Friday afternoon to production (industry convention — fix-forward is harder when the team's offline).
- While a customer demo is in progress against the dev environment.
- When the smoke pack from the previous deploy hasn't been run yet (don't pile changes on unverified builds).

## Cross-references

- The env-var file mechanism and why it overwrites Console values → [`../architecture/08-catalyst-deployment.md`](../architecture/08-catalyst-deployment.md)
- Rollback if a deploy goes wrong → [`05-rollback-procedures.md`](./05-rollback-procedures.md)
- The CR/approval flow gating any deploy → [`01-change-request-process.md`](./01-change-request-process.md)
- Smoke pack details → [`03-testing-strategy.md`](./03-testing-strategy.md)
