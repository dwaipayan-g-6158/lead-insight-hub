# 08 — Catalyst Deployment

How the application gets onto Catalyst, how env vars are managed, and the exact commands the team runs. Read this before your first deploy.

## `catalyst.json`

The project manifest. Source-of-truth for what gets deployed.

```json
{
  "projectName": "lead-insight-hub",
  "projectId": "31210000000133001",
  "envId": "60066539659",
  "functions": {
    "targets": ["api", "eliss-generator", "eliss-heavy-generator", "dossier-sweeper"],
    "source": "functions"
  },
  "client": {
    "source": "app/dist"
  }
}
```

Three rules that matter:

1. **`functions.targets`** lists what `catalyst deploy --only functions` ships. If you add a new function, add its directory name here — otherwise the deploy "succeeds" without your function. See the top-five gotcha in the `zoho-catalyst` skill.
2. **`client.source` points at the build output**, not the source tree. Pointing at `app/` directly would include `node_modules/` and fail with `ZIPSANITIZER_FILES_COUNT_EXCEEDED`. There is no `.catalystignore` mechanism.
3. **`envId` is the Development environment, and the CLI only ever deploys to Development.** The `--org` flag is the **Org ID** (always `60066539659` here), **not** an environment selector — passing the prod env id to it does *not* target production. Promotion to Production is a separate, console-only flow (see §"Promote to production" below).

## Functions

Four function directories under `functions/`:

| Function | Type | Runtime | Memory | Timeout |
| --- | --- | --- | --- | --- |
| `api` | Advanced I/O | Node 18 | (Catalyst default — 128 MB unless tuned in console) | 30 s default |
| `eliss-generator` | Job | Python 3.9 | **512 MB** (per `catalyst-config.example.json`) | 900 s |
| `eliss-heavy-generator` | Job | Python 3.9 | **3072 MB** | 900 s |
| `dossier-sweeper` | Job (cron-driven) | Node 18 | **256 MB** | — |

`dossier-sweeper` is triggered by the `dossier_sweeper_cron` pre-defined cron (every 5 min) — it has no API Gateway route. It reads one env var, `ELISS_GEN_JOBPOOL_ID`, which must be set **Production-scoped** in the console after a migration (see §"Promote to production").

The Job functions execute in the `elissgenpool` Job Pool (memory: 1536 MB at the pool level). The pool's memory caps individual function memory at runtime — the per-function `memory` field in `catalyst-config.json` is the request; the pool ceiling enforces the actual allocation.

> **Heavy function memory mismatch:** The heavy generator declares `memory: 3072` but the pool ceiling is `1536`. In practice the function runs at the pool ceiling. If heavy runs OOM in production, the fix is to **bump the pool memory** in the Catalyst console (Application → Job Scheduling → Job Pools → `elissgenpool` → Edit), not the per-function value.

## Build flow

The client must be built before deployment because `client.source = app/dist`.

```powershell
# From the project root
cd app
npm install                # first time only
npm run build              # writes app/dist/
cd ..
```

Vite emits hashed assets to `app/dist/`. The build is fully static; there is no SSR step.

## Deploy commands

> **Do not use bare `catalyst deploy`** from Claude Code's PowerShell. The CLI prompts for confirmations and hangs on non-interactive shells. Always pass `-p`, `--org`, `--dc`, and `< NUL` (PowerShell-safe stdin redirect).

### Full deploy (functions + client) to development

```powershell
catalyst deploy `
  -p 31210000000133001 `
  --org 60066539659 `
  --dc in `
  < NUL
```

The `< NUL` redirect tells the CLI no stdin is available, which makes prompts auto-default. The backticks are PowerShell line continuations.

### Client-only redeploy (after a UI change)

```powershell
cd app; npm run build; cd ..
catalyst deploy --only client `
  -p 31210000000133001 `
  --org 60066539659 `
  --dc in `
  < NUL
```

The split exists because `catalyst deploy --only functions` does **not** ship the React client. After `app/` changes, you must either rebuild + bare `catalyst deploy`, or rebuild + `--only client`. See the memory rule `feedback_catalyst_client_deploy_split`.

### Single-function deploy (skip Python local install for mixed projects)

```powershell
catalyst deploy --only functions:api `
  -p 31210000000133001 `
  --org 60066539659 `
  --dc in `
  < NUL
```

The `--only functions:<name>` form targets exactly one function. This is the recommended path when you've changed only `functions/api/*` — it skips the Python Job functions, which would otherwise trigger a local Python 3.9 dependency install before zipping.

### Promote to production

> ⚠️ **There is no CLI path to Production.** `catalyst deploy` (with any `--org` value) only ever deploys to **Development**. Promotion is done **exclusively** through the Catalyst console deployment wizard. A previous version of this doc claimed `catalyst deploy --org 50042142947` promotes to prod — that is wrong; ignore any such command.

Production promotion is a **console migration**: it clones **schema + config + function code** from Dev to Prod, but **not row data** and **not Stratus objects** (prod tables come up empty — that's expected). Resource IDs are preserved across environments.

**Click path:** Console → open `lead-insight-hub` → **Settings → Environments → Deployments → Create Deployment**. A 3-step wizard:

1. **Select Features** — service-level checkboxes only (Serverless / Job Scheduling / CloudScale / Settings); the "19/19" counts are informational, not per-component pickers. It is **all-or-nothing per service**. Web Client Hosting lives under **CloudScale**, so any web-client update pulls in CloudScale. Set a **commit message (≤40 chars)**.
2. **Diff Generation** — takes seconds to ~11 min. Poll `GET /baas/v1/project/<projId>/migrate/<deployId>` for `migration_status` (`Diff_Completed`), then hard-reload to render the diff + the "Initiate Deployment" button. Verify Datastore/NoSQL/Stratus show **Total Changes: 0** before initiating; benign symmetric `Table_Scopes`/`Table_Permissions` re-staging is normal.
3. **Initiate Deployment** → "Yes, Proceed" → poll to `Completed`.

**Gotchas:**
- A deployment stuck at `Diff_Completed` **blocks** new ones — open it and **Abort** first.
- If CloudScale/Authentication is in the diff **and** a Zoho social login exists in Dev, the wizard demands a Zoho OAuth Client ID + Secret (a hard gate). The project keeps that gate clear by **deleting the Dev Zoho social login** (Authentication → Authentication Type → "Zoho" → kebab → Delete) — re-addable later.
- Function **env vars are per-environment** and are **not** carried by the migration. They must be set as **Production-scoped** console values per function. Set them via the console UI (scripted automation of that form is unreliable). Job functions cold-start per run (pick up env automatically); the warm `api` function needs a fresh instance (bump a `BUILD_ID` constant → CLI-deploy to Dev → re-run the migration) for changed prod env to take effect.

**Pre-flight checks before promoting**: read [`../maintenance/04-deployment-runbook.md`](../maintenance/04-deployment-runbook.md). Full details and the verified prod IDs are in the memory rule `reference_catalyst_dev_to_prod_promotion`.

#### Deployment history (most recent first)

| Date | Deploy ID | Commit | Contents |
| --- | --- | --- | --- |
| 2026-06-17 | `31210000000260051` | Prod 0617 sweeper age-guard fix | **Patch.** `api` + `dossier-sweeper` updated, `dossier_sweeper_cron` re-enabled. Adds a `CREATEDTIME` age guard so the stale-sweep (cron + inline) marks abandoned dossiers `failed` instead of resuming them — fixes the `1.2.0` cron resurrecting a 4-day-old Heavy dossier. New `sweep_resume_max_age_min` setting (default 180 min). No schema/data change, no gate. |
| 2026-06-17 | `31210000000260040` | Deploy Dev to Prod 0617 sweeper+resume | **4 entities, no schema/data change, no gate.** Added `dossier-sweeper` Job function + `dossier_sweeper_cron` (every 5 min); updated `eliss-generator` (Light self-dispatch resume parity with Heavy); refreshed web client (iOS PWA login-zoom fix `v=35`, mobile bottom-sheet nav, EngineBadge, dialog FLIP). `api` + `eliss-heavy-generator` unchanged. Post-deploy: set `dossier-sweeper` Production-scoped `ELISS_GEN_JOBPOOL_ID=31210000000151372`; cron verified enabled. |
| 2026-06-13 | `31210000000235055` | Deploy Dev to Prod 0613 softtol+UX | 3 functions + web client updated; `app_settings` table + 3 `dossier_requests` checkpoint columns added. Tier-aware soft tolerance, source backfill, zero-sources lint, dialog animations. Fully additive, no gate. |

## Env vars and the `catalyst-config.json` trap

Every Catalyst function has env vars set in `catalyst-config.json`. The CLI uploads this file on every deploy — and **the upload OVERWRITES the function's entire env-var set**, silently. Any secret set manually in the Catalyst console UI gets wiped if it isn't also in `catalyst-config.json`.

This is the #1 most painful gotcha in the platform. Rules:

1. **All env vars — including secrets — live in `catalyst-config.json`.** Gitignore this file.
2. **`catalyst-config.example.json` is the template.** Keep it in git with placeholder values so a new dev can `cp catalyst-config.example.json catalyst-config.json` and fill in their own keys.
3. **Never set a secret in the Catalyst console UI.** It will be wiped on the next deploy.

### Required env vars (per function)

#### `functions/api/` — no required env vars

The Express function reads only from `catalyst-config.example.json`:

```json
{
  "env": {
    "STRATUS_BUCKET": "dossiers",
    "SIGNED_URL_TTL_SECONDS": "3600"
  }
}
```

Add or override values in the gitignored `catalyst-config.json` if you need different bucket names or shorter TTLs in production.

#### `functions/eliss-generator/`

```json
{
  "deployment": {
    "name": "eliss-generator",
    "stack": "python_3_9",
    "type": "job",
    "memory": 512,
    "timeout": 900,
    "env_variables": {
      "ANTHROPIC_API_KEY": "sk-ant-...",
      "ANTHROPIC_MODEL": "claude-sonnet-4-6",
      "RR_API_KEY": "<your-rocketreach-key>",
      "HIBP_API_KEY": "",
      "STRATUS_BUCKET": "dossiers"
    }
  },
  "execution": { "main": "main.py" }
}
```

`HIBP_API_KEY` is optional — when empty, the preflight skips the HaveIBeenPwned probe and proceeds.

#### `functions/eliss-heavy-generator/`

Same shape; the heavy function adds split Anthropic models (parent vs. subagent) and an optional OTX key:

```json
{
  "deployment": {
    "name": "eliss-heavy-generator",
    "stack": "python_3_9",
    "type": "job",
    "memory": 3072,
    "timeout": 900,
    "env_variables": {
      "ANTHROPIC_API_KEY": "REPLACE_WITH_ANTHROPIC_API_KEY",
      "ANTHROPIC_SUBAGENT_MODEL": "claude-sonnet-4-6",
      "ANTHROPIC_PARENT_MODEL": "claude-sonnet-4-6",
      "RR_API_KEY": "REPLACE_WITH_ROCKETREACH_API_KEY",
      "HIBP_API_KEY": "",
      "OTX_API_KEY": "",
      "STRATUS_BUCKET": "dossiers"
    }
  },
  "execution": { "main": "main.py" }
}
```

> **Stack value is `python_3_9`, not `python39`.** Despite what some older Catalyst CLI references show, the live API requires the underscore form. Source: memory rule `feedback_catalyst_python_function_deploy_needs_local_python39`.

## Python 3.9 local dependency

Deploying a Python function requires Python 3.9 **on the developer's machine** because the CLI spawns it locally to resolve `requirements.txt` before zipping. If you only have 3.11 or 3.12 installed, the deploy fails with a cryptic "command not found" against `python3.9`.

**Install from python.org → 3.9.x → "Add to PATH"** before your first Python function deploy. The CLI looks for the binary on PATH.

When you don't need Python (e.g., a UI-only change), use `--only functions:api` and `--only client` to skip the Python resolve step entirely.

## Post-deploy verification

```powershell
# Hit /health on the deployed API — should return BUILD_ID matching index.js
Invoke-RestMethod "https://lead-insight-hub-60066539659.development.catalystserverless.in/server/api/health"

# Expected JSON shape:
# { ok: true, ts: "<iso8601>", build: "2026-05-21-self-signup" }
```

If `build` doesn't match the `BUILD_ID` constant in `functions/api/index.js`, the function image didn't update — investigate before believing the deploy succeeded.

## Pipelines and CI

The project currently uses **manual deploys** — no `catalyst-pipelines.yaml` is configured. Promotions are kicked off by hand from a developer machine. If/when CI lands, document the pipeline file in this section and update `04-deployment-runbook.md`.

## Cross-references

- The full pre-deploy / post-deploy checklist → [`maintenance/04-deployment-runbook.md`](../maintenance/04-deployment-runbook.md)
- Stratus bucket layout and signed-URL TTL → [07-integrations.md](./07-integrations.md)
- Why Job Pool memory matters → [05-eliss-heavy-generator.md](./05-eliss-heavy-generator.md)
- Credential rotation cadence → [`maintenance/07-credentials-and-rotation.md`](../maintenance/07-credentials-and-rotation.md)
