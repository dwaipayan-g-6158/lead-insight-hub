# 01 — Change-Request Process

How proposed changes move from idea to production. The rulebook for non-emergency work. For incidents and emergency fixes, jump to [`06-incident-response.md`](./06-incident-response.md).

## When you need a CR

A change-request is required for anything that:

- Modifies code in `functions/` (any function) or `app/src/` (the SPA).
- Adds/drops/renames a Data Store column or table.
- Adds/rotates a secret in `catalyst-config.json`.
- Changes a Catalyst project setting (Auth, Mail, Stratus bucket config, Job Pool memory).
- Bumps the vendored `/eliss` skill version.
- Touches `catalyst.json` or `package.json` dependencies.

A CR is **not** required for:
- Documentation edits in `docs/` (commit directly with a clear message).
- README updates.
- Renaming a local branch.

## The CR template

Open an issue using this template (paste verbatim into your tracker; if no tracker is configured at the time of this baseline, use a markdown file in `docs/change-requests/YYYY-MM-DD-<slug>.md`):

```markdown
# CR-<short-slug> — <one-line title>

## Summary
What is changing and why (2-3 sentences max).

## Scope
- Files touched: `path/one.js`, `path/two.py`
- Data Store impact: yes/no
  - If yes: which tables/columns, additive vs destructive
- Env-var changes: yes/no
  - If yes: which vars, secrets vs config
- Catalyst project setting changes: yes/no

## Risk assessment
- Customer-visible: yes/no
- Reversible: yes/no
- Worst case if it goes wrong: <one sentence>

## Rollback plan
Specific steps to undo this change if production behavior degrades.
A "redeploy previous build" plan only counts when the prior build is
still in git and we can identify it by commit SHA or build artifact.

## Test plan
- Manual smoke tests to run before promoting to prod:
  - [ ] step 1
  - [ ] step 2
- Automated tests added/changed:
  - List file paths

## Approvers
- Owner: @<github-handle>
- Reviewer: @<github-handle>
- Production promoter (must differ from Owner for prod CRs): @<github-handle>
```

## Approval rules

| Change type | Approvers required |
| --- | --- |
| Doc-only | 0 (commit directly) |
| Code change, dev-only deploy | 1 reviewer |
| Code change, prod deploy | 1 reviewer + 1 different prod-promoter |
| Data Store schema change | 1 reviewer + 1 prod-promoter |
| Secret rotation | 1 reviewer (the owner handles the secret) |
| Catalyst project setting | 1 reviewer + 1 prod-promoter |
| Skill version bump | 1 reviewer (the skill itself is upstream-versioned) |

The "different prod-promoter" rule is the two-pairs-of-eyes safeguard. The CR author can be either the Owner or the Reviewer, but **not** the prod-promoter when promoting to production. Self-approval to prod is not permitted.

## Workflow

1. **Open the CR** with the template above. Fill every section; "N/A" is acceptable but explicit.
2. **Develop on a branch** named `cr/<slug>` (or your team's convention).
3. **Test locally**: `catalyst serve` for the function, `npm run dev` for the SPA. Run the manual smoke checks in your CR.
4. **Open a PR** (or push for review). Link the CR.
5. **Reviewer reads the diff** and runs at least one of the smoke checks. Comments inline; requests changes if needed.
6. **Merge to development** branch. The reviewer or author deploys to dev:
   ```powershell
   catalyst deploy -p 31210000000133001 --org 60066539659 --dc in < NUL
   ```
7. **Smoke-test in dev** (the URL is the dev environment's public domain). Watch for regressions in unrelated features.
8. **Promote to prod**: a *different* approver runs the equivalent command with `--org 50042142947`. They are the prod-promoter on record.
9. **Close the CR** when prod has been stable for ≥1 hour with no rollback. Note the commit SHA in the CR.

## What goes in the commit message

Tie commits to CRs so future debugging is fast:

```
fix(dossiers): include user_id in dedup query

CR-2026-05-23-dedup-leak

The old query matched dossier_requests rows globally instead of
per-user, so two users requesting the same prospect saw the wrong
job's status. Added WHERE user_id = $me to the dedup SELECT.

Reviewed-by: @reviewer
```

The CR slug as a body line lets `git log --grep` find the related history without a tracker.

## Emergency changes

Emergency = "production is degraded right now." Examples: a top-five error rate spike, customer-blocking 5xx, exposed secret.

Procedure:
1. **Open an incident** (see [`06-incident-response.md`](./06-incident-response.md)).
2. **Fix forward or revert** under the incident's authority. The two-pairs-of-eyes rule is suspended for emergencies — the on-call decides.
3. **File the CR retroactively** within 24 hours, marked `(emergency)` in the title, with the incident link in the Summary.

Emergencies are rare. If you find yourself filing more than one in a month, the system has a hygiene problem — escalate to the team retro.

## Cross-references

- The deploy commands the CR will execute → [`04-deployment-runbook.md`](./04-deployment-runbook.md)
- Testing depth expected per CR → [`03-testing-strategy.md`](./03-testing-strategy.md)
- Incident response (when a CR fails post-deploy) → [`06-incident-response.md`](./06-incident-response.md)
