# ELISS Heavy — Sharded Parallel Synthesis (raise the 900s richness ceiling)

**Date:** 2026-06-11
**Status:** Design — pending review
**Scope:** `functions/eliss-heavy-generator` only. Light (`eliss-generator`) is out of scope (single web-search call, not decomposable the same way).

---

## 1. Problem & measured justification

Catalyst Job Pools hard-kill at **900s**. The heavy pipeline runs
`preflight → rocketreach → fanout (4 parallel subagents) → parent synthesis → render → lint → upload`
inside one job. Fanout is already parallel and checkpointed. The **parent synthesis is a single
serial `messages.stream` call** that emits the entire dossier JSON — and it is the wall-clock wall.

Checkpoint-and-resume (already shipped) makes a ceiling hit *non-destructive* (fan-out tokens are
saved, a resume job continues), but it **cannot raise the ceiling**: a resume job is still one 900s
job running that same serial parent call. So it does not enable richer dossiers.

**Benchmark (2026-06-11, production-bound account, `claude-sonnet-4-6`, isolated parent-shaped call):**

| metric | value |
|---|---|
| output throughput | **46.2 tokens/sec** |
| 27,042-token dossier | **585.6s** (parent-only, `end_turn`) |

Real single-job math (900s ceiling): fanout ~90–120s runs *before* the parent, render/upload ~40–60s
*after*, and a depth-lint retry re-runs the **entire** parent. Result:

| dossier output | parent @46.2 t/s | + fanout + render | fits 900s? | survives 1 lint retry? |
|---|---|---|---|---|
| 27K (≈ today) | 585s | ~700–725s | barely | **no** |
| 30K | 650s | ~770–790s | no margin | no |
| 36K (richer) | 780s | ~870s+ | **no** | no |
| 45K+ (goal) | 975s+ | — | **no** | no |

**Conclusion:** richer dossiers do not fit one job at this throughput. Parallelizing the *output*
is the only lever that moves the wall. This is that work.

---

## 2. Approach: spine → parallel shards → narrative reduce → deterministic merge

Replace the one `run_parent_only` call with a map-reduce over the same checkpointed fragments:

```
fragments (from fanout, already checkpointed)
   │
   ▼
[SPINE]      one serial call. Reads all fragments. Emits the coherence-critical
             core (scoring, executive_brief, meta). Small output (~2–4K tok).
             Establishes the prompt cache (§4) for the shards.
   │
   ▼
[SHARDS]     N parallel calls (asyncio.gather, AsyncAnthropic — reuse the fanout
             pattern). Each reads the SAME cached fragment prefix + the spine
             output, and emits ONLY its disjoint slice of dossier keys.
   │
   ▼
[NARRATIVE]  one serial reduce. Receives the fully-assembled structured dossier,
             emits full_dossier_markdown (8–15K-char prose). Guarantees the
             prose matches the merged structured fields.
   │
   ▼
[MERGE]      pure-Python dict merge. Spine is the base; each shard owns DISJOINT
             top-level keys, so merge = base.update(shard) per shard. No LLM
             reconciliation call. Then narrative markdown attached, then the
             existing _apply_rr_company_enrichment safety net.
   │
   ▼
render → lint → upload   (unchanged renderer contract)
```

**Why spine-first (the coherence model approved in brainstorming):** scoring/tier/exec-brief depend
on the whole picture, so they cannot live in a shard blind to the others. The spine computes them
first and passes `scoring.tier` into every shard, so tier-gated content (HOT timeline, scenarios,
discovery_anchors) stays consistent. Because the spine owns the verdict and shards own disjoint
detail keys, the merge needs no reconciliation.

### Wall-clock projection (46.2 t/s, 6 shards)

A 36K-token richer dossier, sharded: spine ~3K (≈65s) + max-shard ~7K (≈150s, parallel) +
narrative ~4K (≈90s) ≈ **~305s effective**, vs 780s serial. Leaves ample headroom under 900s for
fanout, render, *and* a lint retry.

---

## 3. Shard map (disjoint top-level key ownership)

Every dossier top-level key is owned by exactly one producer. This table IS the contract — the
renderer reads these key names verbatim; a key produced by two shards is a bug.

| Producer | Owns |
|---|---|
| **Spine** (serial) | `meta`, `scoring`, `executive_brief` |
| **shard_org** | `lead`, `company`, `org_intelligence` |
| **shard_tech** | `technology` |
| **shard_compliance** | `compliance`, `budget_analysis` |
| **shard_signals** | `signals`, `pre_mortem`, `rep_readiness_checklist` |
| **shard_playbook** | `demo_playbook`, `recommendations`, `recommended_outreach` |
| **shard_momtest** | `data` (Mom Test block), `data_quality`, `sources` |
| **Narrative** (serial reduce) | `full_dossier_markdown` |

Each shard's prompt embeds **only its slice** of `REQUIRED_DOSSIER_SHAPE` plus the relevant Rules
from `build_parent_synthesis_messages` (e.g. shard_compliance keeps Rule 4's `ad360_angle`/
`log360_angle` naming; shard_org keeps the FLAT-DMU rule). This keeps each call focused and small.

**`data` block sub-ownership note:** the schema places `data.deal_premortem` etc. all under one
`data` key — shard_momtest owns the entire `data` key. The spine does NOT emit `data`. No overlap.

---

## 4. Prompt caching — the input-cost control

Sharding re-reads the fragments per shard. Without caching that multiplies input cost ~8×. Mitigation:

- Build a **shared cacheable prefix** = `[system_prompt block, inputs-payload block]` where the
  inputs payload = `{intake, preflight, rr_baseline, subagent_fragments, rr_degraded, …}` (the same
  block `build_parent_synthesis_messages` builds today). Put `cache_control: ephemeral` on the last
  prefix block.
- The **per-call instruction** (spine vs each shard vs narrative) is a **separate trailing block**
  after the cached breakpoint. Caching is prefix-based, so all calls share the cached prefix and
  differ only in the cheap suffix.
- **Ordering matters:** the spine runs first and *creates* the cache (`cache_creation`). The shards
  fire after the spine returns and within the 5-min TTL → they get `cache_read` (~0.1× input cost).
  Document this dependency in code: shards must not start before the spine completes.

Net: input paid ~once at full price + cheap reads thereafter. Output rises modestly (spine
duplication + per-shard JSON envelope + narrative) — accepted per the goal ("raise the ceiling,
accept higher input cost"). This is a token *trade*, not waste.

---

## 5. New modules & changed files

- **`lib/synthesis_shards.py` (new)** — the orchestrator:
  - `SHARD_SPECS` — list of `{key, owns:[...], schema_excerpt, rules_excerpt}`.
  - `build_spine_messages(...)`, `build_shard_messages(spec, spine, ...)`,
    `build_narrative_messages(assembled, ...)` — all using the cached-prefix structure (§4).
  - `run_sharded_synthesis(fragments, intake, preflight, rr_baseline, *, settings, log, on_stage)`
    → returns `(dossier_dict, usage)` with the **same shape** `run_parent_only` returns today, so
    `_finalize` is unchanged. Internally: spine (sync) → `asyncio.run(_shards_async(...))` (gather,
    per-shard `asyncio.wait_for`) → narrative (sync) → merge.
  - Reuse `_extract_json_obj`, `_join_text_blocks`, `_accumulate_usage`, truncation guard
    (`stop_reason == "max_tokens"` → raise) from `fanout.py` — import, don't duplicate.
  - Partial tolerance: a shard that fails/times out → that key-set is **absent** from the merge;
    `_apply_rr_company_enrichment` + renderer empty-state handling cover gaps; the dossier surfaces
    `partial` (same UX as a missing subagent). The spine and narrative are **required** — failure of
    either falls back (§6) or fails the request.
- **`lib/prompts.py`** — factor `REQUIRED_DOSSIER_SHAPE` and the Rules into per-key excerpts the
  shard builders can compose. Keep the monolithic `build_parent_synthesis_messages` intact for the
  fallback path.
- **`main.py`** — in `_run_pipeline`, branch on `heavy_sharded_synthesis_enabled`:
  - **on** → `dossier_dict, usage = run_sharded_synthesis(...)`; `regenerate` closure re-runs
    `run_sharded_synthesis` (or just the narrative — see §7).
  - **off** → today's `run_parent_only(...)` path, byte-for-byte unchanged.
  - The time-budget guard, `checkpoint.write_parent`, and `_finalize` wrapping are reused as-is
    (the sharded call returns the same `(dossier, usage)` tuple).
- **`functions/api/lib/generation-settings.schema.json`** — new keys (§6).
- **`functions/api/lib/generationSettings.js`** — headroom-warning math stays advisory; add a note
  if sharding is off *and* the configured `heavy_parent_max_tokens` × (1/46) would exceed budget.

No renderer, `store_lead`, `dossiers.js`, or DB-column changes — the merged dossier is shape-identical.

---

## 6. Super-admin settings (engine:"heavy", group:"operational")

| key | type | default | notes |
|---|---|---|---|
| `heavy_sharded_synthesis_enabled` | bool | **false** | master flag. Off = today's monolithic parent. Flip to true after live verification. |
| `heavy_shard_max_tokens` | int | 9000 | per-shard output ceiling (each shard is one section group). |
| `heavy_spine_max_tokens` | int | 6000 | spine output ceiling (scoring + brief + meta). |
| `heavy_narrative_max_tokens` | int | 8000 | narrative reduce ceiling (full_dossier_markdown). |
| `heavy_shard_timeout_s` | int | 300 | per-shard `asyncio.wait_for`. A shard timeout drops that key-set (partial). |
| `heavy_sharded_fallback_on_error` | bool | true | if spine or narrative errors, fall back to the monolithic parent within the same job (time permitting) before failing. |

Generators read these at job start with the existing `get_int`/`get_bool`; an empty settings row =
defaults (inert), matching the existing pattern. Schema is generic int/bool → auto-renders in the
Operational accordion, no `validate()` change.

---

## 7. Lint-retry & checkpoint interplay

- **Lint retry:** today `_finalize` calls `regenerate_parent` (full parent re-run) on a depth-lint
  warning. With sharding, most lint failures are localized (e.g. empty `last_90_days_timeline` →
  `shard_signals`; banned phrasing in outreach → `shard_playbook`; thin prose → narrative). **v1:**
  the `regenerate` closure re-runs `run_sharded_synthesis` wholesale (simplest, still far under
  budget because it's parallel). **v2 (noted, not built):** targeted re-run of only the offending
  shard + narrative. Keep v1 for this change.
- **Checkpoint:** unchanged keys. `checkpoint.write_parent` still stores the final assembled
  `dossier` before render, so render/upload retries and resume jobs never re-spend synthesis tokens.
  The resume path (`_run_resume`) calls whichever synthesis path the flag selects — if a resume runs
  with sharding on, it re-shards from the checkpointed fragments (still parallel, still cheap on
  wall-clock). No new checkpoint key needed for v1.

---

## 8. Verification plan

1. **Unit — merge disjointness:** assert no two `SHARD_SPECS` (incl. spine) declare the same owned
   key; assert merged dossier has every priority-1 key.
2. **Live, flag-on, Gabriel Colon / City of Coppell** (`gabriel.colon@coppelltx.gov`): confirm a
   complete, fully-populated dossier (no "Unknown Lead", all sections present), and capture
   per-stage timing from logs — spine, max shard, narrative — verifying total synthesis ≪ 780s.
3. **Token accounting:** Anthropic console shows spine cache_creation + shards cache_read (not N×
   full input). Record output-token delta vs a monolithic run of the same lead.
4. **Richer-than-today:** raise `heavy_shard_max_tokens`/`heavy_narrative_max_tokens` and confirm a
   materially larger dossier still finishes inside one 900s job — the thing the monolith can't do.
5. **Partial tolerance:** force one shard to time out (`heavy_shard_timeout_s`=min) → dossier renders
   `partial` with that section empty, not a hard failure.
6. **Fallback:** force a spine error with `heavy_sharded_fallback_on_error`=true → monolithic parent
   runs and completes.
7. **Flag-off regression:** `heavy_sharded_synthesis_enabled`=false → behavior byte-identical to
   today (monolithic parent + existing checkpoint/resume).

Deploy: `catalyst deploy --only functions:eliss-heavy-generator` and `--only functions:api`
(Python deploy needs local Python 3.9; non-interactive flags per project memory). No client rebuild.

---

## 9. Risks & trade-offs (honest)

- **Output tokens rise modestly** — spine duplication + per-shard envelopes + narrative. Mitigated by
  caching on input; accepted per the stated goal. Not "zero extra tokens."
- **Coherence is engineered, not free** — spine-first + tier-passing mitigates; a final consistency
  is not LLM-verified. The narrative reduce reading assembled structured data is the main coherence
  anchor for prose.
- **Cache-timing dependency** — if the spine→shard ordering or 5-min TTL is violated, input cost
  balloons. Enforced by running spine first and firing shards immediately after.
- **Complexity** — ~8 orchestrated calls, disjoint-key discipline, fallback path. Mitigated by the
  feature flag (ship off, verify, flip) and the unit disjointness test.
- **Throughput-dependent value** — justified by the 46.2 t/s measurement on the production-bound
  account. If that account is later upgraded to ≥100 t/s, the monolith may suffice and the flag can
  stay off. The flag makes this reversible.
