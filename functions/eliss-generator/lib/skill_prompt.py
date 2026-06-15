"""Load the vendored eliss-light skill into a system prompt + user prompt template.

The skill is vendored at ../skill/{SKILL.md, references/*.md, scripts/*.py}.
We concatenate SKILL.md + the three most-load-bearing reference docs into a
single system prompt so the model sees the rubric, schema, and intake rules
without needing to make tool calls to read them.

Prompt-cache-able: the system prompt is identical across every dossier in a
session. The caller in main.py marks the system block with cache_control so
Anthropic stores the prefix and reads it cheaply on each subsequent call
(per memory: this matches the cache_control pattern in the Claude API docs).
"""
import os
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SKILL_ROOT = _HERE.parent / "skill"


# Memory constraints that must be inlined into the system prompt because the
# Claude Code memory system doesn't propagate to direct Anthropic API calls.
# Each maps to one of the feedback_eliss_*.md memory files locally.
_MEMORY_CONSTRAINTS = """
# CRITICAL GENERATION CONSTRAINTS (server-side runtime — these override the skill's defaults)

1. **HTML-only output** — Never produce PDF instructions or call any tool that
   writes anything other than the JSON dossier dict. The HTML rendering happens
   in a separate subprocess after you return; you only emit the JSON.

2. **Tab 1 dict-unwrap discipline** — Every score, ICP rating, tier, confidence
   value, and verdict field MUST be a plain scalar in your JSON output. Do NOT
   wrap values in `{value: ..., confidence: ..., tier: ...}` dicts at the top
   level of `scoring` — the renderer's `_extract_value()` only reads the
   `value` key. Wrapping inside `scoring.dimensions.fit.score` etc. IS allowed.

3. **Tab 1 card contracts** — These fields are SHALLOW (flat strings or lists
   of strings), not nested dicts:
     - executive_brief (str, 200-300 chars)
     - technology.security_stack (list[str])
     - technology.competitors_detected (list[str])
     - technology.{ad_environment, cloud_posture, digital_maturity, displacement_angle} (str)
     - budget_analysis.{estimated_it_spend, security_budget, affordability, budget_trend, deal_authority, deal_cycle_months, calculation_basis} (str — clean dollar strings, NO tildes like ~$X.XM)
     - compliance[*].framework (str, e.g. "HIPAA Security Rule (2025 Update)")
     - compliance[*].pressure (str — exactly one of "HIGH" / "MEDIUM" / "LOW",
       drives the heatmap pressure pill color)
     - compliance[*].urgency (str, prose explaining WHY pressure is this level
       — deadlines, recent enforcement, contract clauses — ~80-200 chars)
     - compliance[*].ad360_fit AND compliance[*].log360_fit (SHORT PROSE
       describing HOW that product addresses this framework, 15-80 chars
       each, e.g. "MFA + privileged session for ePHI access", "Logon audit
       trail for OCR breach review"). NEVER set these to "HIGH" / "MEDIUM"
       / "LOW" — those duplicate the pressure label and produce a useless
       heatmap. If you genuinely cannot describe the angle, OMIT the field
       so the renderer falls back to "—" instead of a misleading label.
       Legacy aliases ad360_angle / log360_angle accepted for backward
       compatibility — same prose contract.
     - lead.tenure (str)
     - company.revenue_estimate (str)
   Nested dicts in these positions render as empty-state.

4. **scoring.{final_score, tier, overall_confidence, risk_adjusted_composite, total_risk_adjustment}**
   must be FLAT at the top of `scoring`, NOT nested under `scoring.composite`.

5. **meta.generated** is a date string `YYYY-MM-DD`, not an ISO timestamp.

6. **company.name** (NOT `legal_name`) drives the filename — must be present.

7. **full_dossier_markdown callouts** open at COLUMN 0 (`**Why:**`, `**Action:**`,
   `**Trigger:**`, `**Why this is HOT now:**`, etc.) — NOT preceded by `>` which
   produces a blockquote, not a callout.

8. **You MUST output JSON only** — no preamble, no markdown fences, no trailing
   commentary. The full response is parsed by `json.loads(response_text)`.

9. **demo_playbook (v7.6.0)** — top-level `demo_playbook{}` is OPTIONAL but
   EXPECTED for HOT and WARM tiers; renderer silently omits the Tab 1 card when
   absent. Shape (mirror for both `ad360` and `log360` keys):
     {
       "ad360":  {"opening_hook": str,
                  "value_moments":      [ {"title": str, "why_it_matters": str, "tell_show_tell": str}, ×3 ],
                  "discovery_questions":[ str, ×3 ],
                  "top_objections":     [ {"objection": str, "response": str}, ×2 ],
                  "cta": str},
       "log360": { ... same shape ... }
     }
   Value moments MUST tie to a specific dossier fact (NOT a feature tour). Skip
   demo_playbook entirely for COOL / COLD tiers — do not emit empty/placeholder
   blocks.

10. **Outreach voice enum (v7.6.0)** — canonical values are `technical`,
    `executive`, `consultative`. Do NOT emit the deprecated brand-coupled names
    (`google`, `apple`, `microsoft`); the renderer aliases them only for
    backward compat with pre-v7.6 dossiers. New dossiers MUST use the canonical
    enum. Voice ↔ template mapping is documented in
    `references/outreach-playbook.md`.

11. **RocketReach company-enrichment passthrough** — when rr_baseline is
    present in the user message, mirror these fields into the dossier dict
    so the Tab 1 "RocketReach Firmographic Enrichment" card renders:
      • company.rr_profile_url      (from rr_baseline.company.profile_url)
      • company.year_founded
      • company.rr_address          (full dict with description/city/state)
      • company.company_phone       (set _rocketreach_company_phone: true)
      • company.company_linkedin    (set _rocketreach_company_linkedin: true)
      • company.naics_codes         (always a list, even with one code)
      • company.sic_codes           (always a list)
      • company.industry_keywords
      • technology.techstack_from_rr  (list[str], capped at ~40)
      • technology.growth_trajectory
      • org_intelligence.departments_headcount
    Mark each RR-sourced field with `_rocketreach_<field>: true`. Curate
    where it adds value (de-dupe techstack, normalize labels) — but do NOT
    drop fields. A server-side merge backfills missing values from the
    baseline, but LLM-curated values (when present and richer) win.
"""


def _read_file(path):
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def build_system_prompt():
    """Concatenate SKILL.md + scoring + schema + memory constraints.

    Outreach playbook is NOT included by default — it's only relevant if the
    model is producing email slots, which adds ~25K chars. The current
    pipeline includes it because every HOT/WARM dossier produces emails.
    """
    skill_md = _read_file(_SKILL_ROOT / "SKILL.md")
    scoring_md = _read_file(_SKILL_ROOT / "references" / "scoring-rubric.md")
    schema_md = _read_file(_SKILL_ROOT / "references" / "dossier-schema.md")
    datapoint_md = _read_file(_SKILL_ROOT / "references" / "datapoint-mining.md")
    outreach_md = _read_file(_SKILL_ROOT / "references" / "outreach-playbook.md")

    parts = [
        skill_md,
        "\n\n---\n# references/scoring-rubric.md\n\n" + scoring_md,
        "\n\n---\n# references/dossier-schema.md\n\n" + schema_md,
        "\n\n---\n# references/datapoint-mining.md\n\n" + datapoint_md,
        "\n\n---\n# references/outreach-playbook.md\n\n" + outreach_md,
        _MEMORY_CONSTRAINTS,
    ]
    return "".join(parts)


_DEGRADED_SCAFFOLDING_REQUIREMENT = (
    " REQUIRED SCAFFOLDING (must be emitted regardless of degraded mode — "
    "these are OSINT-derivable from role, industry, and public signals, "
    "NOT firmographics): `scoring.icp_rating` (object with `label` ∈ "
    "{Weak, Moderate, Strong, Excellent} and `reason` prose), "
    "`scoring.verdict` (object with `headline`, `insight`, `next_step` — "
    "set headline to null only for COOL/COLD tiers per existing schema, "
    "but always emit `insight` and `next_step`), `scoring.dimensions.{fit,"
    "intent,timing,budget}` (each with `score`, `max`, `confidence`; max "
    "is fixed by rubric: fit=25, intent=25, timing=30, budget=20), "
    "`scoring.tier`, `scoring.final_score`, `scoring.overall_confidence`, "
    "and `executive_brief` (200-300 char string). Dropping any of these "
    "leaves the React lead-detail UI blank — the degraded mode constrains "
    "data sourcing, NOT the schema shape."
)

_DEGRADED_GUARD_FULL_MISS = (
    "DEGRADED MODE — RocketReach has no record of this organization "
    "(common for .gov/.edu/non-profit orgs RocketReach does not index). "
    "Source ALL firmographics, exec DMU, and contact data from web_search "
    "and preflight only. Mark every value Tier-C in the JSON. Do NOT "
    "fabricate `num_employees`, `revenue_estimate`, or `techstack` — set "
    "them to null if web_search cannot substantiate them with at least one "
    "authoritative source. Do NOT emit any _rocketreach_* flags. The "
    "renderer will surface an OSINT-only banner explaining the lower "
    "confidence to the operator."
    + _DEGRADED_SCAFFOLDING_REQUIREMENT
)

_DEGRADED_GUARD_COMPANY_MISS = (
    "PARTIAL RR MODE — RocketReach returned named-contact and/or "
    "exec-DMU data but NO company firmographics. Use the contact data "
    "as Tier-B with ᴿᴿ provenance (emit the relevant _rocketreach_* "
    "flags ONLY on the contact / DMU fields). Firmographics — "
    "`num_employees`, `revenue_estimate`, `techstack`, `industry_keywords`, "
    "`naics_codes`, `sic_codes`, `year_founded` — MUST come from web_search "
    "only; mark Tier-C; set to null if unsubstantiated. The renderer will "
    "surface an OSINT-only banner."
    + _DEGRADED_SCAFFOLDING_REQUIREMENT
)


def build_user_prompt(intake, preflight_data, rr_baseline, *,
                      rr_degraded=False, rr_degradation_reason=None):
    """Compose the user-side message with research-ready inputs.

    Returns a JSON string that the model parses to seed STEP 2 of the skill.
    The model has already done STEP 1 (intake) because we pass it pre-validated.

    When `rr_degraded=True`, prepends a `degraded_mode_guard` block at the
    top of the payload so the model adjusts its data-sourcing strategy.
    The variant is selected by `rr_degradation_reason`:
        - "rr_full_miss"    → forbid all firmographic claims unless web_search backed
        - "rr_company_miss" → keep contact data Tier-B, firmographics Tier-C only
    """
    import json

    payload = {}
    if rr_degraded:
        guard = (
            _DEGRADED_GUARD_FULL_MISS
            if rr_degradation_reason == "rr_full_miss"
            else _DEGRADED_GUARD_COMPANY_MISS
        )
        payload["degraded_mode_guard"] = guard
    payload.update({
        "task": "Generate a complete ELISS dossier JSON dict per the skill above.",
        "intake": {
            "name": intake.get("name"),
            "email": intake.get("email"),
            "linkedin_url": intake.get("linkedin_url"),
            "company_url": intake.get("company_url"),
            "notes": intake.get("notes"),
        },
        "preflight": preflight_data,
        "rr_baseline": rr_baseline,
        "output_contract": (
            "Output ONLY a JSON object. No prose before, no prose after. "
            "No markdown fences. The object MUST satisfy the constraints "
            "in the CRITICAL GENERATION CONSTRAINTS section of the system prompt."
        ),
    })
    return json.dumps(payload, indent=2, default=str)
