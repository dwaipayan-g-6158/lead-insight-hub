# Lead Insight Hub — Changelog

All notable changes to the Catalyst application. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [SemVer](https://semver.org/).

The `/eliss` skill ships its own changelog at [`ELISS-CHANGELOG.md`](./ELISS-CHANGELOG.md). When a row in the table below names a skill version, that's the version vendored at `functions/eliss-generator/skill/scripts/` and `functions/eliss-heavy-generator/skill/scripts/`.

---

## [Unreleased]

Items merged to the development branch but not yet promoted to production:

- _(none — all development work through 2026-06-17 is promoted; see [1.2.0])_

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
