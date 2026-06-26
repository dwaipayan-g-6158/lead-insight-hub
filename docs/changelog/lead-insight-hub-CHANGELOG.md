# Lead Insight Hub — Changelog

All notable changes to the Catalyst application. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [SemVer](https://semver.org/).

The `/eliss` skill ships its own changelog at [`ELISS-CHANGELOG.md`](./ELISS-CHANGELOG.md). When a row in the table below names a skill version, that's the version vendored at `functions/eliss-generator/skill/scripts/` and `functions/eliss-heavy-generator/skill/scripts/`.

---

## [Unreleased]

Items merged to the development branch but not yet promoted to production:

### Changed

- **Whole-row click on the Leads page.** Clicking **anywhere** in a desktop leads-table row now opens that lead's dossier, not just the prospect-name link. The lead name stays a real `<a>`, so keyboard focus, middle-click and "open in new tab" still work; clicks on an inner link/button, modifier-clicks (Ctrl/Cmd/Shift/Alt), and active text selections are ignored so none of those get hijacked. The mobile card list was already fully clickable — unchanged. (`app/src/components/LeadsListPage.tsx`)

---

## [1.5.0] — 2026-06-26

Development work promoted to Production via the Catalyst **console deployment wizard** (deploy `31210000000296130`, Development → Production, fully additive — **2 entities**: 1 function updated (`api`) + web client updated; **zero schema/data changes, no new tables/columns, no auth gate**). The pre-deploy diff confirmed Data Store, NoSQL, File Store, Stratus, Cron, Job Pool, API Gateway, Cache, Mobile-app settings, and every authentication component at **Total Changes: 0**. All 25 components completed with empty error logs. Promotion is console-wizard only — there is no CLI path to Production (see [`../architecture/08-catalyst-deployment.md`](../architecture/08-catalyst-deployment.md)).

### Added

- **On-demand PDF export.** Lead dossiers now download as a single, professionally formatted **PDF** instead of raw HTML. The PDF is rendered on demand from the stored dossier HTML via Catalyst **SmartBrowz** (headless Chromium), so it is faithful to the report's existing `@media print` CSS (white background, page breaks, branding). The first render is cached to Stratus under `pdf/<leadId>.pdf` and reused on subsequent downloads (~250 ms cache hit vs ~10 s cold render). New route **`GET /leads/:id/pdf`** (auth + id validation mirroring `GET /:id`), streamed as `application/pdf` with a `Content-Disposition` attachment filename. The download button shows a spinner / "Preparing PDF…" state while rendering. Files: `functions/api/routes/leads.js`, `functions/api/lib/stratus.js` (new `getObjectBuffer`/`putBuffer`/`streamToBuffer` helpers), `app/src/lib/api.ts` (`fetchLeadPdf`), `app/src/components/LeadDetailPage.tsx`.
- **Dossier-completion feedback.** When a dossier reaches `succeeded`, the activity popup now fires a coordinated set of completion signals so a backgrounded 2–3 min job is unmissable: a CSS **confetti** burst, an **animated drawn checkmark** in the success toast, a one-shot glow/**pulse on the activity pill**, plus two **per-user opt-in** alerts — a Web-Audio **success chime** and a **desktop/OS notification** (only when the tab is hidden) — toggled from the account menu under "Completion alerts". All motion respects `prefers-reduced-motion`; sound and notifications default **off** and persist in `localStorage`. New: `app/src/components/ConfettiBurst.tsx`, `app/src/components/AnimatedCheck.tsx`, `app/src/lib/notify.ts`. Touched: `DossierActivityPopup.tsx`, `AppShell.tsx`, `styles.css`.
- **Consistent page headers.** A new shared **`PageHeader`** component (uppercase eyebrow + route icon + title + description + optional right-aligned `aside`) is applied across **Leads, Upload, Settings, Audit, Admin and Dashboard**, so every page header is structurally identical (previously Leads/Upload/Settings had a bare `<h1>`, Audit had an icon, and only Admin had the full eyebrow+icon treatment). New: `app/src/components/PageHeader.tsx`.

### Fixed

- **"Last seen" now tracked for every user.** `loadRole` (`functions/api/lib/auth.js`) previously created a `user_roles` row only for Catalyst platform admins, so users created in the console (who have no row and never went through the app signup flow) never had `last_seen_at` stamped — they showed "—" forever in User management. It now seeds a row for **any** authenticated row-less user (role taken from the platform grant — `admin` only if the platform itself grants it, otherwise `user`; no privilege escalation) and stamps `last_seen_at` on the same insert. Forward-looking: affected users populate on their next login (prior activity can't be backfilled).
- **Settings page width alignment.** The Generation-settings page content now spans the same full container width as every other page; it was constrained to `max-w-4xl`, leaving it visibly narrower/misaligned against Leads/Audit/Admin.

---

## [1.4.0] — 2026-06-24

Development work promoted to Production via the Catalyst **console deployment wizard** (deploy `31210000000299035`, Development → Production, fully additive — **2 entities**: 1 function updated (`api`) + web client updated; **zero schema/data changes, no new tables/columns, no auth gate**). The pre-deploy diff confirmed Data Store, Stratus, Cron, Job Scheduling, and every authentication component at **Total Changes: 0**. See [`../architecture/08-catalyst-deployment.md`](../architecture/08-catalyst-deployment.md) §"Deployment history".

### Added

- **Interactive Audit KPI cards.** The four summary tiles on the `/audit` page — *Events today*, *Active users*, *Dossiers today*, *Searches today* — are now clickable. Each opens a drill-down popup (desktop **Dialog** / mobile **Drawer**, switched on `useIsMobile()`) that lists the exact rows behind the number:
  - *Events / Dossiers / Searches* render the underlying audit-event list (the same row renderer as the main feed).
  - *Active users* renders a per-user roster — name, email, event count, last-activity, and a per-type breakdown.
  - New backend route **`GET /audit/drilldown?card=events|active_users|dossiers|searches`** (`functions/api/routes/audit.js`), gated by the same `requireAdminOrSuperAdmin` middleware as the rest of `/audit`. It **reproduces `GET /audit/summary`'s exact rolling-24h window test** so every drill-down's count matches its card number exactly. Read-only — no new persistence, no schema change.
- **Drill-down "fly-to-card" close animation.** Closing a drill-down popup minimizes it back into the exact KPI card that opened it (and emerges from that card on open), reusing the `flyTarget` FLIP mechanism (`DialogContent` + the `.dialog-fly` keyframes in `styles.css`) first shipped for the reset-password dialog in [1.1.0]. Each tile carries a `data-kpi="<card>"` attribute so the dialog can target the specific clicked card; the displayed card is retained through the close so the fly-out animation keeps its target. Respects `prefers-reduced-motion` (collapses to an instant cut).

### Changed

- **Audit page refactor.** Shared event-row rendering — the responsive table / mobile-card list plus its `TYPE_META`, `FILTERS`, `relTime`, `absTime`, `initialsOf`, and `describe` helpers — was extracted from `AuditPage.tsx` into a new `AuditEventList.tsx`, so the main audit feed and the new drill-down popups render rows identically. No behavior change to the existing feed.

**Files:** `functions/api/routes/audit.js`; `app/src/components/{AuditPage,AuditDrilldownDialog,AuditEventList}.tsx`; `app/src/lib/api.ts`; `app/src/types/audit.ts`.

---

## [1.3.0] — 2026-06-23

Development work promoted to Production via the Catalyst **console deployment wizard** (deploy `31210000000280326`, Development → Production, fully additive — **20 entities**: 1 table + 14 columns added, 4 functions updated, web client updated; **zero deletions, zero row-data changes, no auth gate**). All 25 components completed with empty error logs. See [`../architecture/08-catalyst-deployment.md`](../architecture/08-catalyst-deployment.md) §"Deployment history".

> The function-level fixes below (timezone, renderer hardening, None-safety) were first hotfixed to prod on 2026-06-18 (Serverless-only deploy `31210000000260137`, never changelogged); this release records them and ships the audit feature (table + UI) that was built on Dev afterwards.

### Added

- **Org-wide Audit Report.** A new `audit_events` Data Store table (GLOBAL scope, append-only, **120-day retention**) and `/audit` web page (admin + super-admin only) that logs every authenticated user's logins, dossier creations, lead searches, lead views, and admin actions. Writes are **fire-and-forget** (`functions/api/lib/audit.js`) so a logging failure never breaks a user action; reads are served by `GET /audit` + `GET /audit/summary`, both gated by the new `requireAdminOrSuperAdmin` middleware. Dossier-status is enriched live at read time (not stored on the event). See `functions/api/routes/audit.js`, `app/src/components/AuditPage.tsx`, and [`../architecture/06-data-model.md`](../architecture/06-data-model.md).
  - `POST /me/session-start` — login beacon, fired once per browser session (client `sessionStorage`-gated). Every user generates events; only admins read the log.
  - Search typing-burst collapse — a leads search like `z → zo → zohocorp` coalesces into a single audit row (12-second session window); lead views dedup per user+lead (60s).
  - 120-day retention enforced by `functions/dossier-sweeper` on every 5-minute sweep (batched hard-delete, non-blocking).

### Changed

- **Critical timezone fix.** Catalyst system columns `CREATEDTIME` / `MODIFIEDTIME` are emitted in the project timezone (Asia/Kolkata, **+05:30**), not UTC. The original code appended `"Z"`, shifting timestamps +5.5h into the future so the staleness gate always evaluated true and the dossier sweep broke on the first row. Fixed in `functions/api/routes/dossiers.js` **and** `functions/dossier-sweeper/index.js` by appending the `+05:30` offset — the two **must stay in sync**.
- **Dossier-sweeper double-duty** — in addition to resuming stale dossiers, it now purges `audit_events` older than 120 days each sweep (idempotent, non-blocking).
- **Generator hardening (Light + Heavy)** — the renderer-crash handler now unconditionally patches the row to `status=failed` (previously left at `running` forever); new `_sanitize_name()` strips HTML tags and control characters from intake names before synthesis/render (defense against injection like `<img src=x onerror=...>`).
- **Synthesis None-safety** in `generate_report.py` (both forks) — null source URLs, peer-score null checks, and the SVG DMU ghost-map name comparison now coerce `None → ''` instead of crashing `.strip()` / `len()` on degraded (rr_degraded / OSINT-only) synthesis paths.
- **Reference cleanup** — removed external book-page citations (`(book p72)`, `(Ch5)`, …) from the generated dossier schema/template so the schema is the single source of truth for synthesis.

### Fixed

- Orphaned dossier rows hung at `running` forever after a renderer crash → now marked `failed`.
- Renderer crashes on adversarial lead names containing markup/control characters → now sanitized.
- Missing/null source links in degraded synthesis → skipped gracefully instead of crashing the render.

---

## [1.2.1] — 2026-06-17

Patch promoted to Production via the Catalyst console wizard (deploy `31210000000260051`, Development → Production — `api` + `dossier-sweeper` functions updated, `dossier_sweeper_cron` re-enabled; no schema/data change, no auth gate).

### Fixed

- **Stale-sweep no longer resurrects abandoned dossiers.** Both the global `dossier_sweeper_cron` and the per-user inline `sweepStaleRunning()` (`functions/api/routes/dossiers.js`) resumed **any** stale `running`/`pending` row that had a checkpoint, regardless of how old it was — so right after `1.2.0` enabled the global cron in prod, it auto-resumed a 4-day-old abandoned Heavy dossier (re-spending Anthropic/RocketReach credits nobody requested). Added a **`CREATEDTIME`-based age guard**: a stale row created longer ago than `sweep_resume_max_age_min` (new setting, default **180 min**) is marked `failed` (cleanup) instead of resumed. Fail-closed on an unparseable/missing creation time. The two sweeps are kept in sync.

### Added

- **`sweep_resume_max_age_min`** generation setting (shared / operational, default 180, range 15–1440) in `functions/api/lib/generation-settings.schema.json`, so the super-admin panel can tune the resume age window without a redeploy.

> Operational note: between `1.2.0` and this patch the prod `dossier_sweeper_cron` was temporarily disabled to stop the resurrection behavior; this deploy re-enabled it now that the guard is in place.

---

## [1.2.0] — 2026-06-17

Development work promoted to Production via the Catalyst **console deployment wizard** (deploy `31210000000260040`, Development → Production, fully additive — **4 entities**: 1 function added, 1 function updated, 1 cron added, web client updated; **zero schema/data changes, no auth gate**, `api` and `eliss-heavy-generator` untouched). See [`../architecture/08-catalyst-deployment.md`](../architecture/08-catalyst-deployment.md) §"Deployment history".

### Added

- **`dossier-sweeper`** — a new always-on, engine-agnostic Catalyst **Job Function** (Node 18, 256 MB) driven by the **`dossier_sweeper_cron`** pre-defined cron (every 5 min). It is the global twin of the user-scoped inline `sweepStaleRunning()` in `functions/api/routes/dossiers.js`: it scans **all** users' `dossier_requests` for rows stuck `pending`/`running` past the 15-min staleness window and either resumes them from their Stratus checkpoint (when `checkpoint_ready` + a `resume_target` + attempts remain) or marks them `failed`. Guarantees recovery even when the request owner never re-opens the app (e.g. a mobile request backgrounded after an OOM in the render tail). Reads `ELISS_GEN_JOBPOOL_ID` — set **Production-scoped** in the console post-migration (the migration ships code only, not runtime env). Added to `catalyst.json` `functions.targets`.

### Changed

- **Light generator self-dispatch resume parity with Heavy** (`functions/eliss-generator/main.py`). Light previously had no proactive self-dispatch and relied entirely on an external sweep to recover after a kill. Added `_get_resume_attempts` + `_dispatch_resume` (ported from Heavy) and a post-checkpoint time-budget guard: if synthesis exceeds `light_render_deadline_s` (default 720s of the 900s Job budget), the kill-prone render tail is deferred to a fresh resume Job that re-renders from the Stratus checkpoint (zero re-spent tokens). Guarded by `auto_resume` + the deadline, so fast runs are unchanged.
- **Web client refresh (1.0.0 rebuild).** iOS PWA login-zoom fix (`login-iframe.css` cache-bust `v=35`; inputs 14px→16px + `text-size-adjust`), mobile bottom-sheet navigation (`MobileNavSheet`), mobile dossier status pill, `EngineBadge` (Heavy/Light/Imported indicator), `AppShell` rewrite, and dialog FLIP animations.

> The Heavy sharded-synthesis pipeline, the `api` generation-settings endpoints, and all DataStore schema were already in Production prior to this release (promoted in [1.1.0] / earlier); the Dev→Prod diff confirmed `api` and `eliss-heavy-generator` as unchanged.

---

## [1.1.0] — 2026-06-13

Development work promoted to Production via the Catalyst **console deployment wizard** (deploy `31210000000235055`, Development → Production, fully additive — 3 functions + web client updated, 1 table + 10 columns added (15 entities total), zero deletions, no row-data changes). See [`../architecture/08-catalyst-deployment.md`](../architecture/08-catalyst-deployment.md) §"Promote to production" for the (corrected) mechanism.

### Added

- **Super-admin Generation Settings panel** (`/settings`, gated by `SUPER_ADMIN_EMAIL`, not by role). Tunes every ELISS Light/Heavy lever live — no redeploy. Backed by the new `app_settings` singleton table; both generators read it at job start via `lib/app_settings.load_settings()`. The React panel fetches the schema from `GET /admin/settings` at runtime, so adding a setting needs **no client rebuild**. Canonical schema: `functions/api/lib/generation-settings.schema.json`.
- **Tier-aware soft-warning tolerance** — two settings `light_lint_soft_tolerance` / `heavy_lint_soft_tolerance` (int, default **4**, range 0–20). HOT/WARM stay strict (tolerance 0 → any empty cell warns); COLD/COOL tolerate up to the configured number of isolated empty cells before a dossier is marked `partial`.
- **Checkpoint-and-resume** for the generation pipeline. New `dossier_requests` columns `resume_attempts` (int), `checkpoint_ready` (boolean), `resume_target` (varchar). Expensive synthesis output is persisted to Stratus before the kill-prone render tail; a stale-sweep auto-dispatches a resume job that finishes from the checkpoint.
- **`leads.generation_engine`** column + admin-only Heavy/Light/Imported pill (distinct from `eliss_version`, which is the skill version).
- **Source-quality backfill** in `generate_report.py` (`_backfill_sources_from_markdown`) — when structured `sources` comes back empty, the renderer salvages cited URLs from the narrative (tier markers `[A]/[B]/[C]` or domain heuristic) so the Source Quality donut populates instead of showing "No sources cited".
- **Minimize-to-pill / reset-password dialog animations** — an opt-in `flyTarget` prop on `DialogContent` runs a FLIP that collapses the dialog toward its top-right target (the Dossier-Requests pill, or the account-menu trigger for the reset dialog). CSS `@keyframes dialog-fly-in/out` in `styles.css`.

### Changed

- **`depth_lint.py` reworked into HARD vs SOFT literal classes.** HARD = section-level failures (`No executive brief`, `No applicable frameworks`, `No sources cited`); SOFT = isolated empty cells (`Unknown`, em-dash heatmap cell, `None detected`, empty waterfall). The terminal `partial` decision is now `hard_total > 0 OR rr_degraded [OR fanout_partial] OR soft_hits > tier_tolerance`.
- **Environment-aware `catalyst-client.ts`** — detects `.development.` in the hostname to pick the dev vs prod ZAID (`50042142947`), org id, and Stratus domain. One build serves both environments.

### Fixed

- **Empty Source Quality donut** on dossiers whose structured `sources` array came back empty — fixed by the backfill above, plus `No sources cited` is now an **always-blocking** lint literal (regenerate at any tier; a zero-citation dossier is unshippable regardless of lead value).
- **Reset-password dialog close animation** jumped ~half its width to the left — Tailwind v4 emits `translate-x/y` as the CSS `translate` *property*, so the keyframes must not re-apply `translate(-50%,-50%)`.

---

## [1.0.0] — 2026-05-22

First labeled release. Everything shipped to date is rolled into this baseline. Prior states existed only on the development branch and are pre-1.0 by definition.

### Application surface (frontend + API)

- **Vite + React 19 + TypeScript SPA** under `app/`, deployed via Catalyst Web Client Hosting (`client.source = app/dist`).
- **TanStack Router** with auto code-splitting; routes at `/`, `/leads`, `/leads/:leadId`, `/upload`, `/admin`, `/signup`.
- **shadcn/ui** primitives (Radix + Tailwind) for all interactive components.
- **Sonner** toasts and **Recharts** for the dashboard score visualizations.
- **Express on Node 18** API Function at `functions/api/` with seven route files: `signup, auth, me, leads, dossiers, stats, admin`.
- Middleware stack: `attachCatalyst → requireUser → loadRole → requireAdmin`.
- Lib helpers: `auth, db (paginated ZCQL), stratus, parser, storeDossier, featureFlags, mailer`.
- Self-signup at `POST /auth/signup` (the only public route).
- `BUILD_ID = "2026-05-21-self-signup"` surfaced at `GET /health`.

### Dossier engines

- **`eliss-generator`** (Python 3.9 Job Function, 512 MB / 900 s) — light variant. Seven-stage pipeline: `queued → preflight → rocketreach → synthesis → rendering → lint → upload`. Synthesis-retry on blocking lint hits.
- **`eliss-heavy-generator`** (Python 3.9, 3072 MB / 900 s) — heavy variant. Inserts a `fanout` stage between `rocketreach` and `synthesis`; uses `asyncio.gather` over four Anthropic subagents (Tech / Compliance / Org / Behavioral) plus a parent consolidation call. No retry on blocking lint — marks dossier `partial` instead.
- Both functions share the `elissgenpool` Job Pool (memory ceiling 1536 MB) and a common vendored `skill/scripts/` directory carrying the upstream `/eliss` v7.4.x scripts.
- **RocketReach baseline enrichment** runs on every path when `RR_API_KEY` is set. Coverage gaps surface as `rr_degraded=true` + an inline OSINT-only banner in the rendered HTML; the dossier is still produced and marked `partial`.

### Data model

Four Catalyst Data Store tables, all in the project's SINGLE_DB schema:

| Table | Purpose | Notable |
| --- | --- | --- |
| `leads` (36 cols) | Scored dossier output. | Composite + 4-dimension scoring columns. `tier`, `composite_score`, `email` indexed. |
| `lead_signals` (9 cols) | Per-lead buying signals. | FK to `leads.ROWID` with `ON DELETE CASCADE`. |
| `user_roles` (7 cols) | Application RBAC. | `user_id` unique; `role IN ('admin','user')`. |
| `dossier_requests` (22 cols) | Async job state machine. | `lead_id` FK stored as **string** (bigint precision). `rr_degraded`, `rr_degradation_reason` for coverage banner. |

Regenerate always creates a NEW `leads` row — old dossier URLs continue to render the frozen snapshot.

### Storage

- **Stratus bucket `dossiers`** (created 2026-05-12, no versioning, no encryption, no audit in dev). Keys: `dossiers/<user_id>/ELISS_<Company>_<Last>_<YYYY-MM-DD>.html`.
- Pre-signed GET URLs with a 1-hour TTL (`SIGNED_URL_TTL_SECONDS=3600`).

### Integrations

- Anthropic Claude (Sonnet 4.6) via `anthropic` Python SDK. Direct API only — no OpenRouter relay.
- RocketReach v2 — 8 endpoints, ~12-22 person_export per dossier (light vs heavy).
- AlienVault OTX — optional, gated on `OTX_API_KEY`.
- XposedOrNot — free public endpoints, always on.
- HaveIBeenPwned — optional, gated on `HIBP_API_KEY`.
- Catalyst Native Auth — session cookies, signup email, password reset.
- Catalyst Mail — transactional emails via `mailer.js`.

### Environments

- **Development** (env `60066539659`) — active, used by the team.
- **Production** (env `50042142947`) — created, default-active for the project. No customer traffic yet at this baseline.

### Project metadata

- Project ID `31210000000133001`, ZAID `50042133518`, DC `in`, Timezone `Asia/Kolkata`.
- 5 project users at baseline: 1 App Administrator (`iaminzoho@gmail.com`), 3 active App Users, 1 unconfirmed (`admin@example.com`).

### Vendored skill version

`/eliss` v7.4.2 — XposedOrNot probe added; baseline `--lead-email` flag wired. See [`ELISS-CHANGELOG.md`](./ELISS-CHANGELOG.md) for the upstream entry.

### Known issues / followups

Tracked in `qa-audit-2026-05-15/FOLLOWUPS.md`:
- Mobile responsive fixes (sticky positioning, sheet close, verdict headline truncation) — **resolved** as of 2026-05-15.
- No dedicated audit-events table — accepted at v1.0.0; revisit when admin actions need a queryable history.
- Heavy generator declared memory (3072 MB) exceeds pool ceiling (1536 MB); function runs at the ceiling. Bump pool memory in production if observed OOM rates exceed 5%.
- No CI/CD pipeline (`catalyst-pipelines.yaml` absent). All deploys are manual.

### Upgrade notes

There is no upgrade path from a pre-1.0 state because pre-1.0 wasn't versioned. Anyone running an older commit:

1. Verify `catalyst.json` matches the v1.0.0 shape (three function targets, `app/dist` as client source).
2. Confirm all four Data Store tables exist (`leads`, `lead_signals`, `user_roles`, `dossier_requests`). If `dossier_requests` is missing, create it manually from the schema in [`../architecture/06-data-model.md`](../architecture/06-data-model.md).
3. Rotate `ANTHROPIC_API_KEY` and `RR_API_KEY` per [`../maintenance/07-credentials-and-rotation.md`](../maintenance/07-credentials-and-rotation.md).
4. Deploy via the non-interactive command in [`../maintenance/04-deployment-runbook.md`](../maintenance/04-deployment-runbook.md).

---

## How entries are written

For every release going forward, add a new section at the top of [Unreleased] and move it to a versioned heading on cut. Each section should carry these subheadings (in this order, omitting any that don't apply):

- **Added** — new features visible to users.
- **Changed** — modifications to existing behavior.
- **Deprecated** — features marked for removal.
- **Removed** — features deleted.
- **Fixed** — bug fixes.
- **Security** — vulnerability patches or policy changes.

Reference commits, PR numbers, or upstream skill versions where useful. The goal is that a reader returning after 6 months can reconstruct what shipped and why.
