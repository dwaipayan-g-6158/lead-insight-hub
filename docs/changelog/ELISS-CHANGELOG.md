# ELISS Skill — Changelog (as ported to Catalyst)

The upstream `/eliss` skill ships its own changelog at `C:\Users\dGiri\.claude\skills\eliss\CHANGELOG.md`. This file mirrors the entries that matter for the Catalyst port, annotated with **port status**:

- **PORTED** — vendored into `functions/eliss-generator/skill/scripts/` (and the heavy sibling); shipping in the current Catalyst app version.
- **DEFERRED** — skill change exists but not yet ported.
- **N/A** — change doesn't apply to the Catalyst port (e.g., a CLI-only feature).

The Catalyst app version that includes each port is named in parentheses. When the upstream skill releases, follow the procedure in [`../architecture/09-eliss-skill-explained.md`](../architecture/09-eliss-skill-explained.md) §"When to update the port".

---

## [7.4.2] — 2026-05-19 → **PORTED** (Catalyst app v1.0.0)

### Added — XposedOrNot preflight probe (free public endpoints, no API key)

`scripts/preflight.py` gains `probe_xposedornot()`. Three sub-calls against the free public XposedOrNot endpoints:

- `GET /v1/breaches?domain={domain}` — always runs.
- `GET /v1/check-email/{lead_email}` — fires only with `--lead-email`.
- `GET /v1/breach-analytics?email={lead_email}` — same gating.

New `summary` rollups: `xposedornot_domain_breach_count`, `xposedornot_lead_email_breach_count`, `xposedornot_yearly_breach_max`. Preflight now reports 11/11 probes.

**Catalyst notes:** Wired automatically since the generator passes `lead_email=intake.get("email")` to `preflight.run_preflight(...)`. No env var change required.

---

## [7.4.1] — 2026-05-19 → **PORTED** (Catalyst app v1.0.0)

### Added — AlienVault OTX preflight probe

`scripts/preflight.py` gains `probe_otx()` gated on the new `OTX_API_KEY` env var. Three sub-calls:

- `GET /api/v1/indicators/domain/{domain}/general` — pulse hits on prospect domain.
- `GET /api/v1/indicators/IPv4/{ip}/general` — pulse hits on resolved IPs.
- `GET /api/v1/search/pulses?q={industry}` — sector pulses (when `--industry` set).

**Catalyst notes:** `OTX_API_KEY` is wired in `eliss-heavy-generator/catalyst-config.example.json` but currently empty. Set it in `catalyst-config.json` to enable. The light generator does **not** currently expose `OTX_API_KEY` in its config example — add manually if needed. The `--industry` flag is not yet surfaced through the intake form; **partially DEFERRED**.

---

## [7.4.0] — 2026-05-12 → **PORTED** (Catalyst app v1.0.0)

### Added — Demo Playbook section (Tab 1 card + Tab 2 prose)

Every dossier can now ship a `demo_playbook{}` object that renders as a persona-anchored demo blueprint between the Competitive Threat Matrix and Signal Detail in Tab 1. Opening hook, 3 value moments per product (AD360 + Log360), discovery questions, top objections + responses, CTA.

**Catalyst notes:** Stored in `leads.demo_playbook` as a JSON-encoded text column. Renders automatically once the synthesis populates it.

### Changed — Email-template voices renamed (backwards-compatible)

`google → technical`, `apple → executive`, `microsoft → consultative`. `_LEGACY_VOICE_ALIASES` in the renderer resolves old voice keys.

### Added — 4 new outreach templates (library grows 9 → 13)

`hybrid_cloud_migration`, `audit_deadline`, `executive_briefing_offer`, `event_followup`. Slot 1 priority cascade rewritten in `references/outreach-playbook.md`.

---

## [7.3.0] — 2026-05-09 → **PORTED** (Catalyst app v1.0.0)

### Fixed — RR baseline now includes `Manager` in default management levels

Default `management_levels` changed from `["Director","VP","C-Suite"]` to `["Manager","Director","VP","C-Suite"]`. Surfaces Manager-level IT decision-makers at mid-market / public-sector orgs where the actual decider is sub-Director.

### Added — Path 2b surname-only `person_search` fallback

When `contact_name` matches `<initial> <Surname>` (e.g., `"P Mensah"`) and the strict Path 2 search misses, retry with surname-only. Handles compound/hyphenated surname truncation.

### Changed — Tab 2 inline URLs render as compact host-only pills

`.md-link` CSS rewritten to a rounded pill with truncated host label.

### Changed — Tab 2 RESEARCH SOURCES section auto-stripped

The renderer drops `## RESEARCH SOURCES` headings from `full_dossier_markdown` because Tab 1's Source Quality panel already covers the content.

---

## [7.2.1] — 2026-05-09 → **PORTED** (Catalyst app v1.0.0)

### Fixed — 8 bugs (renderer crashes, garbage rendering, doc drift)

- Hard crash in `main()` when `data.company.name` is a structured-value dict (now routed through `_extract_value()`).
- Five sites where dict repr leaked into HTML (`verdict banner`, `<title>`, `Employees` field, `Basis:` note, risk-flag rows).
- DMU map crash chain in `svg_dmu_ghost_map`, `svg_dmu_orgchart`, `svg_signal_timeline`.

### Added — Two previously-orphaned Tab 1 sections wired

- `org_intelligence.local_autonomy` now renders via `build_local_autonomy_card()`.
- `lead.personalization_hooks[]` now renders via `build_personalization_hooks_card()`.

**Catalyst notes:** Both new cards ship automatically once synthesis populates the fields.

---

## [7.2.0] — 2026-04-30 → **PORTED** (Catalyst app v1.0.0)

### Added — Recommended Outreach (3-email follow-up sequence)

`recommended_outreach[]` carries 3 dossier-driven emails (Slot 1 hard-rule, Slot 2 LLM-pick, Slot 3 always Breakup). Each in one of three voices (now `technical`/`executive`/`consultative`).

---

## [7.1.6] → [7.1.0] (2026-04-24 → 2026-04-23) → **PORTED** (Catalyst app v1.0.0)

The 7.1.x series introduced the RocketReach baseline enrichment pass on every path (`run_baseline_enrichment`), the multi-layer LinkedIn discovery retry ladder, depth-lint contact-verification gates, version stamp consistency across files. All ported via the standard vendor refresh.

### Catalyst-port adaptations

- The baseline pass runs **inside the generator's `_run_pipeline()`**, not inside subagent prompts. The light generator runs `max_bulk_profiles=10`; heavy runs `max_bulk_profiles=20`.
- The `--no-enrich` operator opt-out flag is not currently exposed; if you need to skip RR for a specific request, omit `RR_API_KEY` for that environment (currently treated as a hard failure — see DEFERRED below).
- The skill's "prior dossier within 30 days" skip-condition is **DEFERRED** — every Catalyst dispatch runs the full baseline.

---

## [7.0.x] — 2026-04 → **PORTED** (Catalyst app v1.0.0)

7.0 introduced the four-subagent parallel dispatch pattern. The Catalyst heavy generator implements the same pattern in Python via `asyncio.gather` over four Anthropic AsyncMessages calls. The Light generator runs the single-pass equivalent.

The skill's depth-lint warnings ship through the Catalyst port via the subprocess invocation of `generate_report.py` — `stderr` is parsed by `lib/depth_lint.py` to decide synthesis-retry (light) or partial-marking (heavy).

---

## Deferred features (not yet ported)

| Skill feature | Status | Notes |
| --- | --- | --- |
| `--industry` flag for OTX sector pulse | DEFERRED | Could be auto-derived from RR firmographics |
| PDF render via WeasyPrint | DEFERRED | HTML-only at v1.0.0; clients can browser-print to PDF |
| Skill-side `leads_log.json` registry | N/A | Catalyst Data Store replaces it |
| `--no-enrich` operator opt-out flag | DEFERRED | Workaround: temporarily unset `RR_API_KEY` |
| Skill-side rich CLI flags (`--cleanup-input-json` exception) | N/A | Catalyst tmpfs is per-execution |
| Auth-gated XposedOrNot domain breach endpoint | N/A | Public endpoint sufficient; per skill rationale |

When a deferred feature ships, move it from this table to a versioned heading above with status **PORTED**.

---

## How to use this file

When you bump the vendored scripts in `functions/eliss-generator/skill/scripts/`:

1. Find the upstream changelog entry for the new version at `C:\Users\dGiri\.claude\skills\eliss\CHANGELOG.md`.
2. Decide each line item's port status (PORTED / DEFERRED / N/A).
3. Add a new versioned heading at the top of this file with the same date as the upstream entry.
4. Briefly explain any Catalyst-specific adaptations (e.g., env var name differences, config file changes).
5. Bump `lib/store_lead.py::eliss_version` to match.
6. Update the **Vendored skill version** line in [`lead-insight-hub-CHANGELOG.md`](./lead-insight-hub-CHANGELOG.md) under the matching app version.

The upstream changelog format is verbose; this mirror should be terser — focus on what changed in the *behavior the user sees* and what the *Catalyst port adapts*.
