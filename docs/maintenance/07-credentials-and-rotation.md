# 07 — Credentials & Rotation

Every secret the application depends on, where it lives, and how often it should be rotated. Single source of truth for the credential inventory.

## Inventory

| Secret | Required by | Stored in | Sensitivity | Rotation cadence |
| --- | --- | --- | --- | --- |
| `ANTHROPIC_API_KEY` | `eliss-generator`, `eliss-heavy-generator` | `catalyst-config.json` (per function) | High | 90 days |
| `ANTHROPIC_MODEL` | `eliss-generator` | same | Low (not a secret — model name) | N/A |
| `ANTHROPIC_SUBAGENT_MODEL`, `ANTHROPIC_PARENT_MODEL` | `eliss-heavy-generator` | same | Low | N/A |
| `RR_API_KEY` | both generators | same | High | 90 days |
| `OTX_API_KEY` | `eliss-heavy-generator` (optional) | same | Medium | 180 days if set; can be unset |
| `HIBP_API_KEY` | both generators (optional) | same | Medium | 180 days if set |
| `STRATUS_BUCKET` | all functions | each function's config | Low (config) | N/A |
| `SIGNED_URL_TTL_SECONDS` | `api` | `functions/api/catalyst-config.json` | Low (config) | N/A |
| Catalyst project credentials | local `catalyst login` session | `%APPDATA%\zcatalyst-cli-nodejs\Config\zcatalyst-cli.json` | High (full project access) | Per developer; revoke on offboarding |
| Catalyst user session cookies | browser, runtime | HttpOnly cookie | High | Catalyst-managed; users can sign out |

## The `catalyst-config.json` discipline

These two rules are mandatory and the source of most painful failures otherwise:

1. **All env vars live in `catalyst-config.json`.** That includes secrets, optional keys, and config values. Don't set anything in the Catalyst console UI — it will be wiped by the next `catalyst deploy`. The CLI uploads the JSON wholesale; whatever isn't in the file is gone.
2. **`catalyst-config.json` is gitignored.** Every function directory has a `catalyst-config.example.json` checked in with placeholder values. New developers copy and fill.

Per the top-five Catalyst gotcha from the `zoho-catalyst` skill.

### Per-environment configs

Production uses different secrets than development. The recommended pattern:

```
functions/eliss-generator/
├── catalyst-config.example.json   # checked in, placeholders
├── catalyst-config.dev.json       # gitignored, dev secrets
├── catalyst-config.prod.json      # gitignored, prod secrets
└── catalyst-config.json           # gitignored, COPY of dev or prod before deploy
```

Pre-deploy ritual:
```powershell
# Before any dev deploy:
Copy-Item catalyst-config.dev.json catalyst-config.json -Force

# Before any prod deploy (a different person, ideally):
Copy-Item catalyst-config.prod.json catalyst-config.json -Force
```

A small wrapper script can automate this — see `scripts/deploy-dev.ps1` (not yet checked in; backlog item).

## Rotation procedure

For each high-sensitivity secret (`ANTHROPIC_API_KEY`, `RR_API_KEY`), every 90 days:

### Step 1 — Generate new key at vendor

- **Anthropic:** [console.anthropic.com](https://console.anthropic.com) → API Keys → Create. Name it `lead-insight-hub-prod-YYYY-MM` so old keys are easy to spot.
- **RocketReach:** [rocketreach.co](https://rocketreach.co) → Account → API Settings → New Key.

Copy the new key immediately — vendors typically show it only once.

### Step 2 — Test the new key locally

Set the new key in a local `catalyst-config.local.json` and run a local function smoke. Confirm it authenticates correctly before deploying.

### Step 3 — Update `catalyst-config.dev.json` first

Drop the new key into the dev config. Deploy dev:
```powershell
Copy-Item catalyst-config.dev.json catalyst-config.json -Force
catalyst deploy --only functions:eliss-generator `
    -p 31210000000133001 --org 60066539659 --dc in < NUL
# repeat for eliss-heavy-generator
```

Generate one dossier in dev. If it works, you've validated the new key live.

### Step 4 — Update `catalyst-config.prod.json` and deploy prod

```powershell
Copy-Item catalyst-config.prod.json catalyst-config.json -Force
catalyst deploy --only functions:eliss-generator `
    -p 31210000000133001 --org 50042142947 --dc in < NUL
# repeat for eliss-heavy-generator
```

Generate one dossier in prod. Confirm it succeeds.

### Step 5 — Revoke old key at vendor

Only **after** prod runs cleanly on the new key. Revoking the old key while it's still in use kills in-flight requests.

### Step 6 — Log the rotation

Append to `docs/credentials-log.md` (not part of this baseline; create on first rotation):

```markdown
## 2026-08-22 — ANTHROPIC_API_KEY rotation
- Rotated by: @<handle>
- New key prefix: sk-ant-...XXXX
- Old key revoked at: <timestamp>
- Verification: dev dossier ID <id>, prod dossier ID <id>
- Next rotation due: 2026-11-22
```

Don't commit actual key values. The log is "what happened," not "what the values are."

## Rotation on offboarding

When a team member leaves:
1. **Revoke their Catalyst project access** (Console → Project Users → remove).
2. **Revoke their local `catalyst-cli` session** by removing their machine from any shared signing infrastructure.
3. **Rotate every shared secret** the leaver had access to. Same procedure as the 90-day rotation, but immediate.

The conservative posture is: any secret a leaver could have read is now compromised; rotate it.

## Lost or compromised key

If a key is exposed (committed to git, posted in logs, in a screenshot, leaked otherwise):

1. **Rotate immediately** (Steps 1-5 above, condensed to ~15 minutes).
2. **Revoke the exposed key at the vendor** without waiting for "validate first." Yes, this kills in-flight requests; recover them by retrying after the new key is live.
3. **File an incident** (see [`06-incident-response.md`](./06-incident-response.md)) with severity S1.
4. **Investigate the exposure path** — was it a git commit, a log line, a screenshot? Make the path harder to repeat.

## Vendor contracts (informational)

These aren't secrets, but they need annual review:

| Vendor | Account holder | Plan | Renewal date |
| --- | --- | --- | --- |
| Anthropic | _owner-managed — fill in_ | Direct API (Sonnet 4.6 access) | _owner-managed_ |
| RocketReach | _owner-managed — fill in_ | API tier — sufficient credits for ~30 dossiers/day | _owner-managed_ |
| AlienVault OTX | n/a | Free community tier | n/a |
| XposedOrNot | n/a | Free public endpoints | n/a |
| Catalyst | Owner | Development + production environment access | n/a (Zoho One bundle) |

The project owner replaces the `_owner-managed_` cells with concrete values when contract details are gathered. Keep this table sparse and accurate.

## Cross-references

- The `catalyst-config.json` overwrite gotcha → [`../architecture/08-catalyst-deployment.md`](../architecture/08-catalyst-deployment.md)
- Rollback procedure for a botched key rotation → [`05-rollback-procedures.md`](./05-rollback-procedures.md)
- Security incident response for exposure → [`06-incident-response.md`](./06-incident-response.md)
- Which integration each key authenticates → [`../architecture/07-integrations.md`](../architecture/07-integrations.md)
