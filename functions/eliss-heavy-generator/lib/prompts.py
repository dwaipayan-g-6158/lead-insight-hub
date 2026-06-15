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


# ─────────────────────────────────────────────────────────────────────────────
# v7.5 (heavy) Mom Test Discipline — embedded directly into subagent prompts.
# /eliss SKILL.md ports STEP-2 Parallel Dispatch model to Claude Code Agents
# that can read references/{vertical-playbook,mom-test-discipline}.md at run
# time. The heavy fork calls the Anthropic Messages API directly — the model
# CANNOT read files — so the discipline contract must be inlined verbatim
# here.  This block is appended to each subagent system prompt.
_MT_DISCIPLINE = """

MOM TEST DISCIPLINE (v7.5+ — book "The Mom Test" by Rob Fitzpatrick):
- Every pain/problem/risk you cite MUST tie to a concrete URL, filing, hiring
  event, or news date. Unsourced inferences go into `assumptions[]`, not
  `signals.positive[]`.
- Speak the prospect's operational language, not the vendor's. Banking →
  examination cycle, MRA, FFIEC, change-window. Healthcare → downtime drill,
  break-the-glass, OCR portal, JCo survey. Manufacturing → MES, OEE, takt
  time, OTIF, line-stop. Avoid: "I noticed your company...", "Are you
  currently struggling with...", "How important is X to your business?", any
  "would you ever / do you usually" hypothetical, and any feature-pitching
  language. These banned phrasings fire the depth-lint gate on HOT.
- Pair every evidence-backed pain with its `obstacle` (what blocks resolution
  — examiner queue, turnaround calendar, parent platform mandate) and
  `workaround` (the makeshift current solution — manual CSV reconciliation,
  shared service account, scheduled SQL scripts). The workaround IS the
  earlyvangelist test #4 (book p72) and the single most actionable evidence.
- Signal taxonomy (book p105, p118): annotate each signal with a
  `signal_symbol` ∈ {⚡ pain, ⚓ goal, ☐ obstacle, ⤴ workaround,
  ^ background, ☑ purchasing, $ money, ♀ key-person}.
"""


_MT_TECH = """

MOM TEST FIELDS (v7.5+, REQUIRED):
- company.micro_segment — a who-where slice (e.g. "regional bank, 50–200
  branches, mid core-consolidation, OCC-examined"), NOT the bare vertical
  name. Book Ch7 p93: "If you aren't finding consistent problems and goals,
  you don't yet have a specific enough customer segment."
- company.operating_model — 2-3 sentences in customer language: team size,
  shift coverage (24x5? 24x7? business hours?), where IAM/PAM ownership sits,
  change-window cadence, approval chain. Pull from job postings + RR
  departments + Glassdoor.
"""


_MT_COMPLIANCE = """

MOM TEST FIELDS (v7.5+, REQUIRED):
- Every signals.positive[] entry you produce includes:
  * `id` — stable hyphen-prefixed slug (e.g., "sig-001")
  * `signal_symbol` ∈ {⚡, ⚓, ☐, ⤴, ^, ☑, $, ♀}
  * For pain/obstacle signals (⚡ or ☐): `obstacle` + `workaround` pair.
    The workaround IS the earlyvangelist test #4 (book p72). If the
    obstacle/workaround cannot be inferred from the harvest, set
    workaround="insufficient evidence — must_ask_live".
  * `evidence_strength` ∈ {"sourced", "inferred", "assumed"}.
- Emit a top-level `signals.evidence_index` map: `{ "<sig_id>": "sourced" |
  "inferred" | "assumed" }`. Renderer pills inferred/assumed claims.
"""


_MT_ORG = """

MOM TEST FIELDS (v7.5+, REQUIRED):
- org_intelligence.representative_pain_owner — the operator who actually
  LIVES the pain, distinct from economic_buyer. For IAM at a regional bank:
  economic_buyer = CIO/CISO; representative_pain_owner = IAM Architect or
  Identity Engineering lead running the manual access-review reconciliation.
  Book Ch7 p97 — talking to the pain-owner first is faster, more candid,
  more specific. Shape: {name, title, why, source_url}.  The `why` is one
  sentence describing what they do day-to-day that puts them at the pain.
- signals.last_90_days_timeline[] — chronological list of dated real events
  in the last 90 days, each {date: "YYYY-MM-DD", event, source_url, category,
  evidence_strength}. Categories aligned with the existing signal_category
  taxonomy. Powers the Tab 1 Last-90-Days Timeline card.  Empty on HOT/WARM
  fires the depth-lint gate.
"""


_MT_BEHAVIORAL = """

MOM TEST FIELDS (v7.5+, REQUIRED):
- Every lead.personalization_hooks[] entry MUST cite a specific source
  artifact: a conference talk title + URL, an article + URL, a GitHub repo +
  URL, a podcast episode + URL, or a LinkedIn post + URL. Generic hooks
  ("attended cyber conferences", "interested in zero trust") are useless —
  the rep needs a specific thing they can name.  If only RR-sourced skills
  are available, frame each as a discussion anchor with the URL the RR
  baseline carries.
- Flag which murky-must-learn questions could PLAUSIBLY be answered through
  a peer-to-peer call (reference call with someone in the contact's network).
  The parent synthesizes the final rep_list_of_3.
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
        + _MT_DISCIPLINE
        + _MT_TECH
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
        + _MT_DISCIPLINE
        + _MT_COMPLIANCE
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
        + _MT_DISCIPLINE
        + _MT_ORG
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
        + _MT_DISCIPLINE
        + _MT_BEHAVIORAL
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
                            *, rr_degraded=False, rr_degradation_reason=None,
                            payload_max_chars=12000):
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
        f"## Input\n```json\n{_trim_for_prompt(user_payload, max_chars=payload_max_chars)}\n```"
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
    "earlyvangelist": {
      // Mom Test v7.5+ — book p72 4-pip scorecard. has_makeshift_solution.evidence
      // MUST cite the workaround from signals.positive[].workaround.
      "has_problem":            {"value": true,  "evidence": "...", "source_url": "..."},
      "knows_problem":          {"value": true,  "evidence": "...", "source_url": "..."},
      "has_budget":             {"value": false, "evidence": "...", "source_url": null},
      "has_makeshift_solution": {"value": true,  "evidence": "...", "source_url": null},
      "count": 3,
      "rationale": "3/4 — HOT-worthy; budget is the missing pip."
    },
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
    "ownership": "Public|Private|Government|...",
    "micro_segment": "Mom Test v7.5+: who-where slice (e.g. 'regional bank, 50-200 branches, mid core-consolidation, OCC-examined'). NEVER the bare vertical name.",
    "operating_model": "Mom Test v7.5+: 2-3 sentences in customer language describing day-to-day operating reality."
  },

  // v7.5+ Mom Test top-level `data` block — REQUIRED for HOT/WARM tiers
  "data": {
    "industry_operational_lens": "One paragraph (~80-120 words) in customer language, anchored on company.micro_segment, framing what system availability/identity/audit actually MEANS to this prospect. MUST use customer-language terms from the matched vertical (banking → 'examination cycle', healthcare → 'downtime drill', manufacturing → 'line-stop', etc.).",
    "discovery_discipline": {
      "zoom_strategy": "zoom_now | confirm_category_first",
      "zoom_rationale": "Why this zoom_strategy.",
      "good_questions": [
        {"question": "...", "template": "Talk me through the last time…|How are you dealing with it now?|What are the implications of that?|What else have you tried?|Where does the money come from?", "anchor_fact_ref": "signals.positive[sig-005]"}
      ],
      "bad_questions": [
        {"question": "Do you think it's a good idea?", "why_bad": "people lie to be nice (book p14)"}
      ],
      "anti_patterns": [
        "'I noticed your company...' — feature-rep boilerplate; banned in opening_hook.",
        "A compliment is not a buying signal (book Ch5)."
      ]
    },
    "rep_list_of_3": [
      {"question": "...", "why_it_matters": "...", "dmu_role": "representative_pain_owner|economic_buyer|champion"}
    ],
    "research_vs_ask": {
      "settled_by_research": [{"fact": "...", "source_url": "..."}],
      "must_ask_live":        [{"question": "...", "why_unsettleable": "..."}]
    },
    "deal_premortem": {
      "if_lost": "Single most likely loss scenario in one sentence (book p101).",
      "must_be_true_to_win": ["3-5 success preconditions"]
    }
  },

  "org_intelligence": {
    "economic_buyer":      {"name": "...", "title": "...", "confidence": "CONFIRMED|INFERRED",
                            "linkedin": "...", "note": "..."},
    "champion":            {"name": "...", "title": "...", "email": "...", "phone": "...",
                            "linkedin": "...", "confidence": "CONFIRMED|INFERRED"},
    "technical_evaluator": {"name": "...", "title": "...", "linkedin": "...",
                            "confidence": "CONFIRMED|INFERRED"},
    "blocker":             {"name": "...", "title": "...", "confidence": "INFERRED"},
    // Mom Test v7.5+ (book Ch7 p97) — the operator who actually LIVES the pain,
    // distinct from economic_buyer. For IAM at a regional bank: pain_owner = IAM
    // Architect running the manual reconciliation; economic_buyer = CIO/CISO.
    "representative_pain_owner": {"name": "...", "title": "...", "why": "1 sentence describing day-to-day pain", "source_url": "..."},
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
      // Mom Test v7.5+: each entry includes `id` (stable slug), `signal_symbol`
      // ∈ {⚡ pain, ⚓ goal, ☐ obstacle, ⤴ workaround, ^ background, ☑ purchasing,
      // $ money, ♀ key-person}, and — for pain/obstacle signals — an
      // `obstacle` + `workaround` pair (book p105; workaround IS earlyvangelist
      // test #4).
      {"id": "sig-001", "signal": "...", "signal_symbol": "⚡",
       "signal_category": "compliance_deadline|tech_investment|...",
       "points": 10, "age_days": 0, "source": "...", "confidence": "HIGH",
       "evidence": "...", "evidence_urls": [],
       "obstacle": "what blocks them from solving — policy/contract/budget/legacy",
       "workaround": "the makeshift current solution"}
    ],
    "negative": [
      {"flag": "...", "signal_category": "budget_pressure|...",
       "impact": -8, "age_days": 0, "source": "...", "evidence": "...", "evidence_urls": []}
    ],
    // Mom Test v7.5+ — last-90-days chronological event list. Powers the
    // Tab 1 Last-90-Days Timeline card. Empty on HOT/WARM fires depth-lint.
    "last_90_days_timeline": [
      {"date": "YYYY-MM-DD", "event": "...", "source_url": "...", "category": "audit_finding|hiring|budget_event|...", "evidence_strength": "sourced"}
    ],
    // Mom Test v7.5+ — evidence_strength map keyed by signal `id`. Renderer
    // surfaces a soft confidence pill (inferred=yellow, assumed=gray) for
    // any signal whose strength is below 'sourced'.
    "evidence_index": {"sig-001": "sourced", "sig-002": "inferred"}
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
    // Mom Test v7.5+ (book Ch6 p83-87) — VFWPA outreach beats + Advisory Flip.
    // Renderer prefers these when populated; falls back to legacy `hook`.
    "outreach": {
      "channel": "Email + LinkedIn", "timing": "Within 5 business days",
      "hook": "legacy single-line hook (retained for backward compat)",
      "advisory_posture": "One line: 'You are calling on a regional bank as a ManageEngine PAM/SIEM advisor, not pitching a tool.'",
      "vision":   "What the world looks like once the operational problem is solved — in customer language.",
      "framing":  "Industry advisor, not vendor. Why this conversation is worth their 30 minutes.",
      "weakness": "What you do NOT yet know about the prospect; what you're hoping to learn.",
      "pedestal": "Why THEY specifically — their operational depth, unique view from a representative pain-owner seat.",
      "ask":      "CONCRETE advancement in time, reputation, or cash. A compliment is NOT advancement (book Ch5)."
    },
    "decision_tree": {
      "root_question": "...",
      "branches": [{"signal": "...", "action": "..."}]
    }
  },

  // Mom Test v7.5+ — deal pre-mortem (book p101). Layered over, NOT replacing,
  // pre_mortem[] above. Note this lives inside `data.deal_premortem` per the
  // schema shown earlier in the `data` block — repeated here only as a
  // reminder so it isn't omitted.

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
                                    *, rr_degraded=False, rr_degradation_reason=None,
                                    payload_max_chars=80000):
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
        f"```json\n{_trim_for_prompt(payload, max_chars=payload_max_chars)}\n```\n\n"
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
        "12. MOM TEST DISCIPLINE (v7.5+, REQUIRED for HOT/WARM tiers — book "
        "'The Mom Test' by Rob Fitzpatrick):\n"
        "    (a) Populate the top-level `data` block: `industry_operational_lens` "
        "(one paragraph in customer language, anchored on company.micro_segment, "
        "framing what system availability/identity/audit MEANS to this prospect "
        "— banking uses 'examination cycle/MRA', healthcare 'downtime drill/OCR "
        "portal', manufacturing 'line-stop/OTIF', etc.), `discovery_discipline` "
        "(zoom_strategy + good_questions[] templated from book's real templates: "
        "'Talk me through the last…' / 'How are you dealing with it now?' / "
        "'What are the implications of that?' / 'Where does the money come from?' "
        "+ bad_questions[] from book's verbatim bad-question bank + "
        "anti_patterns[]), `rep_list_of_3` (book p54 — 3 prioritized live "
        "questions only the conversation can settle, each tied to a dmu_role), "
        "`research_vs_ask` (settled_by_research[] with source_url + must_ask_live[] "
        "with why_unsettleable — book p116 cheatsheet, this is the dossier's "
        "spine), and `deal_premortem` ({if_lost, must_be_true_to_win[]} per "
        "book p101).\n"
        "    (b) Populate `scoring.earlyvangelist` — 4 booleans "
        "(has_problem/knows_problem/has_budget/has_makeshift_solution), each "
        "{value, evidence, source_url}, plus count + rationale (book p72). "
        "`has_makeshift_solution.evidence` MUST cite a workaround from "
        "signals.positive[].workaround.\n"
        "    (c) Populate `recommendations.outreach.{vision, framing, weakness, "
        "pedestal, ask, advisory_posture}` — the book's VFWPA mnemonic "
        "(Ch6 p83-87) + the Advisory Flip (Ch6 p87). `ask` MUST specify a "
        "concrete advancement currency (time, reputation, cash). A compliment "
        "is NOT advancement (book Ch5).\n"
        "    (d) Populate `org_intelligence.representative_pain_owner` — the "
        "operator who actually LIVES the pain, distinct from economic_buyer "
        "(book Ch7 p97).\n"
        "    (e) Each `signals.positive[]` entry gets `id` + `signal_symbol` "
        "(⚡⚓☐⤴^☑$♀ per book p105/p118). Pain/obstacle signals also get "
        "`obstacle` + `workaround` pairs. Add a top-level `signals.evidence_index` "
        "map keyed by signal id.\n"
        "    (f) Populate `signals.last_90_days_timeline[]` — chronological "
        "dated events from the harvest. Empty on HOT/WARM fires depth-lint.\n"
        "    (g) Populate `company.micro_segment` (who-where slice, NEVER the "
        "bare vertical) + `company.operating_model` (2-3 sentences in customer "
        "language). Book Ch7 p93.\n"
        "    (h) `demo_playbook.{ad360,log360}.discovery_anchors[]` — sibling to "
        "discovery_questions[], indexed identically. Each anchor "
        "{anchor_fact, source_url} cites the dossier fact that justifies the "
        "question. HOT requires 1:1 coverage; WARM requires ≥50%.\n"
        "    (i) Banned phrasings in opening_hook / outreach.hook|vision|framing|ask "
        "(case-insensitive scan, fires depth-lint on HOT): 'I noticed your "
        "company...', 'Are you currently struggling with...', 'Do you need "
        "better visibility into...', 'Would you ever consider...', 'How "
        "important is X to your business?', 'Hope this email finds you well', "
        "'Just checking in', 'I wanted to reach out because...'.\n"
        "13. Output RAW JSON only — no prose, no ```json fences, no trailing "
        "commentary. The full response is parsed by `JSONDecoder.raw_decode`.\n"
    )
    return [{"role": "user", "content": body}]


# ═════════════════════════════════════════════════════════════════════════════
# SHARDED PARALLEL SYNTHESIS (selected by heavy_synthesis_mode auto/sharded)
# ═════════════════════════════════════════════════════════════════════════════
#
# The monolithic build_parent_synthesis_messages above emits the WHOLE dossier in
# one serial stream — the wall-clock wall (see docs/superpowers/specs/
# 2026-06-11-heavy-sharded-synthesis-design.md). The builders below decompose
# that into: a SPINE call (coherence-critical scoring/brief/meta), N parallel
# SHARD calls (each owns a DISJOINT slice of top-level keys), and a NARRATIVE
# reduce (full_dossier_markdown over the assembled structured dossier).
#
# Caching: every spine+shard call shares an IDENTICAL cacheable prefix
# (system prompt + build_cached_inputs_text). The spine runs first and warms the
# cache; the shards read it (cache_read ≈ 0.1× input). Only the cheap trailing
# instruction differs per call. The narrative call uses a different prefix (the
# assembled dossier) and does not share the cache — that's fine, it's one call.
#
# The schema (REQUIRED_DOSSIER_SHAPE) lives in the cached prefix, so every shard
# sees the exact shape of its keys at near-zero marginal input cost; each shard's
# trailing instruction then says "emit ONLY these top-level keys".


def build_cached_inputs_text(fragments, intake, preflight_data, rr_baseline,
                             *, rr_degraded=False, rr_degradation_reason=None,
                             payload_max_chars=80000):
    """The shared, cacheable context block reused verbatim by the spine and
    every shard. Contains the inputs payload + the full dossier schema. Must be
    byte-identical across all spine/shard calls of one request for the prompt
    cache to hit."""
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
    return (
        "# ELISS dossier synthesis — shared context (cached across all section calls)\n\n"
        "Four research subagents (tech, compliance, org, behavioral) returned JSON "
        "fragments. Below are those fragments + intake + preflight + RocketReach "
        "baseline, then the canonical dossier schema. In the instruction that "
        "follows this block you will be asked to emit ONE SPECIFIC SUBSET of the "
        "dossier's top-level keys — follow the schema below for the exact shape of "
        "those keys.\n\n"
        "## Inputs\n"
        f"```json\n{_trim_for_prompt(payload, max_chars=payload_max_chars)}\n```\n\n"
        + REQUIRED_DOSSIER_SHAPE
        + _rr_degradation_note(rr_degraded, rr_degradation_reason)
    )


# Cross-cutting discipline appended to every spine/shard instruction. Mirrors the
# key-naming + dollar-string + dict-unwrap rules from build_parent_synthesis_messages
# so a sharded dossier matches the renderer contract exactly.
_SHARD_COMMON_DISCIPLINE = (
    "\n\nGLOBAL DISCIPLINE (non-negotiable):\n"
    "- Output RAW JSON only — a single JSON object, no prose, no ```json fences. "
    "Parsed by JSONDecoder.raw_decode.\n"
    "- Emit ONLY the top-level keys named in this instruction. Do NOT emit other "
    "dossier sections (other calls own them) — extra keys are discarded and waste "
    "your output budget.\n"
    "- All values are PLAIN SCALARS or arrays/objects of scalars. Do NOT wrap "
    "values in {value, confidence, tier} dicts; put confidence on a sibling "
    "`<field>_confidence` key.\n"
    "- Dollar amounts are $-prefixed strings with NO tildes (e.g. \"$45M\").\n"
    "- Fill thin areas by INFERENCE from preflight + RR + intake, but never invent "
    "specific facts (names, $ amounts, dates).\n"
)

SPINE_OWNS = ["meta", "scoring", "executive_brief"]

_SPINE_INSTRUCTION = (
    "# YOUR TASK — THE SPINE\n"
    "Emit ONLY these three top-level keys: `meta`, `scoring`, `executive_brief`. "
    "This is the coherence spine — your `scoring.tier` governs the entire dossier; "
    "the section shards consume it. Be decisive and complete here.\n\n"
    "- `scoring`: tier (HOT|WARM|COOL|COLD), final_score, composite, "
    "overall_confidence, icp_match + icp_match_reason, and the FOUR dimension "
    "dicts EMITTED FLAT under `scoring` (NOT under scoring.dimensions): "
    "fit{score,confidence}, intent{score,confidence,signals[]}, "
    "timing{score,confidence}, budget{score,confidence}. Rubric: fit 0-25, "
    "intent 0-25, timing 0-30, budget 0-20; final_score = sum minus risk "
    "adjustments. Also: risk_adjusted_composite, negative_modifiers[], "
    "deal_execution_risks[], total_risk_adjustment, recommended_action, "
    "earlyvangelist (4 pips has_problem/knows_problem/has_budget/"
    "has_makeshift_solution each {value,evidence,source_url} + count + rationale), "
    "and scenarios[] (≥3 for HOT/WARM: one positive, one negative, one pivot; "
    "before_score MUST equal risk_adjusted_composite).\n"
    "- `executive_brief`: a 200-400 char string — WHO + WHAT environment + WHY now "
    "+ WHAT's missing, citing a specific fact (not generic prose).\n"
    "- `meta`: {version: \"heavy-8.0.0-sharded\", generated: \"YYYY-MM-DD\", "
    "rocketreach_budget: {session_totals: {person_lookups: N, company_lookups: M}}}.\n"
    + _SHARD_COMMON_DISCIPLINE
)


# Each shard owns a DISJOINT set of top-level keys. `instruction` tells the model
# exactly which keys to emit and the key-specific shape rules that matter for the
# renderer. The schema in the cached prefix carries full detail; these are the
# critical "don't get this wrong" reminders.
SHARD_SPECS = [
    {
        "key": "org",
        "owns": ["lead", "company", "org_intelligence"],
        "instruction": (
            "# YOUR TASK — ORG / PEOPLE / COMPANY\n"
            "Emit ONLY: `lead`, `company`, `org_intelligence`.\n"
            "- org_intelligence DMU roles (economic_buyer, champion, "
            "technical_evaluator, blocker, representative_pain_owner) are FLAT keys "
            "directly under org_intelligence — NOT nested under `.dmu` (a nested "
            ".dmu renders an EMPTY DMU map). Also include additional_stakeholders[], "
            "future_stakeholders[], ghost_stakeholders[], multi_thread_strategy, "
            "headcount_trend.\n"
            "- lead.title: if unverified, write \"Title to be confirmed\" — NEVER "
            "\"Unknown\". Include seniority, authority, tenure, personalization_hooks[].\n"
            "- company uses keys `hq` (NOT headquarters), `revenue` (NOT "
            "revenue_estimate), `employees`, `employees_confidence`, ownership, "
            "industry. Populate company.micro_segment (a who-where slice, NEVER the "
            "bare vertical) and company.operating_model (2-3 sentences in customer "
            "language)."
            + _SHARD_COMMON_DISCIPLINE
        ),
    },
    {
        "key": "tech",
        "owns": ["technology"],
        "instruction": (
            "# YOUR TASK — TECHNOLOGY & COMPETITIVE\n"
            "Emit ONLY: `technology`. Include ad_environment, cloud_posture, "
            "digital_maturity, security_stack (list of short pill strings), "
            "competitors_detected[], displacement_angle, competitive_readiness_score "
            "+ competitive_readiness_basis, competitive_threat_matrix[] (≥3 rows, "
            "each {competitor, presence_likelihood, basis, displacement_angle, "
            "threat_level}), and renewal_intelligence[]. Use the tech subagent "
            "fragment as primary evidence."
            + _SHARD_COMMON_DISCIPLINE
        ),
    },
    {
        "key": "compliance",
        "owns": ["compliance", "budget_analysis"],
        "instruction": (
            "# YOUR TASK — COMPLIANCE & BUDGET\n"
            "Emit ONLY: `compliance`, `budget_analysis`.\n"
            "- `compliance` is a LIST of 3-5 framework objects. Each uses "
            "`ad360_angle` / `log360_angle` (SHORT PROSE on how the product helps — "
            "NOT the key `_fit`, and NOT a HIGH/MED/LOW value), plus `pressure` "
            "(HIGH|MEDIUM|LOW), `urgency`, `evidence`, `evidence_urls`.\n"
            "- `budget_analysis`: dollar fields ($-prefixed strings, no tildes) "
            "estimated_it_spend, security_budget, affordability, budget_trend, "
            "deal_authority, deal_cycle_months, calculation_basis; and USD INTEGER "
            "fields estimated_deal_size, deal_size_basis, iam_iga_budget, siem_budget."
            + _SHARD_COMMON_DISCIPLINE
        ),
    },
    {
        "key": "signals",
        "owns": ["signals"],
        "instruction": (
            "# YOUR TASK — BUYING SIGNALS\n"
            "Emit ONLY: `signals` (a single object).\n"
            "- signals.positive[] entries each get `id` (slug e.g. sig-001), "
            "`signal_symbol` (one of ⚡⚓☐⤴^☑$♀); pain/obstacle signals (⚡ or ☐) "
            "ALSO get an `obstacle` + `workaround` pair. Add a top-level "
            "signals.evidence_index map keyed by signal id.\n"
            "- signals.last_90_days_timeline[] is REQUIRED when the spine tier "
            "(provided below) is HOT or WARM — chronological dated events "
            "{date, event, source_url, category, evidence_strength}. Empty on "
            "HOT/WARM fails the depth-lint gate.\n"
            "- signals.negative[] as applicable, each {flag, signal_category, "
            "impact, source, evidence, evidence_urls}."
            + _SHARD_COMMON_DISCIPLINE
        ),
    },
    {
        "key": "riskprep",
        "owns": ["pre_mortem", "rep_readiness_checklist"],
        "instruction": (
            "# YOUR TASK — PRE-MORTEM & REP READINESS\n"
            "Emit ONLY: `pre_mortem`, `rep_readiness_checklist`.\n"
            "- `pre_mortem`: 3 distinct deal-loss scenarios grounded in the actual "
            "dossier facts, each {scenario, why_it_could_happen, evidence_urls, "
            "mitigation, earliest_signal}.\n"
            "- `rep_readiness_checklist`: 5-8 specific items the rep must verify or "
            "prepare before the first call."
            + _SHARD_COMMON_DISCIPLINE
        ),
    },
    {
        "key": "playbook",
        "owns": ["demo_playbook", "recommendations", "recommended_outreach"],
        "instruction": (
            "# YOUR TASK — DEMO PLAYBOOK / RECOMMENDATIONS / OUTREACH\n"
            "Emit ONLY: `demo_playbook`, `recommendations`, `recommended_outreach`.\n"
            "- demo_playbook.{ad360,log360}: each has value_moments[] (each "
            "{title, why_it_matters, tell_show_tell} tied to a specific dossier "
            "fact), discovery_questions[], discovery_anchors[] (1:1 with "
            "discovery_questions on HOT), top_objections[], cta; plus persona + "
            "opening_hook at the top level of demo_playbook.\n"
            "- recommendations: action, next_steps[], ad360_talking_points[], "
            "log360_talking_points[], objections[], decision_tree, and outreach "
            "(VFWPA: vision/framing/weakness/pedestal/ask + advisory_posture; `ask` "
            "names a concrete advancement currency — time, reputation, or cash).\n"
            "- recommended_outreach[]: 3 templates, each {slot, template_name, "
            "template_id, voice, triggered_by[], subject, body, rationale}.\n"
            "- BANNED phrasings anywhere in opening_hook / outreach (fire depth-lint "
            "on HOT): 'I noticed your company...', 'Are you currently struggling "
            "with...', 'Do you need better visibility into...', 'Would you ever "
            "consider...', 'How important is X to your business?', 'Hope this email "
            "finds you well', 'Just checking in', 'I wanted to reach out because...'."
            + _SHARD_COMMON_DISCIPLINE
        ),
    },
    {
        "key": "momdata",
        "owns": ["data"],
        "instruction": (
            "# YOUR TASK — MOM TEST `data` BLOCK\n"
            "Emit ONLY: `data` (a single object).\n"
            "- industry_operational_lens (one paragraph ~80-120 words in customer "
            "language, anchored on company.micro_segment from the spine/fragments).\n"
            "- discovery_discipline: zoom_strategy + zoom_rationale + good_questions[] "
            "(using the book's real templates: 'Talk me through the last…' / 'How are "
            "you dealing with it now?' / 'What are the implications of that?' / 'What "
            "else have you tried?' / 'Where does the money come from?') + "
            "bad_questions[] (each {question, why_bad}) + anti_patterns[].\n"
            "- rep_list_of_3 (3 questions, each {question, why_it_matters, dmu_role}).\n"
            "- research_vs_ask (settled_by_research[] with source_url + must_ask_live[] "
            "with why_unsettleable).\n"
            "- deal_premortem ({if_lost, must_be_true_to_win[]})."
            + _SHARD_COMMON_DISCIPLINE
        ),
    },
    {
        "key": "quality",
        "owns": ["data_quality", "sources"],
        "instruction": (
            "# YOUR TASK — DATA QUALITY & SOURCES\n"
            "Emit ONLY: `data_quality`, `sources`.\n"
            "- `data_quality`: overall_confidence (HIGH|MEDIUM|LOW), 3-6 "
            "assumptions[], 3-6 gaps[], and sources_actually_checked[] with ≥10 "
            "entries (preflight + RR + each web_search the subagents ran), each "
            "{source, access_method, layer, yielded_signal}.\n"
            "- `sources`: an OBJECT keyed by Company/Person/Technology/Financial/"
            "Compliance, each a list of {url, tier (A|B|C), label}; ≥10 URLs total. "
            "Pull every URL from the subagent fragments' sources[] lists + preflight "
            "source URLs + RR links. NEVER emit `sources: {}`."
            + _SHARD_COMMON_DISCIPLINE
        ),
    },
]


def build_spine_instruction():
    return _SPINE_INSTRUCTION


def build_shard_instruction(spec, spine_obj):
    """Trailing instruction for one shard — its key list + a compact view of the
    spine so the section stays consistent with the verdict/tier."""
    scoring = (spine_obj or {}).get("scoring") if isinstance(spine_obj, dict) else None
    spine_view = {
        "tier": (scoring or {}).get("tier"),
        "final_score": (scoring or {}).get("final_score"),
        "recommended_action": (scoring or {}).get("recommended_action"),
        "executive_brief": (spine_obj or {}).get("executive_brief"),
    }
    return (
        spec["instruction"]
        + "\n\n## SPINE (already computed — keep your section consistent with this)\n"
        f"```json\n{_trim_for_prompt(spine_view, max_chars=4000)}\n```\n"
    )


_NARRATIVE_INSTRUCTION = (
    "# YOUR TASK — TAB 2 NARRATIVE\n"
    "Write the `full_dossier_markdown` for the dossier whose STRUCTURED data is "
    "given above. Output the markdown document DIRECTLY as RAW TEXT — do NOT wrap "
    "it in JSON, do NOT use ```fences, do NOT add any preamble. Start with the "
    "first markdown heading and nothing before it.\n\n"
    "Length: aim for 8000-15000 characters — DENSE, not padded. Be concise; do not "
    "exceed ~15000 characters. Cover, in this order: (1) Score Summary, "
    "(2) Executive Brief, (3) Person Profile, (4) Company Profile, (5) Technology "
    "+ Competitive Matrix, (6) Org Intelligence + Ghost Stakeholders, (7) Budget, "
    "(8) Compliance, (9) Buying Signals, (10) Deal Execution Risks, (11) Scoring "
    "Rationale, (12) Strategic Recs, (13) Pre-Mortem, (14) Rep Readiness, "
    "(15) Research Sources. Use markdown ## / ### headings and bullet lists. "
    "Callouts open at COLUMN 0 with `**Why:**`, `**Action:**`, `**Trigger:**` — "
    "NEVER preceded by `>` (a blockquote breaks the callout). Cite source tier "
    "letters [A]/[B]/[C] inline after each evidence sentence. Every fact MUST come "
    "from the structured dossier above — do NOT invent."
)


def build_narrative_messages(assembled_dossier, *, payload_max_chars=80000):
    """Build the system+user messages for the narrative reduce. Receives the
    assembled structured dossier (without full_dossier_markdown) and asks for the
    prose AS RAW MARKDOWN (not JSON) — a single text field has no reason to be
    JSON-wrapped, and raw text makes a max_tokens stop non-fatal (it just yields
    slightly shorter, still-valid prose instead of unparseable JSON)."""
    body = (
        "# ELISS dossier — structured data (source of truth for the narrative)\n\n"
        f"```json\n{_trim_for_prompt(assembled_dossier, max_chars=payload_max_chars)}\n```\n\n"
        + _NARRATIVE_INSTRUCTION
    )
    return [{"role": "user", "content": body}]


# All top-level dossier keys, owned exactly once across spine + shards + narrative.
# Used by the disjointness unit test and as documentation of the merge contract.
NARRATIVE_OWNS = ["full_dossier_markdown"]


def all_owned_keys():
    keys = list(SPINE_OWNS)
    for spec in SHARD_SPECS:
        keys.extend(spec["owns"])
    keys.extend(NARRATIVE_OWNS)
    return keys
