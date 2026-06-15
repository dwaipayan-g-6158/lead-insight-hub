# Prod Schema Baseline (pre-migration) + Dev→Prod drift

Captured 2026-06-01. Column counts per table BEFORE the full re-migration.

| Table | Table ID | Prod cols (pre) | Dev cols | Drift |
|-------|----------|-----------------|----------|-------|
| leads | 31210000000141001 | 37 | 38 | **Dev has `generation_engine`** (varchar(12), col `31210000000183045`, seq 38); Prod lacks it |
| user_roles | 31210000000143001 | 7 | (parity assumed) | none observed |
| lead_signals | 31210000000145001 | 9 | (parity assumed) | none observed |
| dossier_requests | 31210000000151002 | 22 | (parity assumed) | none observed |

## Prod `leads` columns (pre-migration, 37) — ends at:
- seq 36 `demo_playbook` (text, col 31210000000163052)
- seq 37 `opened_by_creator_at` (datetime, col 31210000000178020)
- **MISSING:** `generation_engine`

## Expected migration effect on schema
- Cloud Scale migration brings Prod → Dev schema. Expected: **add `generation_engine` (nullable varchar) to Prod `leads`**. This is additive/non-destructive — no existing column dropped or retyped.
- `lead_signals.lead_id` is a FK to `leads` with ON-DELETE-CASCADE (parent_column 37073000000021447). Migration must preserve this FK; verify post-migration that the 27 signals still resolve to their 3 leads.

## Post-migration schema check
Re-run `List_All_Columns` on all 4 Prod tables and confirm:
- [ ] `leads` now has 38 cols incl. `generation_engine`
- [ ] No column REMOVED vs this baseline (no data-type narrowing either)
- [ ] `lead_signals.lead_id` FK intact (ON-DELETE-CASCADE → parent leads)
- [ ] user_roles / dossier_requests column sets unchanged
