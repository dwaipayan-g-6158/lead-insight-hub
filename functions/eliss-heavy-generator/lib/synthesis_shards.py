"""Sharded parallel synthesis for the heavy pipeline.

Drop-in alternative to lib.fanout.run_parent_only, selected by the super-admin
setting heavy_synthesis_mode (auto/sharded) via main._should_shard. Instead of
one serial parent call that
emits the whole dossier (~585s for a 27K-token HOT dossier at 46 tok/s — see
docs/superpowers/specs/2026-06-11-heavy-sharded-synthesis-design.md), it runs:

    spine (serial, warms the prompt cache)
      → N section shards (parallel, each reads the cached fragments + the spine)
      → narrative reduce (serial, writes full_dossier_markdown over the merge)
      → deterministic dict merge (spine base + disjoint shard keys)

Each shard owns a DISJOINT set of top-level dossier keys (prompts.SHARD_SPECS),
so the merge is conflict-free — no LLM reconciliation call. The function returns
(dossier_dict, usage_dict) in EXACTLY the shape run_parent_only returns, so
main.py's _finalize / checkpoint / render tail is unchanged.

Reuses fanout.py's tolerant JSON parse, usage accumulation, model resolution,
truncation guard convention, and the RR firmographic safety-net merge — single
source of truth for those behaviors.
"""
import asyncio
import concurrent.futures
import logging
import os

from anthropic import Anthropic, AsyncAnthropic

from .app_settings import get_int
from .fanout import (
    ParentSynthesisTimeout,
    _accumulate_usage,
    _apply_rr_company_enrichment,
    _extract_json_obj,
    _join_text_blocks,
    _resolve_parent_model,
    _strip_placeholder_api_key,
)
from .prompts import (
    SHARD_SPECS,
    build_cached_inputs_text,
    build_narrative_messages,
    build_shard_instruction,
    build_spine_instruction,
)
from .skill_prompt import build_system_prompt

# Defaults (used when the super-admin settings row is empty). The Python
# generator reads settings.get via get_int with these same numbers, so an empty
# row is a no-op.
SPINE_MAX_TOKENS = 6_000
SHARD_MAX_TOKENS = 12_000
NARRATIVE_MAX_TOKENS = 8_000
SHARD_TIMEOUT_S = 300
# Spine (~6K tok) + narrative (~8K tok) ≈ 300s of serial streaming at ~46 tok/s;
# the parallel shards are bounded by SHARD_TIMEOUT_S. This buffer is added to the
# shard timeout to size the overall orchestration budget.
_SPINE_NARRATIVE_BUFFER_S = 240


def _build_messages(cached_inputs_text, instruction):
    """Spine/shard message list: a cached inputs block + a cheap trailing
    instruction. The cached block is byte-identical across spine and all shards
    so the cache (warmed by the spine) is reused by the shards."""
    return [{
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": cached_inputs_text,
                "cache_control": {"type": "ephemeral"},
            },
            {"type": "text", "text": instruction},
        ],
    }]


def _system_blocks(system_text):
    return [{
        "type": "text",
        "text": system_text,
        "cache_control": {"type": "ephemeral"},
    }]


def _check_truncation(response, label, max_tokens):
    # Same guard as fanout._run_parent_synthesis: a max_tokens stop means the
    # JSON is cut off and _extract_json_obj would silently return a small nested
    # object. Fail loudly so the orchestrator's fallback / failure path runs.
    if getattr(response, "stop_reason", None) == "max_tokens":
        raise ValueError(
            f"sharded {label} truncated: stop_reason=max_tokens at {max_tokens} "
            f"tokens — raise the corresponding heavy_*_max_tokens setting"
        )


def _run_sync_call(api_key, model, system_text, prefix_text, instruction,
                   *, max_tokens, thinking_enabled, thinking_budget, usage, log,
                   label):
    """One synchronous streaming call (spine or narrative). Mutates `usage`."""
    client = Anthropic(api_key=api_key)
    stream_kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "system": _system_blocks(system_text),
        "messages": _build_messages(prefix_text, instruction),
    }
    if thinking_enabled and int(thinking_budget) >= 1024 and int(thinking_budget) < max_tokens:
        stream_kwargs["thinking"] = {"type": "enabled", "budget_tokens": int(thinking_budget)}

    with client.messages.stream(**stream_kwargs) as stream:
        response = stream.get_final_message()
    _accumulate_usage(usage, response)
    _check_truncation(response, label, max_tokens)
    return _extract_json_obj(_join_text_blocks(response.content))


async def _run_shard_async(client, model, system_text, cached_inputs, spec,
                           spine_obj, *, max_tokens, timeout_s, usage, log):
    """One section shard. Returns (spec, dict) or (spec, None) on failure —
    partial-tolerant like the fan-out subagents (a missing section renders
    empty rather than failing the whole dossier)."""
    instruction = build_shard_instruction(spec, spine_obj)

    async def _do_call():
        async with client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=_system_blocks(system_text),
            messages=_build_messages(cached_inputs, instruction),
        ) as stream:
            return await stream.get_final_message()

    try:
        response = await asyncio.wait_for(_do_call(), timeout=timeout_s)
        # Single-threaded event loop → no lock needed on `usage`.
        _accumulate_usage(usage, response)
        _check_truncation(response, f"shard {spec['key']}", max_tokens)
        obj = _extract_json_obj(_join_text_blocks(response.content))
        log.info("sharded: shard %s ok (owns=%s)", spec["key"], ",".join(spec["owns"]))
        return (spec, obj)
    except asyncio.TimeoutError:
        log.warning("sharded: shard %s timed out after %ds — section(s) %s will be empty",
                    spec["key"], timeout_s, spec["owns"])
        return (spec, None)
    except Exception as e:
        log.warning("sharded: shard %s failed: %s — section(s) %s will be empty",
                    spec["key"], e, spec["owns"])
        return (spec, None)


async def _run_shards_async(api_key, model, system_text, cached_inputs, spine_obj,
                            *, max_tokens, timeout_s, usage, log):
    client = AsyncAnthropic(api_key=api_key)
    tasks = [
        _run_shard_async(client, model, system_text, cached_inputs, spec, spine_obj,
                         max_tokens=max_tokens, timeout_s=timeout_s, usage=usage, log=log)
        for spec in SHARD_SPECS
    ]
    return await asyncio.gather(*tasks)


def run_sharded_synthesis(
    fragments,
    intake,
    preflight_data,
    rr_baseline,
    *,
    settings=None,
    rr_degraded=False,
    rr_degradation_reason=None,
    parent_model=None,
    parent_max_tokens=None,          # accepted for call-site parity; unused (per-stage ceilings apply)
    parent_thinking_enabled=False,
    parent_thinking_budget=0,
    parent_payload_max_chars=None,
    parent_timeout_s=None,
    degraded=False,
    log=None,
    on_stage=None,
):
    """Spine → parallel shards → narrative reduce → merge.

    Returns (dossier_dict, usage_dict) in the same shape run_parent_only returns.
    Raises ParentSynthesisTimeout if the whole orchestration exceeds its budget
    (so main.py can defer to a resume job, exactly like the monolithic path).
    """
    log = log or logging.getLogger("eliss-heavy-generator")
    settings = settings or {}
    model = _resolve_parent_model(parent_model)
    payload_max_chars = parent_payload_max_chars or 80000

    spine_max = get_int(settings, "heavy_spine_max_tokens", SPINE_MAX_TOKENS)
    shard_max = get_int(settings, "heavy_shard_max_tokens", SHARD_MAX_TOKENS)
    narrative_max = get_int(settings, "heavy_narrative_max_tokens", NARRATIVE_MAX_TOKENS)
    shard_timeout = get_int(settings, "heavy_shard_timeout_s", SHARD_TIMEOUT_S)
    # Overall budget = the larger of the passed parent timeout and what the
    # orchestration actually needs (shards bounded by their timeout, plus the
    # serial spine + narrative). main.py's pre-synthesis budget guard ensures we
    # only START in-process when this fits the remaining job time.
    overall_timeout = max(int(parent_timeout_s or 0), shard_timeout + _SPINE_NARRATIVE_BUFFER_S)

    api_key = _strip_placeholder_api_key(os.environ.get("ANTHROPIC_API_KEY"))
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set in the function environment")

    if on_stage:
        try:
            on_stage("synthesis")
        except Exception:
            pass

    cached_inputs = build_cached_inputs_text(
        fragments, intake, preflight_data, rr_baseline,
        rr_degraded=rr_degraded, rr_degradation_reason=rr_degradation_reason,
        payload_max_chars=payload_max_chars,
    )
    system_text = build_system_prompt()
    usage = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}
    # Thinking on the spine only, and only when not in a degraded (timeout-retry) run.
    spine_thinking = bool(parent_thinking_enabled) and not degraded

    def _orchestrate():
        # 1) SPINE — serial; warms the cache and fixes the verdict/tier.
        spine_obj = _run_sync_call(
            api_key, model, system_text, cached_inputs, build_spine_instruction(),
            max_tokens=spine_max, thinking_enabled=spine_thinking,
            thinking_budget=parent_thinking_budget, usage=usage, log=log, label="spine",
        )
        tier = ((spine_obj or {}).get("scoring") or {}).get("tier") if isinstance(spine_obj, dict) else None
        log.info("sharded: spine done (tier=%s, out=%d)", tier, usage["output"])

        # 2) SHARDS — parallel; each reads the cached prefix + the spine.
        shard_results = asyncio.run(_run_shards_async(
            api_key, model, system_text, cached_inputs, spine_obj,
            max_tokens=shard_max, timeout_s=shard_timeout, usage=usage, log=log,
        ))

        # 3) MERGE — spine base + disjoint shard keys (no LLM reconciliation).
        dossier = {}
        if isinstance(spine_obj, dict):
            dossier.update(spine_obj)
        for spec, obj in shard_results:
            if not isinstance(obj, dict):
                continue
            for k in spec["owns"]:
                if k in obj:
                    dossier[k] = obj[k]
        ok = sum(1 for _, o in shard_results if isinstance(o, dict))
        log.info("sharded: %d/%d shards merged", ok, len(SHARD_SPECS))

        # 4) NARRATIVE — serial reduce over the assembled structured dossier.
        # Returns RAW markdown text (not JSON), so a max_tokens stop just yields
        # slightly shorter prose rather than unparseable JSON.
        narr_msgs = build_narrative_messages(dossier, payload_max_chars=payload_max_chars)
        narr_text = _run_narrative(api_key, model, system_text, narr_msgs, narrative_max, usage, log)
        if narr_text:
            dossier["full_dossier_markdown"] = narr_text
        else:
            log.warning("sharded: narrative produced no full_dossier_markdown")

        return dossier

    # Budget guard mirrors run_parent_only: stop WAITING at overall_timeout (the
    # underlying streams keep going, but the checkpoint is durable and the process
    # exits, so main.py defers cleanly).
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(_orchestrate)
        try:
            dossier = fut.result(timeout=overall_timeout)
        except concurrent.futures.TimeoutError:
            ex.shutdown(wait=False)
            raise ParentSynthesisTimeout(
                f"sharded synthesis exceeded {overall_timeout}s"
            )

    dossier = _apply_rr_company_enrichment(dossier, rr_baseline)
    usage["stop_reason"] = "end_turn"
    return dossier, usage


def _run_narrative(api_key, model, system_text, narr_msgs, narrative_max, usage, log):
    """Narrative call — returns full_dossier_markdown as RAW TEXT (not JSON).

    full_dossier_markdown is a single string field, so we ask for raw markdown
    and use the response text directly. A max_tokens stop is therefore NON-FATAL:
    it just yields a shorter (still-valid) narrative instead of unparseable JSON
    (the failure mode that crashed the first verification run). Strips an
    accidental ```markdown / ``` fence if the model adds one."""
    client = Anthropic(api_key=api_key)
    with client.messages.stream(
        model=model,
        max_tokens=narrative_max,
        system=_system_blocks(system_text),
        messages=narr_msgs,
    ) as stream:
        response = stream.get_final_message()
    _accumulate_usage(usage, response)
    if getattr(response, "stop_reason", None) == "max_tokens":
        log.warning("sharded: narrative hit max_tokens (%d) — using the truncated prose "
                    "(non-fatal); raise heavy_narrative_max_tokens for the full length",
                    narrative_max)
    text = _join_text_blocks(response.content).strip()
    # Strip a stray code fence if the model wrapped the markdown despite instructions.
    if text.startswith("```"):
        nl = text.find("\n")
        if nl != -1:
            text = text[nl + 1:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return text.strip()
