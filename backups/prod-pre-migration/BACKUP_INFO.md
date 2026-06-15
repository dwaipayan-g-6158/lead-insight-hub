# Production Pre-Migration Backup

**Captured:** 2026-06-01 (before full Dev→Prod re-migration)
**Project:** lead-insight-hub `31210000000133001`
**Environment:** Production (env_zgid `50042142947`, env id `31210000000135001`)
**Org:** Emma `60066539659` | DC: IN

## Row counts at backup time

| Table | Table ID | Rows |
|-------|----------|------|
| leads | 31210000000141001 | 3 |
| user_roles | 31210000000143001 | 1 |
| lead_signals | 31210000000145001 | 27 |
| dossier_requests | 31210000000151002 | 2 |

These counts are the **floor** for post-migration verification — Prod must have ≥ these counts and the same key ROWIDs afterward.

## Key ROWIDs (must survive migration)

- leads: `37073000000027003` (Coppell/HOT), `37073000000033003` (Bellaire/WARM), `37073000000044002` (Chicago/WARM)
- user_roles: `37073000000027001` (admin, user_id `37073000000025005`)
- dossier_requests: `37073000000032001`, `37073000000041001`
- lead_signals: 27 rows tied to lead_ids `...027003`, `...033003`, `...044002`

## Restore procedure (if data lost)

Use MCP `Insert_Rows` into the respective table. **Pass all bigint values (ROWID, lead_id, user_id, CREATORID) as STRINGS** — Catalyst JSON number precision gotcha (17-digit IDs > 2^53 round off). Source data: the per-table `.json` files in this directory.
