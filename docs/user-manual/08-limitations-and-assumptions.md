# 08 — Limitations & Assumptions

Honest list of what the app can't do, what we assume about the environment, and what changes you might want to watch for in future releases.

## Hard limits

### Per-dossier limits

- **15-minute generation cap.** Catalyst Job Functions have a 15-minute hard timeout. Light dossiers finish well under this (~3-5 min). Heavy dossiers run 8-13 min and may approach the cap; if any individual research thread runs >10 min, the dossier may mark Partial because the parent runs out of time.
- **No PDF export.** The rendered HTML is the only output format. You can browser-print to PDF if needed.
- **No chained dossiers.** You can't say "research these 10 prospects in one batch" via a single button — each is a separate intake.

### RocketReach budget

- **~12-22 calls per dossier** (12 for light, 22 for heavy). At a typical monthly RR budget, this allows roughly **100-200 dossiers/month** before hitting the quota ceiling.
- **No firmographics for some orgs.** RR doesn't index every organization — `.gov`, `.edu`, smaller nonprofits, foreign-language orgs often return blanks. The system handles this gracefully (OSINT-only banner, Partial label) but you can't force-find data that isn't there.

### Anthropic budget

- **~6-10K input + ~4-6K output tokens** per light dossier. ~25-40K input + ~15-25K output for heavy.
- **Rate limits apply per-key.** During high-load periods, generations may pause briefly. Anthropic's status page is the source of truth for outages.

### Upload limits

- **6 MB per file** (Express body parser ceiling).
- **6 MB per ZIP**, ~50 files typical.
- **No CSV-only path.** HTML is the source format.

### Storage

- **Stratus signed URLs expire in 1 hour.** A page refresh gets a fresh URL.
- **No file versioning.** Stratus is configured without versioning at v1.0.0 — if a file is overwritten or deleted, the prior version is unrecoverable.

## Assumptions

The application assumes certain things about how it's deployed and operated. If any change, behavior may break:

### Catalyst environment

- **Single Catalyst DC: IN.** All URLs, integrations, and IDs are pinned to the India DC. Multi-DC deployment is not supported at v1.0.0.
- **Asia/Kolkata timezone.** All timestamps in the UI display in IST. If a user is in a different timezone, they'll see IST anyway — manual conversion needed.
- **Catalyst Native Auth is configured.** Self-signup, email confirmation, password resets all go through Catalyst.

### User identity

- **Real email addresses.** Catalyst sends confirmation emails. Disposable email services may or may not work depending on whether Catalyst's mail servers can deliver to them.
- **One account per email.** Catalyst rejects duplicate signups.

### Browser

- **Modern browsers only.** Chrome ≥ 100, Safari ≥ 17, Firefox ≥ 100, Edge ≥ 100. Older browsers may render incorrectly — Tailwind 3 + React 19 don't ship many polyfills.
- **JavaScript enabled.** It's a SPA — no JS, no app.
- **Cookies enabled.** Catalyst session cookies are required to authenticate.

### Network

- **The application URL is reachable.** Corporate firewalls that block `.catalystserverless.in` will make the app unreachable.
- **The Stratus subdomain is reachable.** `dossiers-development.zohostratus.in` (or the prod equivalent) must be reachable; the iframe loads from there.

## Things that look like bugs but are intentional

### Regenerate creates a new lead instead of updating

Old shared URLs remain valid. By design — explained in [Creating a dossier](./01-creating-a-dossier.md#regenerating-later) and [Managing leads](./03-managing-leads.md#regenerating-a-lead).

### Two users see different lead lists

Each user owns their own leads. By design — explained in [FAQ](./07-faq.md#can-two-people-see-the-same-lead).

### Admin can't see all users' leads in one list

Admin's **Leads** tab still shows only their own. To get cross-user counts, an admin needs to run ZCQL queries against the database directly (see [`05-admin-tasks.md`](./05-admin-tasks.md#aggregate-stats)).

### "Heavy" toggle requires 5 taps

Intentional friction so heavy mode isn't accidentally enabled.

### Sometimes dossiers say "Partial" instead of "Done"

Quality gates flagged thin sections; the dossier renders anyway with the gap acknowledged. By design — the alternative would be "fail outright on imperfect data" which throws away usable analysis.

## Backlog items (not in v1.0.0)

Things the team is considering for future releases:

| Feature | Why deferred |
| --- | --- |
| In-app diff between two versions of the same lead | Manual side-by-side works for now |
| Lead deletion for non-admins | Admins prefer the gate; revisit if it becomes a bottleneck |
| Bulk dossier generation (10 prospects in one submit) | Job Pool capacity limits — better as a feature when budget allows |
| Catalyst Pipelines CI/CD | Manual deploy is fine at current pace |
| Application-wide audit log (`audit_events` table) | No urgent need; manual investigation via existing tables works |
| Automated alerting on `/health` failure | Manual user-reports suffice at low volume |
| Multi-DC deployment | Single DC is enough until cross-region customer demand |
| Export structured lead data as CSV | Current need is HTML viewing, not data dumps |
| Custom scoring tunables | Score model is locked at v1.0.0; per-tenant tuning is a v2 conversation |
| Public status page | Internal channel is sufficient at current scale |
| Token-based invite flow | Self-signup works; invite is a polish item |

If you need any of these, raise it with the team and it'll go on the backlog.

## What we explicitly don't do

- **No CRM integration.** The dossier is an artifact — your CRM is where you record engagement.
- **No outreach sending.** The recommended emails are templates you copy and send from your own email client.
- **No call recording or note-taking inside the app.** Use your CRM, Gong, etc.
- **No team-level analytics or leaderboards.** This is an individual research tool, not a sales-management dashboard.

## When to come back to this page

Read it once now; bookmark it. The next time someone in your team says "wait, why does the app do X?" — check here first to confirm whether it's a bug or intentional.

## Cross-references

- The full scoring model → [Reading the dossier](./02-reading-the-dossier.md)
- The admin's view of constraints → [`05-admin-tasks.md`](./05-admin-tasks.md)
- The team's deferred features in detail → [`../changelog/lead-insight-hub-CHANGELOG.md`](../changelog/lead-insight-hub-CHANGELOG.md) — Known issues section.
