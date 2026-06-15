"""Anthropic synthesis — direct Messages API with web_search server tool.

One streaming API call. The Anthropic SDK requires streaming for any request
that could exceed 10 minutes (any max_tokens > ~8K triggers this), so we use
messages.stream() with get_final_message() to bypass the non-streaming
timeout. We don't actually consume the stream incrementally — we just need
the streaming envelope.
"""
import json
import os
import re

from anthropic import Anthropic

from .skill_prompt import build_system_prompt, build_user_prompt

DEFAULT_MODEL = "claude-sonnet-4-6"
# 32K is enough for the dossier (~25K typical) with headroom for thinking
# and the model's internal tool-use orchestration of web_search.
DEFAULT_MAX_TOKENS = 32_000
# Light edition runs 4 web searches per dossier — was 6, dropped to
# halve the worst case when the lint retry fires (each search ≈ 1 min
# of streaming latency). The skill's STEP-3 evidence floor is unaffected:
# 4 searches still hits the minimum-3-tier-A-sources requirement when
# the queries are well-formed.
WEB_SEARCH_MAX_USES = 4


def _extract_dossier_json(content_blocks):
    """Find the final text block(s) and parse the embedded JSON object.

    The system prompt instructs the model to output only JSON, but the
    model sometimes appends a trailing sentence ("Here's the dossier
    — let me know if…") or a second JSON snippet after the main one.
    `json.loads(text[start:end+1])` then raised "Extra data" at the byte
    where the narration started (seen on Eric Herasymchuck @ char 47026).

    Fix: scan for the first `{` and use JSONDecoder.raw_decode, which
    parses exactly one value and returns the index where it stopped.
    Trailing content is ignored. Handles both bare object output and
    ```json ... ``` fences (raw_decode is fine starting at the brace,
    fences are skipped over by the leading-whitespace scan it does).
    """
    text_parts = []
    for block in content_blocks:
        block_type = getattr(block, "type", None)
        if block_type == "text":
            text_parts.append(block.text)
    if not text_parts:
        raise ValueError("LLM response contained no text blocks")
    text = "\n".join(text_parts)

    decoder = json.JSONDecoder()

    # Walk through every `{` until raw_decode parses one cleanly. Almost
    # always the first one wins; the loop only matters if the model
    # opens with a stray `{` inside an example/narration block.
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

    snippet = text[:500].replace("\n", " ")
    raise ValueError(
        f"LLM response had no parseable JSON object "
        f"(last error: {last_err}); first 500 chars: {snippet}"
    )


def synthesize(intake, preflight_data, rr_baseline, *, rr_degraded=False,
               rr_degradation_reason=None, model=None, max_tokens=None,
               web_search_max_uses=None, thinking_enabled=False,
               thinking_budget=0):
    """Call Anthropic with web_search; return (dossier_dict, usage_dict).

    Args:
        intake: {name, email, linkedin_url, company_url, notes} (any subset).
        preflight_data: dict from skill.scripts.preflight.run_preflight().
        rr_baseline: dict from RocketReachClient.run_baseline_enrichment().
            May be None when rr_degraded=True with reason rr_full_miss.
        rr_degraded: True when RR coverage gap was detected and the pipeline
            is running in OSINT-augmented mode. Triggers a guard block in the
            user prompt forbidding firmographic fabrication.
        rr_degradation_reason: "rr_full_miss" (no RR data at all) or
            "rr_company_miss" (named_contact/exec_dmu present, firmographics
            missing). Selects the guard block variant.
        model: override ANTHROPIC_MODEL env var. Default claude-sonnet-4-6.
        max_tokens: override DEFAULT_MAX_TOKENS.

    Returns:
        (dossier_dict, {"input": int, "output": int, "cache_read": int,
                        "cache_creation": int, "stop_reason": str})

    Raises:
        RuntimeError if ANTHROPIC_API_KEY is unset. Anthropic SDK exceptions
        propagate to the caller (main.py catches and patches the row).
    """
    api_key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    # Treat literal placeholder strings as unset.
    if api_key.startswith("REPLACE"):
        api_key = ""
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set in the function environment")

    model = (model or os.environ.get("ANTHROPIC_MODEL") or DEFAULT_MODEL).strip()
    max_tokens = max_tokens or DEFAULT_MAX_TOKENS
    web_uses = WEB_SEARCH_MAX_USES if web_search_max_uses is None else int(web_search_max_uses)

    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(
        intake, preflight_data, rr_baseline,
        rr_degraded=rr_degraded,
        rr_degradation_reason=rr_degradation_reason,
    )

    # Prompt-cache the 24K-char system prefix; identical across every dossier
    # in a session, so the second+ call reads it cheaply.
    system_block = [
        {
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral"},
        }
    ]
    tools = [
        {
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": web_uses,
        }
    ]

    # Extended thinking is opt-in via the super-admin settings. The Messages
    # API requires max_tokens > budget_tokens and forbids a custom temperature
    # while thinking is on (we never set temperature, so that holds). A budget
    # below 1024 is rejected by the API, so we gate on it here defensively.
    stream_kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system_block,
        "tools": tools,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    if thinking_enabled and int(thinking_budget) >= 1024 and int(thinking_budget) < max_tokens:
        stream_kwargs["thinking"] = {
            "type": "enabled",
            "budget_tokens": int(thinking_budget),
        }

    client = Anthropic(api_key=api_key)
    # Streaming required for any max_tokens > ~8K (the SDK rejects non-
    # streaming calls that could in theory exceed 10 minutes).
    # get_final_message blocks until completion and returns the same shape
    # as create() would have produced.
    with client.messages.stream(**stream_kwargs) as stream:
        response = stream.get_final_message()

    # Truncation guard: a max_tokens stop means the dossier JSON is cut off, and
    # _extract_dossier_json would silently fall through to a small nested object
    # (→ near-empty "Unknown Lead" dossier with blank sections). Fail loudly so
    # the lint-retry / failure path runs instead of storing garbage.
    if getattr(response, "stop_reason", None) == "max_tokens":
        raise ValueError(
            f"synthesis truncated: stop_reason=max_tokens at {max_tokens} tokens — "
            "dossier JSON incomplete; raise light_max_tokens"
        )
    dossier = _extract_dossier_json(response.content)
    dossier = _apply_rr_company_enrichment(dossier, rr_baseline)
    usage = {
        "input": getattr(response.usage, "input_tokens", 0) or 0,
        "output": getattr(response.usage, "output_tokens", 0) or 0,
        "cache_read": getattr(response.usage, "cache_read_input_tokens", 0) or 0,
        "cache_creation": getattr(response.usage, "cache_creation_input_tokens", 0) or 0,
        "stop_reason": getattr(response, "stop_reason", None),
    }
    return dossier, usage


def _apply_rr_company_enrichment(dossier_dict, rr_baseline):
    """Backfill renderer-expected RR firmographic fields from rr_baseline['company'].

    The renderer at scripts/generate_report.py build_rocketreach_enrichment()
    reads 11 specific paths. The LLM frequently drops most of them under
    output-token pressure even when the raw data was in the user prompt
    (observed on Karen Lenkeys / Qlarant — 21K output tokens, only
    year_founded survived into the dossier). This pass is the safety net.

    Read-only merge — only sets a field when it's missing or empty in the
    LLM-synthesized dict. Sets _rocketreach_<field>: true flags so the
    renderer's RR provenance pill (ᴿᴿ) attaches correctly.
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

    # company.* slots
    _set_if_empty(
        co, "rr_profile_url",
        co_rr.get("profile_url") or co_rr.get("rr_profile_url"),
        flag_key="_rocketreach_rr_profile_url",
    )
    _set_if_empty(
        co, "year_founded",
        co_rr.get("year_founded") or co_rr.get("founded_year"),
        flag_key="_rocketreach_year_founded",
    )
    # RR returns `address` as a dict with description/city/state. Renderer
    # reads either company.rr_address or company.address with a 'description'
    # key; we land in rr_address so we don't shadow the LLM's prose address.
    addr = co_rr.get("address")
    if isinstance(addr, dict) and addr.get("description"):
        _set_if_empty(co, "rr_address", addr, flag_key="_rocketreach_rr_address")
    _set_if_empty(
        co, "company_phone",
        co_rr.get("phone") or co_rr.get("company_phone"),
        flag_key="_rocketreach_company_phone",
    )
    _set_if_empty(
        co, "company_linkedin",
        co_rr.get("linkedin_url") or co_rr.get("company_linkedin"),
        flag_key="_rocketreach_company_linkedin",
    )
    # RR uses singular `naics_code` / `sic_code` for primary, list variants
    # for full set. Normalize to a list either way.
    naics = co_rr.get("naics_codes") or co_rr.get("naics_code")
    if naics and not isinstance(naics, list):
        naics = [naics]
    _set_if_empty(co, "naics_codes", naics, flag_key="_rocketreach_naics_codes")
    sic = co_rr.get("sic_codes") or co_rr.get("sic_code")
    if sic and not isinstance(sic, list):
        sic = [sic]
    _set_if_empty(co, "sic_codes", sic, flag_key="_rocketreach_sic_codes")
    _set_if_empty(
        co, "industry_keywords",
        co_rr.get("industry_keywords") or co_rr.get("keywords"),
        flag_key="_rocketreach_industry_keywords",
    )

    # technology.* slots — RR's `techstack` is a list of {name, ...} or strings.
    # Renderer's pill loop is shape-tolerant, but list[str] is the canonical
    # contract from dossier-schema so we normalize here.
    rr_tech = co_rr.get("techstack")
    if isinstance(rr_tech, list) and rr_tech:
        normalized = []
        for t in rr_tech:
            if isinstance(t, dict) and t.get("name"):
                normalized.append(t["name"])
            elif isinstance(t, str) and t:
                normalized.append(t)
        if normalized:
            _set_if_empty(
                tech, "techstack_from_rr", normalized,
                flag_key="_rocketreach_techstack_from_rr",
            )

    rr_growth = co_rr.get("growth") or co_rr.get("growth_trajectory")
    if rr_growth:
        _set_if_empty(
            tech, "growth_trajectory", rr_growth,
            flag_key="_rocketreach_growth_trajectory",
        )

    # org_intelligence.* — RR returns `department_employee_distribution` or
    # `departments` depending on plan tier; renderer reads departments_headcount.
    depts = (
        co_rr.get("departments_headcount")
        or co_rr.get("department_employee_distribution")
        or co_rr.get("departments")
    )
    if depts:
        _set_if_empty(
            org, "departments_headcount", depts,
            flag_key="_rocketreach_departments_headcount",
        )

    return dossier_dict
