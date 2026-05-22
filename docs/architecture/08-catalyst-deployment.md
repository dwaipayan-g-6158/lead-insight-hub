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
    "targets": ["api", "eliss-generator", "eliss-heavy-generator"],
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
3. **`envId`** is the development environment by default. Use `--org <envId>` on the CLI to deploy to production (`50042142947`).

## Functions

Three function directories under `functions/`:

| Function | Type | Runtime | Memory | Timeout |
| --- | --- | --- | --- | --- |
| `api` | Advanced I/O | Node 18 | (Catalyst default — 128 MB unless tuned in console) | 30 s default |
| `eliss-generator` | Job | Python 3.9 | **512 MB** (per `catalyst-config.example.json`) | 900 s |
| `eliss-heavy-generator` | Job | Python 3.9 | **3072 MB** | 900 s |

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

```powershell
catalyst deploy `
  -p 31210000000133001 `
  --org 50042142947 `
  --dc in `
  < NUL
```

Only the `--org` value changes. Build the client once; the same `app/dist/` ships to both environments. **Pre-flight checks before promoting**: read `04-deployment-runbook.md` in the maintenance section.

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
