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
        )
        tools = [
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": SUBAGENT_WEB_SEARCH_MAX_USES,
            }
        ]
        async def _do_call():
            async with client.messages.stream(
                model=model,
                max_tokens=SUBAGENT_MAX_TOKENS,
                system=system_blocks,
                tools=tools,
                messages=messages,
            ) as stream:
                return await stream.get_final_message()

        response = await asyncio.wait_for(_do_call(), timeout=SUBAGENT_TIMEOUT_S)
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
        log.warning("subagent %s timed out after %ds", name, SUBAGENT_TIMEOUT_S)
        return (name, None, usage)
    except Exception as e:
        log.warning("subagent %s failed: %s", name, e)
        return (name, None, usage)


async def _fanout_async(
    intake, preflight_data, rr_baseline, rr_degraded, rr_degradation_reason,
    subagent_model, log,
):
    api_key = _strip_placeholder_api_key(os.environ.get("ANTHROPIC_API_KEY"))
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set in the function environment")

    client = AsyncAnthropic(api_key=api_key)
    tasks = [
        _run_one_subagent(
            client, name, spec, intake, preflight_data, rr_baseline,
            rr_degraded, rr_degradation_reason, subagent_model, log,
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
    )

    client = Anthropic(api_key=api_key)
    # Stream wrapper for the same > 8K max_tokens reason as in lib/synth.py.
    with client.messages.stream(
        model=parent_model,
        max_tokens=PARENT_MAX_TOKENS,
        system=system_blocks,
        messages=messages,
    ) as stream:
        response = stream.get_final_message()

    text = _join_text_blocks(response.content)
    dossier = _extract_json_obj(text)
    usage = {
        "input": int(getattr(response.usage, "input_tokens", 0) or 0),
        "output": int(getattr(response.usage, "output_tokens", 0) or 0),
        "cache_read": int(getattr(response.usage, "cache_read_input_tokens", 0) or 0),
        "cache_creation": int(getattr(response.usage, "cache_creation_input_tokens", 0) or 0),
        "stop_reason": getattr(response, "stop_reason", None),
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


def run_heavy_synthesis(
    intake,
    preflight_data,
    rr_baseline,
    *,
    rr_degraded: bool = False,
    rr_degradation_reason: Optional[str] = None,
    subagent_model: Optional[str] = None,
    parent_model: Optional[str] = None,
    log: Optional[logging.Logger] = None,
    on_stage=None,
):
    """Public entry — same call site shape as lib/synth.synthesize().

    Args:
        intake, preflight_data, rr_baseline: same as light's synthesize().
        rr_degraded, rr_degradation_reason: same OSINT-fallback contract.
        subagent_model: override Sonnet 4.6 for the 4 research legs.
        parent_model: override Sonnet 4.6 for the consolidation call.
        log: logger; falls back to module logger.
        on_stage: optional callback(stage_name) used by main.py to flip the
            dossier_requests.stage column mid-fanout so the front-end pill
            doesn't think we stalled during the long subagent wait.

    Returns:
        (dossier_dict, usage_dict, fanout_meta)
        fanout_meta = {
            "subagents_total": 4,
            "subagents_ok": int (0-4),
            "per_subagent": {name: {ok, input, output}},
        }
    """
    log = log or logging.getLogger("eliss-heavy-generator")
    subagent_model = (
        subagent_model
        or os.environ.get("ANTHROPIC_SUBAGENT_MODEL")
        or DEFAULT_SUBAGENT_MODEL
    ).strip()
    parent_model = (
        parent_model
        or os.environ.get("ANTHROPIC_PARENT_MODEL")
        or DEFAULT_PARENT_MODEL
    ).strip()

    # ---- fan-out ----------------------------------------------------------
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
        )
    )
    subagents_ok = sum(1 for v in per_subagent.values() if v.get("ok"))
    log.info("fanout: %d/%d subagents returned a fragment", subagents_ok, len(SUBAGENT_PROMPTS))

    if subagents_ok == 0:
        # No fragments at all is a hard failure — the parent has nothing to
        # consolidate. Bubble up rather than producing a meaningless dossier.
        raise RuntimeError("all 4 subagents failed or timed out — no research fragments")

    # ---- parent synthesis -------------------------------------------------
    if on_stage:
        try:
            on_stage("synthesis")
        except Exception:
            pass

    dossier, parent_usage = _run_parent_synthesis(
        fragments, intake, preflight_data, rr_baseline,
        rr_degraded, rr_degradation_reason,
        parent_model, log,
    )

    dossier = _apply_rr_company_enrichment(dossier, rr_baseline)

    total_usage = {
        "input": fanout_usage.get("input", 0) + parent_usage.get("input", 0),
        "output": fanout_usage.get("output", 0) + parent_usage.get("output", 0),
        "cache_read": fanout_usage.get("cache_read", 0) + parent_usage.get("cache_read", 0),
        "cache_creation": (
            fanout_usage.get("cache_creation", 0) + parent_usage.get("cache_creation", 0)
        ),
        "stop_reason": parent_usage.get("stop_reason"),
    }
    fanout_meta = {
        "subagents_total": len(SUBAGENT_PROMPTS),
        "subagents_ok": subagents_ok,
        "per_subagent": per_subagent,
    }
    return dossier, total_usage, fanout_meta
