"""Subagent + parent-synthesis prompts for the heavy pipeline.

Ports the /eliss skill's STEP-2 Parallel Dispatch model (SKILL.md lines
185-299) into prompt templates that can be fired against the Anthropic
Messages API instead of the Claude Code `Agent` tool. Each subagent is
scope-narrow on purpose — Tech is forbidden from speculating about budget
authority, Behavioral is forbidden from inventing technology fingerprints —
so the parent synthesis call has a clean job: merge, don't reconcile.

Output shape contract: every subagent returns a JSON object only (no
narration, no fences). The parent receives the four fragments verbatim as
part of its user message and emits the canonical dossier JSON that
store_lead and generate_report already understand.
"""
import json
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Subagent system prompts
# ─────────────────────────────────────────────────────────────────────────────
#
# Each subagent gets a tight system prompt that:
#   1. Names its layer + the JSON keys it owns (no overlap with siblings)
#   2. Lists the search axes it should hit (and explicitly the ones it should
#      NOT hit — that's a different subagent's job)
#   3. Reminds it to cite Tier-A/B/C sources and to return JSON only
#   4. Caps web_search at the budget enforced by max_uses in fanout.py
#
# Why so prescriptive: with web_search enabled the model otherwise drifts into
# adjacent topics (a Tech subagent will start scoring compliance pressure
# because the search results mention HIPAA). Hard scope cuts that.

_SUBAGENT_OUTPUT_DISCIPLINE = """
OUTPUT DISCIPLINE — non-negotiable:
- Return RAW JSON only. No prose, no fences (no ```json), no preamble.
- All values are PLAIN SCALARS or arrays of scalars. Do NOT wrap values in
  {value, confidence, tier} dicts. Confidence belongs on each top-level field
  via a `_confidence` sibling key (e.g. "<field>_confidence": "high|medium|low").
- Cite every claim. Each fragment ends with a "sources" list:
    "sources": [{"url": str, "tier": "A"|"B"|"C", "note": str}]
  Tier-A = the company's own site, SEC EDGAR, official gov procurement.
  Tier-B = reputable trade press, analyst firms, Glassdoor/LinkedIn primary.
  Tier-C = aggregators, marketing pages, generic listicles.
- If you cannot evidence a claim within your web_search budget, OMIT the key
  instead of inventing a value. Empty is better than wrong.
"""


_SUBAGENT_SYSTEMS = {
    "tech": (
        "You are a B2B technology-stack analyst working as one of four parallel "
        "research subagents on an enterprise lead dossier. Your scope is TECH ONLY: "
        "the prospect's identity, access management posture, security tools, cloud "
        "stack, observability stack, and the competitive landscape against "
        "ManageEngine AD360 / Log360.\n\n"
        "SCOPE — keys you own in the output JSON (omit any you cannot evidence):\n"
        "  identity:\n"
        "    primary_idp                  (e.g. \"Azure AD\", \"Okta\", \"Ping\")\n"
        "    mfa_posture                  (\"enforced\"/\"partial\"/\"absent\"/\"unknown\")\n"
        "    privileged_access_tools      (list of strings)\n"
        "  security_stack:\n"
        "    siem_tools                   (list — e.g. [\"Splunk Enterprise\", \"Sentinel\"])\n"
        "    edr_tools                    (list)\n"
        "    other_security_tools         (list)\n"
        "  cloud:\n"
        "    primary_cloud                (\"AWS\"/\"Azure\"/\"GCP\"/\"hybrid\"/\"on-prem\"/\"unknown\")\n"
        "    cloud_posture_summary        (short string)\n"
        "  observability:\n"
        "    log_management_tools         (list)\n"
        "  competitors:\n"
        "    competitors_detected         (list of strings — direct AD360/Log360 alternatives)\n"
        "    displacement_angles          (list of short strings — why we displace them)\n"
        "  digital_maturity               (\"high\"/\"medium\"/\"low\")\n"
        "  ad_environment                 (short string describing AD topology)\n"
        "  evidence_summary               (string — 2-3 sentences citing key signals)\n\n"
        "SEARCH GUIDANCE — within your web_search budget, prioritize:\n"
        "  1. The company's careers page / job postings (mention of specific tools)\n"
        "  2. BuiltWith / Wappalyzer fingerprints on the company domain\n"
        "  3. Tech-trade-press coverage (CRN, ComputerWeekly, DarkReading) tying tools to this org\n"
        "  4. Conference talks / case studies by employees\n\n"
        "DO NOT speculate on budget authority, compliance pressure, executive\n"
        "personalities, or org structure — those are other subagents' lanes.\n"
        + _SUBAGENT_OUTPUT_DISCIPLINE
    ),

    "compliance": (
        "You are a B2B compliance + procurement analyst working as one of four "
        "parallel research subagents. Your scope is COMPLIANCE PRESSURE + "
        "PROCUREMENT CYCLE for this lead's organization.\n\n"
        "SCOPE — keys you own (use these EXACT key names — the renderer reads them literally):\n"
        "  compliance: [                         # list, one entry per framework — produce 3-5\n"
        "    {\n"
        "      framework:        str            # e.g. \"HIPAA Security Rule (2025 Update)\"\n"
        "      pressure:         \"HIGH\"|\"MEDIUM\"|\"LOW\"\n"
        "      urgency:          str            # 1-2 sentence prose: WHY this pressure\n"
        "      ad360_angle:      str            # ⚠ KEY NAME: ad360_angle (NOT ad360_fit). Short prose — how AD360 helps. 15-80 chars.\n"
        "      log360_angle:     str            # ⚠ KEY NAME: log360_angle. Short prose — how Log360 helps.\n"
        "      evidence:         str            # 1 sentence citing the source\n"
        "      evidence_urls:    [str]          # 1-3 URLs\n"
        "    }\n"
        "  ]\n"
        "  procurement_signals: [                # list of detected procurement triggers (renders into signals.positive[])\n"
        "    {type: str, description: str, source_url: str, observed_date: str, points: int}\n"
        "  ]\n"
        "  budget_analysis:                      # all dollar fields are STRINGS with $ prefix\n"
        "    estimated_it_spend     str   # clean dollar string e.g. \"$45M\" (NO tildes)\n"
        "    security_budget        str   # e.g. \"$6.8M (15% of IT)\"\n"
        "    affordability          str   # \"Strong|Adequate|Constrained|Unknown\" + 1 sentence\n"
        "    budget_trend           str   # \"Growing|Stable|Shrinking\" + 1 sentence\n"
        "    deal_authority         str   # who signs at this price point\n"
        "    deal_cycle_months      str   # e.g. \"6-9\"\n"
        "    calculation_basis      str   # 1-line note on how you estimated\n"
        "    estimated_deal_size    int   # USD integer — your best estimate of an AD360+Log360 deal\n"
        "    deal_size_basis        str   # 1 sentence — how you sized the deal\n"
        "    iam_iga_budget         int   # USD integer — ~12% of security_budget\n"
        "    siem_budget            int   # USD integer — ~15% of security_budget\n\n"
        "PROCUREMENT SIGNAL TYPES to hunt for: RFP/RFI publication, budget\n"
        "amendments, audit findings, federal grant awards, CISO/CIO speaking\n"
        "engagements, M&A activity, executive changes in security org,\n"
        "contract expirations on competing tools.\n\n"
        "SEARCH GUIDANCE — prioritize:\n"
        "  1. USAspending.gov + SAM.gov contract awards (for federal/SLED targets)\n"
        "  2. Recent 10-K / 10-Q filings (SEC EDGAR) — security-budget commentary\n"
        "  3. State audit reports, OIG findings, breach notification filings\n"
        "  4. Industry-specific regulator news (OCR for HIPAA, FTC, GLBA, NYDFS, etc.)\n\n"
        "DO NOT analyze the company's tech stack, exec backgrounds, or\n"
        "personality fit — those are other subagents' lanes.\n"
        + _SUBAGENT_OUTPUT_DISCIPLINE
    ),

    "org": (
        "You are a B2B org-intelligence analyst working as one of four parallel "
        "research subagents. Your scope is the DECISION-MAKING UNIT (DMU) and\n"
        "BUYING-CENTER POLITICS for this lead's organization.\n\n"
        "SCOPE — keys you own. ⚠ CRITICAL: emit DMU roles as FLAT keys at\n"
        "org_intelligence level, NOT nested under .dmu. Putting them under\n"
        ".dmu causes the renderer's DMU map to be empty.\n\n"
        "  org_intelligence:\n"
        "    # FLAT DMU role keys — each is a dict with name/title/confidence/linkedin/note\n"
        "    economic_buyer:        {name: str|null, title: str, confidence: \"CONFIRMED|INFERRED\",\n"
        "                            linkedin: str?, note: str}      # budget owner (CIO/CISO/City Mgr)\n"
        "    champion:              {name: str|null, title: str, email?: str, phone?: str,\n"
        "                            linkedin?: str, confidence: \"CONFIRMED|INFERRED\", note?: str}\n"
        "    technical_evaluator:   {name: str|null, title: str, linkedin?: str,\n"
        "                            confidence: \"CONFIRMED|INFERRED\"}  # runs the POC\n"
        "    blocker:               {name: str|null, title: str, confidence: \"INFERRED\"}\n"
        "    additional_stakeholders: [{role: str, name: str, title: str, relevance: str}]\n"
        "    future_stakeholders:   [{role: str, why: str, action: str}]  # OPEN reqs / unidentified\n"
        "    ghost_stakeholders:    [{title: str, why_matters: str}]      # silent influencers\n"
        "    multi_thread_strategy: str            # 1 sentence — how to work multiple stakeholders\n"
        "    reporting_structure:   str            # 1 sentence prose — who reports to whom\n"
        "    headcount_trend:       str            # \"growing|flat|shrinking\" + 1 sentence\n"
        "    open_security_reqs:    [{title: str, posted_date?: str, source_url: str}]\n"
        "    org_autonomy:          \"central|federated|local|unknown\"\n"
        "  lead:                                     # only the named lead in intake\n"
        "    name:        str\n"
        "    title:       str          # if unverified, write \"Title to be confirmed\" — NEVER \"Unknown\"\n"
        "    seniority:   \"C-Suite / Executive | Director / VP | Manager | IC\"\n"
        "    authority:   \"Economic Buyer | Champion | Technical Evaluator | Influencer\"\n"
        "    tenure:      str          # e.g. \"3 yrs at this co (Jan 2023–Present)\"\n"
        "    email:       str\n"
        "    linkedin_url: str?\n"
        "    location:    str?\n"
        "    personalization_hooks: [str]   # 2-3 specific hooks from career/posts/projects\n"
        "  company:\n"
        "    employees:   str          # e.g. \"6,320 (HQ) / ~36,000 managed\"\n"
        "    employees_confidence: \"CONFIRMED|ESTIMATED\"\n"
        "    revenue:     str          # clean dollar string, $-prefixed\n"
        "    hq:          str          # full address\n"
        "    ownership:   str          # e.g. \"Public sector / Municipal\"\n\n"
        "Inbound contact defaults to technical_evaluator UNLESS research confirms\n"
        "Director-level authority over IT/security budget. Vacant/unidentified roles\n"
        "with no person identified go in future_stakeholders[] ONLY (not as a DMU\n"
        "role with name=null) — the DMU map only renders a node when name is set.\n\n"
        "RR baseline data (named contact, exec DMU, departments) is provided in\n"
        "the user message — TREAT IT AS GROUND TRUTH and curate from it; use\n"
        "web_search only to fill gaps and validate.\n\n"
        "DO NOT touch tech stack, compliance, or behavioral profiling —\n"
        "other subagents' lanes.\n"
        + _SUBAGENT_OUTPUT_DISCIPLINE
    ),

    "behavioral": (
        "You are a B2B behavioral analyst working as one of four parallel "
        "research subagents. Your scope is the NAMED LEAD'S personalization "
        "surface — what they care about publicly, what they've said, what they've "
        "shipped, and how to credibly approach them.\n\n"
        "SCOPE — keys you own:\n"
        "  behavioral:\n"
        "    public_talks: [                         # conference talks, podcasts\n"
        "      {title: str, venue: str, year: str, url: str, summary: str}\n"
        "    ]\n"
        "    articles_authored: [\n"
        "      {title: str, publisher: str, year: str, url: str}\n"
        "    ]\n"
        "    open_source_activity?  str             # GitHub fingerprint if present\n"
        "    linkedin_recent_posts: [                # last 90 days, topic-tagged\n"
        "      {snippet: str, topic: str, posted_date: str, url?: str}\n"
        "    ]\n"
        "    career_arc_summary   str               # 1 paragraph\n"
        "    personality_signals  list[str]         # short observed traits\n"
        "  outreach:\n"
        "    voice              \"technical\"|\"executive\"|\"consultative\"\n"
        "    hooks: list[str]                        # 3-5 candidate first-line hooks\n"
        "    anti_patterns: list[str]                # what NOT to lead with (1-3)\n"
        "    cadence_advice     str                  # cadence + channel preference\n\n"
        "If the intake contains no named individual (company-only lead), return\n"
        "{} as your fragment — do not fabricate a behavioral profile.\n\n"
        "DO NOT speculate on org structure, tech stack, or compliance —\n"
        "other subagents' lanes.\n"
        + _SUBAGENT_OUTPUT_DISCIPLINE
    ),
}


# A single dict — fanout.py iterates over .items() to spawn subagents in
# parallel. The .name field on each spec is what shows up in per_subagent
# meta + log lines.
SUBAGENT_PROMPTS = {
    name: {"system": system, "name": name}
    for name, system in _SUBAGENT_SYSTEMS.items()
}


# ─────────────────────────────────────────────────────────────────────────────
# User-message builders
# ─────────────────────────────────────────────────────────────────────────────

def _trim_for_prompt(obj, max_chars=8000):
    """JSON-dump but clip very long branches so the prompt stays under control.

    Preflight data is small (~1-2K) but rr_baseline with bulk_lookup×20 can
    push 30K+ chars. Subagent prompts only need the salient fields; the full
    RR blob lives elsewhere and the renderer's RR-enrichment step backfills.
    """
    raw = json.dumps(obj, default=str, ensure_ascii=False)
    if len(raw) <= max_chars:
        return raw
    return raw[: max_chars - 30] + " /*…trimmed for prompt budget…*/"


def _rr_degradation_note(rr_degraded, rr_degradation_reason):
    if not rr_degraded:
        return ""
    if rr_degradation_reason == "rr_full_miss":
        return (
            "\n\nRR COVERAGE GAP — rr_baseline is fully unavailable for this org.\n"
            "Do NOT fabricate firmographic data (revenue, headcount, year_founded,\n"
            "industry codes, departments). Rely on preflight + web_search only.\n"
        )
    if rr_degradation_reason == "rr_company_miss":
        return (
            "\n\nRR COVERAGE GAP — RR has contact-level data but no firmographics.\n"
            "Use the named_contact / exec_dmu blocks as ground truth; do NOT invent\n"
            "company-level details (revenue, headcount, etc.) — leave them blank or\n"
            "source them explicitly from web_search and tag the evidence URL.\n"
        )
    return ""


def build_subagent_messages(spec, intake, preflight_data, rr_baseline,
                            *, rr_degraded=False, rr_degradation_reason=None):
    """Build the user message for one subagent.

    Each subagent gets:
      - the intake (so it knows who/what we're researching)
      - the preflight blob (free OSINT signal)
      - the RR baseline trimmed to its lane (full blob for org; firmographics
        + techstack for tech; firmographics + departments for compliance;
        named_contact for behavioral) — fanout.py passes the full blob and
        we trim here.
    """
    name = spec.get("name", "subagent")

    # Lane-specific RR trim. The org and tech subagents need more of it; the
    # behavioral lane only needs the named contact.
    rr_for_lane = None
    if rr_baseline:
        if name == "org":
            rr_for_lane = {
                "company": rr_baseline.get("company"),
                "named_contact": rr_baseline.get("named_contact"),
                "exec_dmu_enriched": rr_baseline.get("exec_dmu_enriched"),
                "exec_dmu_summary": rr_baseline.get("exec_dmu_summary"),
                "departments": rr_baseline.get("departments")
                                or (rr_baseline.get("company") or {}).get("departments_headcount"),
            }
        elif name == "tech":
            rr_for_lane = {
                "company": rr_baseline.get("company"),
                "techstack": (rr_baseline.get("company") or {}).get("techstack"),
            }
        elif name == "compliance":
            rr_for_lane = {
                "company": {
                    k: (rr_baseline.get("company") or {}).get(k)
                    for k in ("name", "industry", "naics_codes", "naics_code",
                              "sic_codes", "sic_code", "year_founded",
                              "employees", "revenue", "industry_keywords")
                },
            }
        elif name == "behavioral":
            rr_for_lane = {
                "named_contact": rr_baseline.get("named_contact"),
            }
        else:
            rr_for_lane = rr_baseline

    user_payload = {
        "intake": intake,
        "preflight": preflight_data,
        "rr_baseline_for_lane": rr_for_lane,
    }
    body = (
        f"# Research request — lane: {name}\n\n"
        f"You are the **{name}** subagent. Stick to your lane. Return a JSON "
        f"fragment matching the keys listed in your system prompt.\n\n"
        f"## Input\n```json\n{_trim_for_prompt(user_payload, max_chars=12000)}\n```"
        f"{_rr_degradation_note(rr_degraded, rr_degradation_reason)}\n\n"
        f"Use web_search up to your budget cap. When you're done, emit the JSON "
        f"fragment. No prose around it."
    )
    return [{"role": "user", "content": body}]


# Concrete schema enumeration injected into the parent prompt. Lifted from the
# light skill's references/dossier-schema.md so the parent can't drift away from
# the renderer contract. Every key name here is what `generate_report.py` reads
# verbatim — typos render as silent empty sections in the HTML.
REQUIRED_DOSSIER_SHAPE = r"""
## EMIT-ORDER PRIORITY (read this BEFORE the schema)

Emit keys in EXACTLY the order below. If you sense your output is approaching
token budget, NEVER drop a key from the first 9 priorities — those power the
renderer's required sections. The later sections are valuable but recoverable.

**Priority 1 — must always be present** (renderer breaks visibly without these):
  1. `meta`
  2. `data_quality`
  3. `sources`
  4. `full_dossier_markdown`
  5. `executive_brief`
  6. `scoring`
  7. `lead`
  8. `company`
  9. `org_intelligence`

**Priority 2 — must be present for HOT/WARM tiers:**
 10. `technology`
 11. `compliance`
 12. `budget_analysis`
 13. `demo_playbook`
 14. `signals`
 15. `pre_mortem`
 16. `rep_readiness_checklist`
 17. `recommendations`
 18. `recommended_outreach`

## REQUIRED DOSSIER SHAPE (emit every key — renderer reads these verbatim)

```json
{
  "meta": {
    "version":   "heavy-8.0.0",
    "generated": "YYYY-MM-DD",
    "rocketreach_budget": {"session_totals": {"person_lookups": N, "company_lookups": M}}
  },

  "data_quality": {
    "overall_confidence": "HIGH|MEDIUM|LOW",
    "assumptions": [
      "3-6 specific assumptions e.g. 'IT budget estimated at 3% of general fund per municipal benchmark'",
      "..."
    ],
    "gaps": [
      "3-6 specific gaps e.g. 'No incumbent SIEM surfaced — could be greenfield OR hidden legacy'",
      "..."
    ],
    "sources_actually_checked": [
      {"source": "preflight.dns",                "access_method": "preflight",       "layer": 1, "yielded_signal": true},
      {"source": "preflight.microsoft_tenant",   "access_method": "preflight",       "layer": 2, "yielded_signal": false},
      {"source": "preflight.web_fingerprint",    "access_method": "preflight",       "layer": 2, "yielded_signal": true},
      {"source": "preflight.crt_sh",             "access_method": "preflight",       "layer": 2, "yielded_signal": true},
      {"source": "preflight.otx",                "access_method": "preflight",       "layer": 3, "yielded_signal": true},
      {"source": "preflight.sec_edgar",          "access_method": "preflight",       "layer": 4, "yielded_signal": false},
      {"source": "preflight.usaspending",        "access_method": "preflight",       "layer": 4, "yielded_signal": true},
      {"source": "RocketReach /account",         "access_method": "rocketreach_api", "layer": 5, "yielded_signal": true},
      {"source": "RocketReach /company/lookup",  "access_method": "rocketreach_api", "layer": 5, "yielded_signal": true},
      {"source": "RocketReach /person/search",   "access_method": "rocketreach_api", "layer": 5, "yielded_signal": true},
      {"source": "RocketReach /bulkLookup",      "access_method": "rocketreach_api", "layer": 5, "yielded_signal": true},
      {"source": "web_search '<your actual query 1>'", "access_method": "web_search", "layer": 3, "yielded_signal": true},
      {"source": "web_search '<actual query 2>'",       "access_method": "web_search", "layer": 4, "yielded_signal": true},
      {"source": "web_search '<actual query 3>'",       "access_method": "web_search", "layer": 6, "yielded_signal": false}
    ]
  },

  "sources": {
    "Company":    [{"url": "https://...", "tier": "A|B|C", "label": "1-5 word description"}],
    "Person":     [{"url": "https://www.linkedin.com/in/...", "tier": "B", "label": "LinkedIn profile"}],
    "Technology": [{"url": "...", "tier": "B", "label": "..."}],
    "Financial":  [{"url": "...", "tier": "A", "label": "..."}],
    "Compliance": [{"url": "...", "tier": "A", "label": "..."}]
  },
  // sources REQUIREMENT: aim for >= 10 total URLs across categories. Pull every
  // citation URL from your 4 subagent fragments (each fragment has a sources[]
  // list) plus the preflight signals' source URLs plus any RR-provided links.
  // NEVER emit "sources": {} or omit this key.

  "full_dossier_markdown": "MULTI-THOUSAND-CHAR PROSE — see Tab 2 section below for required content.",
  // full_dossier_markdown REQUIREMENT: 8000-15000 chars of markdown prose.
  // MUST cover EVERY Tab 2 section in order: Score Summary, Executive Brief,
  // Person Profile, Company Profile, Technology + Competitive Matrix, Org
  // Intelligence + Ghost Stakeholders, Budget, Compliance, Buying Signals,
  // Deal Execution Risks, Scoring Rationale, Strategic Recs, Pre-Mortem,
  // Rep Readiness, Research Sources. Use markdown headings (##, ###), bullet
  // lists, and column-0 callouts (e.g. `**Why:**`, `**Action:**`, `**Trigger:**`
  // — NEVER preceded by `>` which renders as a blockquote instead of a callout).
  // Cite every claim with the source's [A] / [B] / [C] tier marker inline.

  "executive_brief": "200-400 char string. WHO + WHAT environment + WHY now + WHAT's missing. Cite a specific fact, not generic prose.",

  "scoring": {
    "tier": "HOT|WARM|COOL|COLD",
    "final_score": 68,
    "composite": 68,
    "overall_confidence": "HIGH|MEDIUM|LOW",
    "icp_match": "Strong|Moderate|Weak",
    "icp_match_reason": "one sentence explaining the rating",
    "fit":    {"score": 18, "confidence": "MEDIUM"},
    "intent": {"score": 16, "confidence": "MEDIUM",
               "signals": [{"category": "Compliance Need", "points": 10, "evidence": "..."}]},
    "timing": {"score": 20, "confidence": "MEDIUM"},
    "budget": {"score": 14, "confidence": "MEDIUM"},
    "risk_adjusted_composite": 64,
    "negative_modifiers":   [{"modifier": "label", "points": -8}],
    "deal_execution_risks": [{"risk": "label", "adjustment": -3}],
    "total_risk_adjustment": -4,
    "recommended_action": "PURSUE NOW|MONITOR|NURTURE|PASS",
    "scenarios": [
      {"label": "trigger label", "delta": 6, "before_score": 64, "after_score": 70,
       "before_tier": "WARM", "after_tier": "HOT", "kind": "positive|negative|pivot",
       "logic": "1-2 sentence rationale",
       "trigger": "what the rep would literally hear on a call"}
    ]
  },

  "lead": {
    "name": "...", "title": "...",
    "seniority": "C-Suite / Executive | Director / VP | Manager | IC",
    "authority": "Economic Buyer | Champion | Technical Evaluator | Influencer",
    "tenure": "e.g. \"3 yrs at this co (Jan 2023–Present); 25 yrs in IT director/CIO roles\"",
    "email": "...", "linkedin_url": "...", "location": "...",
    "personalization_hooks": ["specific hook 1", "specific hook 2", "..."]
  },

  "company": {
    "name": "...",
    "industry": "...",
    "employees": "string with confidence note",
    "employees_confidence": "CONFIRMED|ESTIMATED",
    "revenue": "$-prefixed string e.g. \"$84M\"",
    "hq": "full address string",
    "ownership": "Public|Private|Government|..."
  },

  "org_intelligence": {
    "economic_buyer":      {"name": "...", "title": "...", "confidence": "CONFIRMED|INFERRED",
                            "linkedin": "...", "note": "..."},
    "champion":            {"name": "...", "title": "...", "email": "...", "phone": "...",
                            "linkedin": "...", "confidence": "CONFIRMED|INFERRED"},
    "technical_evaluator": {"name": "...", "title": "...", "linkedin": "...",
                            "confidence": "CONFIRMED|INFERRED"},
    "blocker":             {"name": "...", "title": "...", "confidence": "INFERRED"},
    "additional_stakeholders": [{"role": "...", "name": "...", "title": "...", "relevance": "..."}],
    "future_stakeholders":     [{"role": "...", "why": "...", "action": "..."}],
    "ghost_stakeholders":      [{"title": "...", "why_matters": "..."}],
    "multi_thread_strategy": "1 sentence",
    "headcount_trend": "..."
  },

  "technology": {
    "ad_environment": "...", "cloud_posture": "...", "digital_maturity": "...",
    "security_stack":       ["pill 1", "pill 2"],
    "competitors_detected": ["competitor 1"],
    "displacement_angle":   "1-2 sentence strategy note",
    "competitive_readiness_score": 7,
    "competitive_readiness_basis": "1-2 sentence rationale naming the incumbent + displacement angle",
    "competitive_threat_matrix": [
      {"competitor": "Splunk", "presence_likelihood": "Likely|Possible|Unlikely",
       "basis": "evidence text", "basis_urls": [], "displacement_angle": "...",
       "threat_level": "Critical|Moderate|Low"}
    ],
    "renewal_intelligence": [
      {"incumbent": "Splunk", "estimated_renewal_window": "Q2-Q4 2027",
       "confidence": "CONFIRMED|INFERRED|ESTIMATED",
       "basis": "1-sentence cite", "timing_trigger": "imminent|strong|moderate|lockout"}
    ]
  },

  "compliance": [
    {"framework": "...", "pressure": "HIGH|MEDIUM|LOW",
     "urgency": "...",
     "ad360_angle":  "short prose — how AD360 helps (NOT HIGH/MED/LOW)",
     "log360_angle": "short prose — how Log360 helps",
     "evidence": "1 sentence citing the source", "evidence_urls": ["..."]}
  ],

  "budget_analysis": {
    "estimated_it_spend": "$900K", "security_budget": "$180K (20% of IT)",
    "affordability": "constrained|adequate|strong", "budget_trend": "growing|flat|shrinking",
    "deal_authority": "...", "deal_cycle_months": "6-9",
    "calculation_basis": "...",
    "estimated_deal_size": 50000, "deal_size_basis": "...",
    "iam_iga_budget": 21600, "siem_budget": 27000
  },

  "demo_playbook": {
    "persona": "Role + 1-2 sentence operating context",
    "opening_hook": "90-second cold open — dossier-grounded reframe",
    "ad360": {
      "value_moments": [
        {"title": "specific moment title",
         "why_it_matters": "tied to a specific dossier fact",
         "tell_show_tell": "Tell: claim. Show: the one screen. Tell: takeaway."}
      ],
      "discovery_questions": ["..."],
      "top_objections": [{"objection": "...", "response": "..."}],
      "cta": "specific micro-commitment"
    },
    "log360": { "...same shape as ad360..." }
  },

  "signals": {
    "positive": [
      {"signal": "...", "signal_category": "compliance_deadline|tech_investment|...",
       "points": 10, "age_days": 0, "source": "...", "confidence": "HIGH",
       "evidence": "...", "evidence_urls": []}
    ],
    "negative": [
      {"flag": "...", "signal_category": "budget_pressure|...",
       "impact": -8, "age_days": 0, "source": "...", "evidence": "...", "evidence_urls": []}
    ]
  },

  "pre_mortem": [
    {"scenario": "label", "why_it_could_happen": "explanation",
     "evidence_urls": [], "mitigation": "how to prevent",
     "earliest_signal": "first observable sign this scenario is developing"}
  ],

  "rep_readiness_checklist": [
    "5-8 specific items the rep must verify or prepare before the first call",
    "..."
  ],

  "recommendations": {
    "action": "PURSUE NOW|MONITOR|NURTURE|PASS",
    "next_steps": ["Step 1: ...", "Step 2: ...", "Step 3: ..."],
    "ad360_talking_points":  ["..."],
    "log360_talking_points": ["..."],
    "objections": [{"objection": "...", "response": "..."}],
    "outreach": {"channel": "Email + LinkedIn", "timing": "Within 5 business days",
                 "hook": "..."},
    "decision_tree": {
      "root_question": "...",
      "branches": [{"signal": "...", "action": "..."}]
    }
  },

  "recommended_outreach": [
    {"slot": 1, "template_name": "Compliance Gap", "template_id": "compliance_gap",
     "voice": "technical|executive|consultative",
     "triggered_by": ["..."], "subject": "...", "body": "...",
     "rationale": "Why this template for this prospect"}
  ]
}
```
"""


def build_parent_synthesis_messages(fragments, intake, preflight_data, rr_baseline,
                                    *, rr_degraded=False, rr_degradation_reason=None):
    """Build the parent's user message — receives the 4 fragments + the inputs."""
    # Mark missing fragments so the parent knows the dossier will be partial.
    fragment_block = {
        "tech": fragments.get("tech") or {"_missing": True},
        "compliance": fragments.get("compliance") or {"_missing": True},
        "org": fragments.get("org") or {"_missing": True},
        "behavioral": fragments.get("behavioral") or {"_missing": True},
    }
    payload = {
        "intake": intake,
        "preflight": preflight_data,
        "rr_baseline": rr_baseline,
        "subagent_fragments": fragment_block,
        "rr_degraded": rr_degraded,
        "rr_degradation_reason": rr_degradation_reason,
    }

    body = (
        "# Parent synthesis — emit the COMPLETE canonical ELISS dossier JSON.\n\n"
        "You are the consolidator. Four subagents (tech, compliance, org, behavioral) "
        "have returned JSON fragments. Merge them with intake + preflight + RR "
        "baseline into the dossier JSON that `generate_report.py` renders. The same "
        "renderer is used by the light pipeline — wrong key names produce silently "
        "empty sections in the HTML.\n\n"
        "## Inputs\n"
        f"```json\n{_trim_for_prompt(payload, max_chars=80000)}\n```\n\n"
        + REQUIRED_DOSSIER_SHAPE
        + "\n## Rules\n"
        "1. EMIT KEYS IN THE PRIORITY ORDER given above. The first 9 priority keys "
        "(meta, data_quality, sources, full_dossier_markdown, executive_brief, "
        "scoring, lead, company, org_intelligence) are non-negotiable — emit them "
        "FIRST, before anything else, so they survive even if your output is "
        "truncated. NEVER emit `\"sources\": {}` or omit any priority-1 key.\n"
        "2. EMIT EVERY required slot above. If a fragment was `_missing` or its data "
        "was thin, fill the gap from preflight + RR + intake using INFERENCE — but "
        "do NOT invent specific facts (names, $ amounts, dates). Acknowledge thin "
        "areas in `data_quality.gaps[]` and adjust `data_quality.overall_confidence` "
        "to MEDIUM or LOW.\n"
        "3. SCORING is yours alone. Use the rubric: fit (0-25), intent (0-25), "
        "timing (0-30), budget (0-20). final_score = sum minus risk adjustments. "
        "Each dimension is a `{score: int, confidence: \"HIGH|MEDIUM|LOW\"}` dict "
        "EMITTED FLAT under `scoring` — NOT nested under `scoring.dimensions`. "
        "Match the schema in the section above byte-for-byte.\n"
        "4. KEY NAMES MATTER: compliance rows use `ad360_angle`/`log360_angle` "
        "(NOT `_fit`); ICP uses `icp_match`+`icp_match_reason` (NOT `icp_rating`); "
        "DMU roles are FLAT under `org_intelligence` (NOT under `.dmu`); "
        "verdict is `scoring.recommended_action`+`recommendations.action`; "
        "company uses `hq` (NOT `headquarters`), `revenue` (NOT `revenue_estimate`), "
        "`employees` (NOT `num_employees_*`).\n"
        "5. For HOT/WARM tiers (final_score >= 50), `scoring.scenarios[]` is "
        "REQUIRED — emit at minimum 3 cards (one positive, one negative, one "
        "pivot). `before_score` must equal `risk_adjusted_composite`.\n"
        "6. `pre_mortem[]` is REQUIRED — 3 distinct loss scenarios grounded in the "
        "actual dossier facts. `rep_readiness_checklist[]` is REQUIRED — 5-8 items. "
        "`recommendations` is REQUIRED — action + next_steps + ad360_talking_points "
        "+ log360_talking_points + objections + decision_tree.\n"
        "7. `demo_playbook.{ad360,log360}.value_moments[]` — each value moment is "
        "`{title, why_it_matters, tell_show_tell}`. NOT a placeholder; tie each to "
        "a specific dossier fact.\n"
        "8. `sources` top-level: NON-NEGOTIABLE. For EVERY URL the 4 subagent "
        "fragments cited (in their `sources` lists), every preflight source URL, "
        "and every RR-provided link — drop it under the appropriate category "
        "(Company/Person/Technology/Financial/Compliance) with a tier letter "
        "A/B/C. Aim for ≥10 total. NEVER emit `\"sources\": {}` — that renders "
        "as \"No sources cited.\" in Tab 2 and breaks the Source Quality donut.\n"
        "9. `full_dossier_markdown`: NON-NEGOTIABLE. 8000-15000 chars of dense "
        "markdown prose. Section headers using ## and ###. Cover in order: "
        "(1) Score Summary, (2) Executive Brief, (3) Person Profile, "
        "(4) Company Profile, (5) Technology + Competitive Matrix, "
        "(6) Org Intelligence + Ghost Stakeholders, (7) Budget, "
        "(8) Compliance, (9) Buying Signals, (10) Deal Execution Risks, "
        "(11) Scoring Rationale, (12) Strategic Recs, (13) Pre-Mortem, "
        "(14) Rep Readiness, (15) Research Sources. Callouts open at column "
        "0 with `**Why:**`, `**Action:**`, `**Trigger:**` — NEVER `> **Why:**`. "
        "Cite Tier letters [A]/[B]/[C] inline after each evidence sentence.\n"
        "10. `data_quality`: NON-NEGOTIABLE. Must contain `overall_confidence`, "
        "3-6 `assumptions[]`, 3-6 `gaps[]`, and `sources_actually_checked[]` "
        "with ≥10 entries (preflight + RR + each web_search the subagents ran).\n"
        "11. Apply the system-prompt's CRITICAL GENERATION CONSTRAINTS exactly: Tab 1 "
        "dict-unwrap discipline, flat top-level scoring keys, compliance pressure "
        "HIGH/MEDIUM/LOW, dollar strings without tildes.\n"
        "12. Output RAW JSON only — no prose, no ```json fences, no trailing "
        "commentary. The full response is parsed by `JSONDecoder.raw_decode`.\n"
    )
    return [{"role": "user", "content": body}]
