"""Heavy synthesis: 4 parallel Anthropic subagents + parent consolidation.

Replaces the single `synth.synthesize()` call used by eliss-generator with a
fan-out: four independent `AsyncAnthropic.messages.stream` calls run via
`asyncio.gather`, each scoped to one research layer with its own web_search
budget. A final parent call merges the four JSON fragments + preflight + RR
baseline into the canonical dossier JSON shape that store_lead / generate_report
already consume — so the rest of the pipeline is unchanged.

Why fan-out instead of one bigger call:
  • Within a single `messages.create` the model serializes its web_search tool
    use. 4 parallel `messages.stream` calls give ~4x effective search budget at
    roughly the same wall time as one larger call would have.
  • Per-subagent prompts can be narrower (just Tech, just Compliance, etc.),
    which keeps each call's output tokens bounded and reduces the chance of
    the model drifting off-topic under pressure.
  • Failures are partial: if Compliance times out, Tech/Org/Behavioral still
    contribute and the dossier surfaces as `partial` with a banner — matches
    the existing rr_degraded UX.

Hard caps that keep us inside Catalyst's 15-min Job ceiling:
  • Each subagent: max_uses=10 on web_search, asyncio.wait_for=600s.
  • Parent synthesis: max_tokens=32K, no tools (pure consolidation).

Returns:
  (dossier_dict, usage_dict, fanout_meta) — same shape as light's synthesize()
  for the first two, plus a meta dict with {subagents_ok, subagents_total,
  per_subagent_stats} for the partial-status decision in main.py.
"""
import asyncio
import concurrent.futures
import json
import logging
import os
import time
from typing import Optional

from anthropic import AsyncAnthropic

from .prompts import (
    SUBAGENT_PROMPTS,
    build_parent_synthesis_messages,
    build_subagent_messages,
)
from .skill_prompt import build_system_prompt


# Single shared model unless overridden per-subagent or via env. Sonnet is the
# sweet spot for the 4 research legs — Opus on all four would blow the token
# budget without commensurate quality lift; Opus on the parent synthesis is a
# defensible upgrade if cost permits (see plan file).
DEFAULT_SUBAGENT_MODEL = "claude-sonnet-4-6"
DEFAULT_PARENT_MODEL = "claude-sonnet-4-6"

# Per-subagent caps. The plan's validation report recommends 10-12; we use 10
# to leave headroom and keep occasional 11-search dips inside the timeout.
SUBAGENT_WEB_SEARCH_MAX_USES = 10
SUBAGENT_TIMEOUT_S = 600  # 10 min hard ceiling per subagent
SUBAGENT_MAX_TOKENS = 8_000  # JSON fragments are ~3-5K typical
# Parent must produce the full dossier JSON including the 8-15K char Tab 2
# `full_dossier_markdown` string. Sonnet 4.6 max output is 64K — we use the
# full ceiling so info-rich HOT-tier dossiers don't truncate the trailing
# data_quality / sources / full_dossier_markdown sections. The model only
# generates what it needs; this is a safety cap, not a target. Tradeoff:
# worst-case wall time ~10-13 min for parent streaming alone, plus
# fanout + preflight + render = pushing 15-min Job cap. If timeouts
# become common, tighten SUBAGENT_WEB_SEARCH_MAX_USES first, then consider
# the 2-Job pipeline split flagged in the plan file.
PARENT_MAX_TOKENS = 64_000


class ParentSynthesisTimeout(Exception):
    """Parent consolidation exceeded its wall-clock ceiling.

    Raised by run_parent_only when the parent call doesn't return inside
    parent_timeout_s. The fan-out checkpoint is already durable by the time
    this fires, so main.py hands off to a resume Job rather than losing the
    subagent tokens.
    """


def _strip_placeholder_api_key(raw: str) -> str:
    """Treat "REPLACE_ME"-style placeholders as unset.

    Mirrors the same treatment in lib/synth.py — when catalyst-config.json
    has a literal placeholder, the function shouldn't fall back to a real key
    in a shared env var. Fail loudly instead.
    """
    s = (raw or "").strip()
    return "" if s.startswith("REPLACE") else s


def _extract_json_obj(text: str):
    """Tolerant JSON parse — same approach as lib/synth._extract_dossier_json.

    Models reliably append narration ("Here's the dossier..."), occasionally
    open with a ```json fence, and very occasionally produce a second JSON
    block. `JSONDecoder.raw_decode` parses ONE value from a position and
    returns where it stopped — trailing content is ignored. We scan every `{`
    until one parses cleanly; almost always the first wins.
    """
    decoder = json.JSONDecoder()
    search_from = 0
    last_err = None
    while True:
        start = text.find("{", search_from)
        if start < 0:
            break
        try:
            obj, _end = decoder.raw_decode(text, idx=start)
            return obj
        except json.JSONDecodeError as e:
            last_err = e
            search_from = start + 1
    snippet = (text or "")[:500].replace("\n", " ")
    raise ValueError(
        f"no parseable JSON object in subagent response "
        f"(last error: {last_err}); first 500 chars: {snippet}"
    )


def _join_text_blocks(content_blocks) -> str:
    parts = []
    for block in content_blocks:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "\n".join(parts)


def _accumulate_usage(into: dict, response):
    usage = getattr(response, "usage", None)
    if not usage:
        return
    into["input"] = into.get("input", 0) + int(getattr(usage, "input_tokens", 0) or 0)
    into["output"] = into.get("output", 0) + int(getattr(usage, "output_tokens", 0) or 0)
    into["cache_read"] = into.get("cache_read", 0) + int(
        getattr(usage, "cache_read_input_tokens", 0) or 0
    )
    into["cache_creation"] = into.get("cache_creation", 0) + int(
        getattr(usage, "cache_creation_input_tokens", 0) or 0
    )


async def _run_one_subagent(
    client: AsyncAnthropic,
    name: str,
    spec: dict,
    intake: dict,
    preflight_data: dict,
    rr_baseline: Optional[dict],
    rr_degraded: bool,
    rr_degradation_reason: Optional[str],
    model: str,
    log: logging.Logger,
    max_tokens: int = SUBAGENT_MAX_TOKENS,
    web_search_max_uses: int = SUBAGENT_WEB_SEARCH_MAX_USES,
    timeout_s: int = SUBAGENT_TIMEOUT_S,
    payload_max_chars: int = 12000,
):
    """One layer-scoped research pass. Returns (name, fragment_dict, usage)
    or (name, None, usage) on timeout/error. Never raises — partial-tolerant.
    """
    t0 = time.monotonic()
    usage = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}
    try:
        system_blocks = [
            {
                "type": "text",
                "text": spec["system"],
                # Subagent system prompts are stable across runs — cache them.
                "cache_control": {"type": "ephemeral"},
            }
        ]
        messages = build_subagent_messages(
            spec, intake, preflight_data, rr_baseline,
            rr_degraded=rr_degraded,
            rr_degradation_reason=rr_degradation_reason,
            payload_max_chars=payload_max_chars,
        )
        tools = [
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": web_search_max_uses,
            }
        ]
        async def _do_call():
            async with client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                system=system_blocks,
                tools=tools,
                messages=messages,
            ) as stream:
                return await stream.get_final_message()

        response = await asyncio.wait_for(_do_call(), timeout=timeout_s)
        _accumulate_usage(usage, response)

        text = _join_text_blocks(response.content)
        try:
            fragment = _extract_json_obj(text)
        except ValueError as e:
            log.warning("subagent %s returned unparseable JSON: %s", name, e)
            return (name, None, usage)

        elapsed = time.monotonic() - t0
        log.info(
            "subagent %s ok in %.1fs (in=%d out=%d)",
            name, elapsed, usage["input"], usage["output"],
        )
        return (name, fragment, usage)

    except asyncio.TimeoutError:
        log.warning("subagent %s timed out after %ds", name, timeout_s)
        return (name, None, usage)
    except Exception as e:
        log.warning("subagent %s failed: %s", name, e)
        return (name, None, usage)


async def _fanout_async(
    intake, preflight_data, rr_baseline, rr_degraded, rr_degradation_reason,
    subagent_model, log,
    subagent_max_tokens=SUBAGENT_MAX_TOKENS,
    subagent_web_search_max_uses=SUBAGENT_WEB_SEARCH_MAX_USES,
    subagent_timeout_s=SUBAGENT_TIMEOUT_S,
    subagent_payload_max_chars=12000,
):
    api_key = _strip_placeholder_api_key(os.environ.get("ANTHROPIC_API_KEY"))
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set in the function environment")

    client = AsyncAnthropic(api_key=api_key)
    tasks = [
        _run_one_subagent(
            client, name, spec, intake, preflight_data, rr_baseline,
            rr_degraded, rr_degradation_reason, subagent_model, log,
            max_tokens=subagent_max_tokens,
            web_search_max_uses=subagent_web_search_max_uses,
            timeout_s=subagent_timeout_s,
            payload_max_chars=subagent_payload_max_chars,
        )
        for name, spec in SUBAGENT_PROMPTS.items()
    ]
    # return_exceptions is unnecessary because _run_one_subagent swallows;
    # left explicit for safety in case future edits surface an exception.
    results = await asyncio.gather(*tasks, return_exceptions=True)

    fragments = {}
    per_subagent = {}
    total_usage = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}
    for r in results:
        if isinstance(r, BaseException):
            log.warning("subagent task raised (caught at gather): %s", r)
            continue
        name, fragment, sub_usage = r
        per_subagent[name] = {
            "ok": fragment is not None,
            "input": sub_usage.get("input", 0),
            "output": sub_usage.get("output", 0),
        }
        for k, v in sub_usage.items():
            total_usage[k] = total_usage.get(k, 0) + int(v or 0)
        if fragment is not None:
            fragments[name] = fragment

    return fragments, per_subagent, total_usage


def _run_parent_synthesis(
    fragments, intake, preflight_data, rr_baseline,
    rr_degraded, rr_degradation_reason,
    parent_model, log,
    max_tokens=PARENT_MAX_TOKENS,
    thinking_enabled=False,
    thinking_budget=0,
    payload_max_chars=80000,
):
    """Sync parent call — pure text-gen, no tools, no streaming needed.

    Using the sync `Anthropic` client deliberately: AsyncAnthropic complicates
    `asyncio.run` nesting since the fan-out already consumed one event loop.
    For a tool-less ~32K-token request the sync client is simpler.
    """
    from anthropic import Anthropic
    api_key = _strip_placeholder_api_key(os.environ.get("ANTHROPIC_API_KEY"))
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set in the function environment")

    system_prompt = build_system_prompt()
    system_blocks = [{
        "type": "text",
        "text": system_prompt,
        "cache_control": {"type": "ephemeral"},
    }]
    messages = build_parent_synthesis_messages(
        fragments, intake, preflight_data, rr_baseline,
        rr_degraded=rr_degraded,
        rr_degradation_reason=rr_degradation_reason,
        payload_max_chars=payload_max_chars,
    )

    # Extended thinking is opt-in via super-admin settings. Same API constraints
    # as lib/synth.py: max_tokens > budget_tokens, no custom temperature (we set
    # none), budget >= 1024.
    stream_kwargs = {
        "model": parent_model,
        "max_tokens": max_tokens,
        "system": system_blocks,
        "messages": messages,
    }
    if thinking_enabled and int(thinking_budget) >= 1024 and int(thinking_budget) < max_tokens:
        stream_kwargs["thinking"] = {
            "type": "enabled",
            "budget_tokens": int(thinking_budget),
        }

    client = Anthropic(api_key=api_key)
    # Stream wrapper for the same > 8K max_tokens reason as in lib/synth.py.
    with client.messages.stream(**stream_kwargs) as stream:
        response = stream.get_final_message()

    text = _join_text_blocks(response.content)
    stop_reason = getattr(response, "stop_reason", None)
    # Truncation guard: if the model hit the max_tokens ceiling the dossier JSON
    # is cut off mid-object. _extract_json_obj would then silently fall through
    # to the first COMPLETE nested object (e.g. just the `lead` block
    # {"name": ...}), producing a near-empty "Unknown Lead" dossier with blank
    # sections. Fail loudly so the pipeline retries/fails instead of storing
    # garbage. (Root cause of the 2026-06-11 "Unknown Lead" report.)
    if stop_reason == "max_tokens":
        raise ValueError(
            f"parent synthesis truncated: stop_reason=max_tokens at {max_tokens} tokens — "
            "dossier JSON incomplete; raise heavy_parent_max_tokens or lower the payload"
        )
    dossier = _extract_json_obj(text)
    usage = {
        "input": int(getattr(response.usage, "input_tokens", 0) or 0),
        "output": int(getattr(response.usage, "output_tokens", 0) or 0),
        "cache_read": int(getattr(response.usage, "cache_read_input_tokens", 0) or 0),
        "cache_creation": int(getattr(response.usage, "cache_creation_input_tokens", 0) or 0),
        "stop_reason": stop_reason,
    }
    return dossier, usage


def _apply_rr_company_enrichment(dossier_dict, rr_baseline):
    """Same safety-net merge as lib/synth._apply_rr_company_enrichment.

    The parent synthesis model frequently drops RR firmographic fields under
    output-token pressure even when they were in the user message. This pass
    backfills the renderer-expected slots so the Tab 1 RocketReach card
    renders correctly. Read-only — only fills empty slots.
    """
    if not isinstance(dossier_dict, dict):
        return dossier_dict
    co_rr = (rr_baseline or {}).get("company") or {}
    if not isinstance(co_rr, dict) or not co_rr:
        return dossier_dict

    # setdefault returns the EXISTING value when the key is present — even if
    # that value is a string. Replace non-dict sections explicitly so the
    # subsequent .setdefault/.get chain on `co`/`tech`/`org` is safe.
    for k in ("company", "technology", "org_intelligence"):
        if not isinstance(dossier_dict.get(k), dict):
            dossier_dict[k] = {}
    co = dossier_dict["company"]
    tech = dossier_dict["technology"]
    org = dossier_dict["org_intelligence"]

    def _empty(v):
        return v in (None, "", [], {})

    def _set_if_empty(target, key, value, flag_key=None):
        if _empty(value):
            return
        if _empty(target.get(key)):
            target[key] = value
            if flag_key:
                target[flag_key] = True

    _set_if_empty(co, "rr_profile_url",
                  co_rr.get("profile_url") or co_rr.get("rr_profile_url"),
                  flag_key="_rocketreach_rr_profile_url")
    _set_if_empty(co, "year_founded",
                  co_rr.get("year_founded") or co_rr.get("founded_year"),
                  flag_key="_rocketreach_year_founded")
    addr = co_rr.get("address")
    if isinstance(addr, dict) and addr.get("description"):
        _set_if_empty(co, "rr_address", addr, flag_key="_rocketreach_rr_address")
    _set_if_empty(co, "company_phone",
                  co_rr.get("phone") or co_rr.get("company_phone"),
                  flag_key="_rocketreach_company_phone")
    _set_if_empty(co, "company_linkedin",
                  co_rr.get("linkedin_url") or co_rr.get("company_linkedin"),
                  flag_key="_rocketreach_company_linkedin")
    naics = co_rr.get("naics_codes") or co_rr.get("naics_code")
    if naics and not isinstance(naics, list):
        naics = [naics]
    _set_if_empty(co, "naics_codes", naics, flag_key="_rocketreach_naics_codes")
    sic = co_rr.get("sic_codes") or co_rr.get("sic_code")
    if sic and not isinstance(sic, list):
        sic = [sic]
    _set_if_empty(co, "sic_codes", sic, flag_key="_rocketreach_sic_codes")
    _set_if_empty(co, "industry_keywords",
                  co_rr.get("industry_keywords") or co_rr.get("keywords"),
                  flag_key="_rocketreach_industry_keywords")

    rr_tech = co_rr.get("techstack")
    if isinstance(rr_tech, list) and rr_tech:
        normalized = []
        for t in rr_tech:
            if isinstance(t, dict) and t.get("name"):
                normalized.append(t["name"])
            elif isinstance(t, str) and t:
                normalized.append(t)
        if normalized:
            _set_if_empty(tech, "techstack_from_rr", normalized,
                          flag_key="_rocketreach_techstack_from_rr")

    rr_growth = co_rr.get("growth") or co_rr.get("growth_trajectory")
    if rr_growth:
        _set_if_empty(tech, "growth_trajectory", rr_growth,
                      flag_key="_rocketreach_growth_trajectory")

    depts = (
        co_rr.get("departments_headcount")
        or co_rr.get("department_employee_distribution")
        or co_rr.get("departments")
    )
    if depts:
        _set_if_empty(org, "departments_headcount", depts,
                      flag_key="_rocketreach_departments_headcount")

    return dossier_dict


def _resolve_subagent_model(subagent_model):
    return (
        subagent_model
        or os.environ.get("ANTHROPIC_SUBAGENT_MODEL")
        or DEFAULT_SUBAGENT_MODEL
    ).strip()


def _resolve_parent_model(parent_model):
    return (
        parent_model
        or os.environ.get("ANTHROPIC_PARENT_MODEL")
        or DEFAULT_PARENT_MODEL
    ).strip()


def run_fanout_only(
    intake,
    preflight_data,
    rr_baseline,
    *,
    rr_degraded: bool = False,
    rr_degradation_reason: Optional[str] = None,
    subagent_model: Optional[str] = None,
    subagent_max_tokens: Optional[int] = None,
    subagent_web_search_max_uses: Optional[int] = None,
    subagent_timeout_s: Optional[int] = None,
    subagent_payload_max_chars: Optional[int] = None,
    log: Optional[logging.Logger] = None,
    on_stage=None,
):
    """Run JUST the 4-subagent fan-out — the expensive, checkpointable asset.

    Split out from run_heavy_synthesis so main.py can persist the fragments to
    Stratus the instant the barrier completes, then decide (time-budget guard)
    whether to run the parent in-process or hand it to a resume Job.

    Returns (fragments, per_subagent, fanout_usage, subagents_ok).
    Raises RuntimeError if every subagent failed (nothing to consolidate).
    """
    log = log or logging.getLogger("eliss-heavy-generator")
    subagent_model = _resolve_subagent_model(subagent_model)
    subagent_max_tokens = subagent_max_tokens or SUBAGENT_MAX_TOKENS
    subagent_web_search_max_uses = subagent_web_search_max_uses or SUBAGENT_WEB_SEARCH_MAX_USES
    subagent_timeout_s = subagent_timeout_s or SUBAGENT_TIMEOUT_S
    subagent_payload_max_chars = subagent_payload_max_chars or 12000

    if on_stage:
        try:
            on_stage("fanout")
        except Exception:
            pass

    fragments, per_subagent, fanout_usage = asyncio.run(
        _fanout_async(
            intake, preflight_data, rr_baseline,
            rr_degraded, rr_degradation_reason,
            subagent_model, log,
            subagent_max_tokens=subagent_max_tokens,
            subagent_web_search_max_uses=subagent_web_search_max_uses,
            subagent_timeout_s=subagent_timeout_s,
            subagent_payload_max_chars=subagent_payload_max_chars,
        )
    )
    subagents_ok = sum(1 for v in per_subagent.values() if v.get("ok"))
    log.info("fanout: %d/%d subagents returned a fragment", subagents_ok, len(SUBAGENT_PROMPTS))

    if subagents_ok == 0:
        # No fragments at all is a hard failure — the parent has nothing to
        # consolidate. Bubble up rather than producing a meaningless dossier.
        raise RuntimeError("all 4 subagents failed or timed out — no research fragments")

    return fragments, per_subagent, fanout_usage, subagents_ok


def run_parent_only(
    fragments,
    intake,
    preflight_data,
    rr_baseline,
    *,
    rr_degraded: bool = False,
    rr_degradation_reason: Optional[str] = None,
    parent_model: Optional[str] = None,
    parent_max_tokens: Optional[int] = None,
    parent_thinking_enabled: bool = False,
    parent_thinking_budget: int = 0,
    parent_payload_max_chars: Optional[int] = None,
    parent_timeout_s: Optional[int] = None,
    degraded: bool = False,
    log: Optional[logging.Logger] = None,
    on_stage=None,
):
    """Run JUST the parent consolidation over already-computed fragments.

    Wraps the (sync) parent call in a wall-clock timeout so a slow stream can't
    silently eat the whole Job budget. On timeout raises ParentSynthesisTimeout
    — by then the fan-out checkpoint exists, so the caller can resume cheaply.

    `degraded=True` (a timeout-triggered resume) disables thinking and tightens
    the output ceiling so the retry is likelier to finish.

    Returns (dossier_dict, parent_usage).
    """
    log = log or logging.getLogger("eliss-heavy-generator")
    parent_model = _resolve_parent_model(parent_model)
    parent_max_tokens = parent_max_tokens or PARENT_MAX_TOKENS
    parent_payload_max_chars = parent_payload_max_chars or 80000

    if degraded:
        # "Degraded" disables extended thinking ONLY. Do NOT reduce max_tokens:
        # generation time scales with the tokens the model actually emits, not
        # the ceiling, so a lower cap doesn't make it finish sooner — it just
        # TRUNCATES the dossier JSON (→ unparseable → near-empty "Unknown Lead").
        # The real lever for a slow parent is more wall-clock, which the resume
        # job already provides (see _run_resume's generous parent timeout).
        parent_thinking_enabled = False
        log.info("parent running DEGRADED (extended thinking disabled)")

    if on_stage:
        try:
            on_stage("synthesis")
        except Exception:
            pass

    def _call():
        return _run_parent_synthesis(
            fragments, intake, preflight_data, rr_baseline,
            rr_degraded, rr_degradation_reason,
            parent_model, log,
            max_tokens=parent_max_tokens,
            thinking_enabled=parent_thinking_enabled,
            thinking_budget=parent_thinking_budget,
            payload_max_chars=parent_payload_max_chars,
        )

    if parent_timeout_s and int(parent_timeout_s) > 0:
        # ThreadPoolExecutor + result(timeout=...) stops us WAITING on a runaway
        # parent stream; it can't kill the underlying HTTP call (the sync
        # Anthropic client owns it). That's fine — the checkpoint is durable and
        # the Job is about to defer/exit, so the abandoned thread dies with the
        # process. shutdown(wait=False) so we never block on that thread.
        ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        fut = ex.submit(_call)
        try:
            dossier, parent_usage = fut.result(timeout=int(parent_timeout_s))
            ex.shutdown(wait=False)
        except concurrent.futures.TimeoutError:
            ex.shutdown(wait=False)
            log.warning("parent synthesis exceeded %ss — ParentSynthesisTimeout", parent_timeout_s)
            raise ParentSynthesisTimeout(f"parent synthesis exceeded {parent_timeout_s}s")
    else:
        dossier, parent_usage = _call()

    dossier = _apply_rr_company_enrichment(dossier, rr_baseline)
    return dossier, parent_usage


def merge_usage(fanout_usage, parent_usage):
    """Sum two usage dicts into the total_usage shape main.py records."""
    fanout_usage = fanout_usage or {}
    parent_usage = parent_usage or {}
    return {
        "input": fanout_usage.get("input", 0) + parent_usage.get("input", 0),
        "output": fanout_usage.get("output", 0) + parent_usage.get("output", 0),
        "cache_read": fanout_usage.get("cache_read", 0) + parent_usage.get("cache_read", 0),
        "cache_creation": (
            fanout_usage.get("cache_creation", 0) + parent_usage.get("cache_creation", 0)
        ),
        "stop_reason": parent_usage.get("stop_reason"),
    }


def run_heavy_synthesis(
    intake,
    preflight_data,
    rr_baseline,
    *,
    rr_degraded: bool = False,
    rr_degradation_reason: Optional[str] = None,
    subagent_model: Optional[str] = None,
    parent_model: Optional[str] = None,
    subagent_max_tokens: Optional[int] = None,
    parent_max_tokens: Optional[int] = None,
    subagent_web_search_max_uses: Optional[int] = None,
    subagent_timeout_s: Optional[int] = None,
    subagent_payload_max_chars: Optional[int] = None,
    parent_payload_max_chars: Optional[int] = None,
    parent_thinking_enabled: bool = False,
    parent_thinking_budget: int = 0,
    parent_timeout_s: Optional[int] = None,
    log: Optional[logging.Logger] = None,
    on_stage=None,
):
    """Thin wrapper: fan-out then parent, in one call. Same return shape as
    before — kept for the lint-retry path in main.py and any other caller. The
    main pipeline now calls run_fanout_only / run_parent_only directly so it can
    checkpoint between them.

    Returns (dossier_dict, total_usage, fanout_meta).
    """
    log = log or logging.getLogger("eliss-heavy-generator")
    fragments, per_subagent, fanout_usage, subagents_ok = run_fanout_only(
        intake, preflight_data, rr_baseline,
        rr_degraded=rr_degraded, rr_degradation_reason=rr_degradation_reason,
        subagent_model=subagent_model,
        subagent_max_tokens=subagent_max_tokens,
        subagent_web_search_max_uses=subagent_web_search_max_uses,
        subagent_timeout_s=subagent_timeout_s,
        subagent_payload_max_chars=subagent_payload_max_chars,
        log=log, on_stage=on_stage,
    )
    dossier, parent_usage = run_parent_only(
        fragments, intake, preflight_data, rr_baseline,
        rr_degraded=rr_degraded, rr_degradation_reason=rr_degradation_reason,
        parent_model=parent_model,
        parent_max_tokens=parent_max_tokens,
        parent_thinking_enabled=parent_thinking_enabled,
        parent_thinking_budget=parent_thinking_budget,
        parent_payload_max_chars=parent_payload_max_chars,
        parent_timeout_s=parent_timeout_s,
        log=log, on_stage=on_stage,
    )
    fanout_meta = {
        "subagents_total": len(SUBAGENT_PROMPTS),
        "subagents_ok": subagents_ok,
        "per_subagent": per_subagent,
    }
    return dossier, merge_usage(fanout_usage, parent_usage), fanout_meta
