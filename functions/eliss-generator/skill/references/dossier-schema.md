# ELISS Light — Dossier JSON Renderer Schema

Read this file ONCE before constructing the dossier dict in Step 4. The renderer (`generate_report.py`) reads these EXACT field names. Wrong key names = silent empty sections in the HTML report.

## Required top-level fields (renderer breaks without these)

```
executive_brief            top-level string. Tab 1 Executive Brief card.
full_dossier_markdown      top-level string. Tab 2 prose. 8K–15K chars.
scoring                    dict (see schema below). Each dimension is a dict, not int.
lead                       dict. Person Profile section.
company                    dict. Company Profile section.
technology                 dict (incl. competitive_threat_matrix[]).
budget_analysis            dict. STRING fields with $K/M/B suffixes + int deal-size fields.
data_quality               dict. {overall_confidence, assumptions[], gaps[]}.
org_intelligence           dict. DMU roles are FLAT keys, NOT nested under .dmu.
compliance                 list of rows.
recommendations            top-level dict. Powers Strategic Recommendations.
pre_mortem                 list. 3 loss scenarios.
rep_readiness_checklist    list of 5–8 strings.
recommended_outreach       list. 3 email objects (HOT/WARM).
sources                    top-level dict of category arrays.
meta.rocketreach_budget    dict. Required when any RR call fired.
```

---

## scoring

All dimension scores must be dicts with `score` + `confidence`, not bare ints.

```json
"scoring": {
  "tier": "HOT",
  "final_score": 80,
  "composite": 80,
  "overall_confidence": "HIGH|MEDIUM|LOW",
  "icp_match": "Strong|Moderate|Weak",
  "icp_match_reason": "one sentence",
  "fit":    {"score": 21, "confidence": "HIGH"},
  "intent": {
    "score": 18, "confidence": "MEDIUM",
    "signals": [
      {"category": "Compliance Need", "points": 10, "evidence": "..."},
      {"category": "Direct Inquiry",  "points": 12, "evidence": "..."}
    ]
  },
  "timing": {"score": 24, "confidence": "MEDIUM"},
  "budget": {"score": 17, "confidence": "MEDIUM"},
  "risk_adjusted_composite": 67,
  "negative_modifiers":   [{"modifier": "label", "points": -8}],
  "deal_execution_risks": [{"risk": "label", "adjustment": -3}],
  "total_risk_adjustment": -13,
  "recommended_action": "PURSUE NOW",
  "earlyvangelist": {
    "has_problem":              {"value": true,  "evidence": "...", "source_url": "..."},
    "knows_problem":            {"value": true,  "evidence": "...", "source_url": "..."},
    "has_budget":               {"value": false, "evidence": "...", "source_url": null},
    "has_makeshift_solution":   {"value": true,  "evidence": "...", "source_url": null},
    "count": 3,
    "rationale": "3/4 — HOT-worthy; budget is the missing pip."
  }
}
```

**v7.6+ (Mom Test upgrade) — `scoring.earlyvangelist`.** Four booleans per book p72. Each `{value, evidence, source_url}`. `count` ∈ 0–4 + `rationale`. The `has_makeshift_solution` evidence MUST cite the workaround from `signals.positive[].workaround` (or `obstacle/workaround` on a dedicated problem entry). 4-pip = strongest enterprise buyer; 3-pip = HOT-worthy; 2-pip = WARM; 0–1 = real lead but not the buying moment. Renders as the Tab 1 4-pip Earlyvangelist Scorecard (collapsed-by-default).

---

## data — Mom Test discipline surfaces (v7.6+)

New top-level `data` block holds the Mom Test surfaces. Powers Tab 1 hero cards (Operational Lens always-open, Research-vs-Ask always-open, Rep's List of 3 always-open, Discovery Discipline collapsed) + Tab 2 sections.

```json
"data": {
  "industry_operational_lens": "One paragraph in customer language, anchored on company.micro_segment, framing what system availability/identity/audit MEANS to this prospect. Uses ≥2 phrases from the matched vertical-playbook section's Customer Language list.",
  "discovery_discipline": {
    "zoom_strategy": "zoom_now | confirm_category_first",
    "zoom_rationale": "Why this zoom_strategy — cite vertical-playbook section.",
    "good_questions": [
      {"question": "...", "template": "Talk me through the last time…", "anchor_fact_ref": "signals.positive[sig-005]"}
    ],
    "bad_questions": [
      {"question": "...", "why_bad": "anything involving the future is an over-optimistic lie"}
    ],
    "anti_patterns": [
      "'I noticed your company...' — feature-rep boilerplate.",
      "Treating a compliment as a buying signal — a stall is not advancement."
    ]
  },
  "rep_list_of_3": [
    {"question": "...", "why_it_matters": "...", "dmu_role": "representative_pain_owner"},
    {"question": "...", "why_it_matters": "...", "dmu_role": "economic_buyer"},
    {"question": "...", "why_it_matters": "...", "dmu_role": "economic_buyer"}
  ],
  "research_vs_ask": {
    "settled_by_research": [{"fact": "...", "source_url": "..."}],
    "must_ask_live":        [{"question": "...", "why_unsettleable": "..."}]
  },
  "deal_premortem": {
    "if_lost": "The single most likely loss scenario in one sentence.",
    "must_be_true_to_win": ["3–5 success preconditions"]
  }
}
```

**Required for HOT/WARM.** `industry_operational_lens` (lint: `[depth-lint] industry_language_missing` if <2 vertical-playbook terms). `discovery_discipline.good_questions[i]` must be a prospect-specific instance of a real Mom Test template tied to a dossier fact via `anchor_fact_ref`. `research_vs_ask` is the dossier's spine (book p116); without it, the dossier degrades into a vendor brochure. `rep_list_of_3` — exactly 3, no more (book p54). `deal_premortem` layers over, NOT replaces, `pre_mortem[]`.

---

## lead — Person Profile

```json
"lead": {
  "name": "...", "title": "...",
  "seniority": "C-Suite / Executive | Director / VP | Manager | IC",
  "authority": "Economic Buyer | Champion | Technical Evaluator | Influencer",
  "tenure":    "8 years (Jan 2018–Present)",
  "email": "...", "email_grade": "A|B|C|F",
  "phone": "...", "linkedin_url": "...", "location": "...",
  "personalization_hooks": ["..."],
  "_rocketreach_name": true, "_rocketreach_title": true, "_rocketreach_email": true
}
```

Renderer reads `seniority`, `authority`, `tenure` directly — keep these key names.

### `lead.title` discipline (v7.5.2)

The `title` field renders into the **Tab 1 lead-sub header** (just below the lead name) and the Person Profile field. It is real estate for *who this person is* — not for the verification process.

**If RR + LinkedIn + web search all fail to verify the title**, write `"Title to be confirmed"` (or leave the field empty — the renderer falls back to that placeholder). Document the verification effort in `data_quality.gaps[]` only. Use `org_intelligence.champion.note` for the qualitative narrative ("Verify inbound role first; promote to Champion only if title research confirms IT/security ownership").

**Anti-patterns the renderer now strips** (substituted with `"Title to be confirmed"`):

- `"Unknown — verification incomplete after N OSINT angles"`
- `"Unverified after ..."`
- `"unknown role"` / `"role unknown"` / `"unknown title"` / `"title unknown"`
- bare `"Unknown"` (case-insensitive)
- any title starting with `"Unknown —"` / `"Unknown -"`

This guard is defense-in-depth — the authoring rule is still the primary contract. The header line `"<title> at <company> • <email>"` should always read as a clean identity line, not a process log.

---

## company — Company Profile

Renderer reads `hq` (NOT `headquarters`), `employees` (NOT `num_employees_*`), `revenue` as a `$`-prefixed STRING (NOT raw int). The waterfall budget chart parses `revenue` as prose with `$` prefix.

```json
"company": {
  "name": "...",
  "industry": "Government — Local/Municipal",
  "sub_industry": "...",
  "employees": "6,320 (DC Gov) / ~36,000 managed scope",
  "employees_confidence": "CONFIRMED|ESTIMATED",
  "revenue": "$8.3B",
  "hq": "200 I Street SE, Washington, DC 20005",
  "ownership": "Public sector / Government",
  "micro_segment": "US state agency, mid-sized, on a NASPO ValuePoint contract — cyber-grant-funded SIEM modernization in motion",
  "operating_model": "SecOps team of ~12 covering 24×5 in-house with weekend on-call rotations; IAM ownership sits with Identity Engineering team; change windows align to fiscal-year boundaries and quarterly CAB approval."
}
```

**v7.6+ (Mom Test upgrade).** `micro_segment` is REQUIRED — a sliced who-where from `references/vertical-playbook.md`, NEVER the bare vertical name. `operating_model` is REQUIRED — 2–3 sentences in customer language. Both anchor the Tab 1 Operational Lens hero band.

---

## technology — Technology & Security Posture

```json
"technology": {
  "ad_environment":       "On-prem AD across 21 departments…",
  "cloud_posture":        "Hybrid — on-prem + selective SaaS…",
  "digital_maturity":     "High — 8 published security policies, NIST 800-53…",
  "security_stack":        ["KnowBe4 (confirmed)", "On-prem AD (inferred)"],
  "competitors_detected":  ["No incumbent SIEM/IAM identified — greenfield"],
  "displacement_angle":   "Strategy note rendered below the badges.",
  "competitive_threat_matrix": [ ... see below ... ]
}
```

`security_stack[]` and `competitors_detected[]` render as pill badges. `displacement_angle` renders as a strategy note.

### Competitive Readiness Badge (REQUIRED)

Two top-level `technology` fields drive the score badge that renders above the threat matrix:

```json
"technology": {
  "competitive_readiness_score": 7,
  "competitive_readiness_basis": "Likely SailPoint + Splunk incumbents; AD360 coexists upstream of SailPoint and Log360 carries DORA Article 17 templates Splunk lacks — pilot-able without rip-and-replace, but a POC is mandatory to clear F500 vendor-risk review."
}
```

`competitive_readiness_score` is an integer 1–10. Renderer thresholds (verified from `build_competitive_matrix_html`):

| Score | Color | Label |
|---|---|---|
| 8–10 | green  | "Strong position" |
| 5–7  | amber  | "Competitive, POC required" |
| 1–4  | red    | "Uphill battle" |

`competitive_readiness_basis` is a 1–2 sentence rationale rendered next to the badge under "Competitive Readiness (vs. most likely incumbent)". Be specific: name the incumbent and the displacement angle, not a generic statement. If the basis string is empty the renderer prints "No basis provided." which looks unfinished — always populate.

How to score:
- **8–10 (green)**: greenfield confirmed OR incumbent at end-of-renewal OR ICP feature-fit dominant.
- **5–7 (amber)**: incumbent likely but coexistable / phase-2-displaceable, POC scope is clear.
- **1–4 (red)**: large-incumbent + recent renewal + heavy switching cost, or non-fit AD environment.

---

### renewal_intelligence[] — incumbent contract-renewal windows (v7.5)

The single highest-leverage Timing data point per /eliss SKILL.md. For each Likely-or-Confirmed competitor in the threat matrix, derive an estimated renewal window and let it feed Timing scoring deterministically.

```json
"technology": {
  "renewal_intelligence": [
    {
      "incumbent": "Splunk",
      "estimated_renewal_window": "Q2-Q4 2027",
      "confidence": "INFERRED",
      "basis": "Typical 3-yr enterprise cycle; RR techstack first-seen 2024; no explicit RFP found",
      "timing_trigger": "moderate"
    }
  ]
}
```

**Field rules:**

- `incumbent`: matches a `competitive_threat_matrix[].competitor` value exactly.
- `estimated_renewal_window`: prose like `"Q2-Q4 2027"`, `"~Mar 2026"`, `"contract expired Q1 2025"`. Don't fake precision.
- `confidence`: `"CONFIRMED"` (RFP/SAM.gov/press-release date), `"INFERRED"` (3-yr cycle from first-seen), or `"ESTIMATED"` (vertical benchmark only).
- `basis`: 1-sentence cite — RR first-seen date, press-release URL, USAspending end-date, etc.
- `timing_trigger`: one of `"imminent"` (<6mo), `"strong"` (6-12mo), `"moderate"` (12-24mo), `"lockout"` (just renewed for ≥2yr).

**Scoring tie:** the highest `timing_trigger` across all renewal_intelligence[] rows maps directly to the Timing rubric:
- `imminent` → +24 Timing
- `strong` → +18 Timing  
- `moderate` → +12 Timing
- `lockout` → caps Timing at 6 AND triggers `recently_renewed_lockout: -18` structural modifier

Cite the row in the scoring rationale so the rep can falsify the inference on the discovery call.

### technology.web_fingerprint{} — Tab 1 badge grid (v7.5)

Auto-populated by `preflight.py probe_web_fingerprint()`. Renderer reads this to draw the "Web Property Tech Fingerprint" badge grid on Tab 1 (the depth-lint warning we keep seeing flags this section as missing — populating it removes the warning).

```json
"technology": {
  "web_fingerprint": {
    "frontend":  ["React", "Webpack"],
    "analytics": ["Google Analytics 4", "Adobe Analytics"],
    "chat":      ["Drift"],
    "cdn":       ["Cloudflare"],
    "cms":       ["Adobe Experience Manager"],
    "framework": ["ASP.NET 4.8"],
    "email_marketing": ["Marketo"]
  }
}
```

Each category is an array of detected brands. Empty arrays are fine — the renderer hides empty categories. Source: HTTP HEAD response headers + script-tag scraping from preflight; no Claude tokens consumed.

### competitive_threat_matrix[]

Use exact key names `competitor` and `presence_likelihood` (NOT `incumbent`/`presence`). At least 1 row required — never write "None detected." When direct evidence is absent, infer (Microsoft-heavy → Sentinel/Defender Likely; post-breach → CrowdStrike Possible; <500 emp → Splunk Unlikely).

```json
{
  "competitor": "Microsoft Sentinel",
  "presence_likelihood": "Likely",
  "basis": "evidence text",
  "basis_urls": [],
  "displacement_angle": "on-prem vs cloud-only",
  "threat_level": "Moderate"
}
```

- `presence_likelihood`: `"Likely"` | `"Possible"` | `"Unlikely"`
- `threat_level`: `"Critical"` | `"Moderate"` | `"Low"`

---

## budget_analysis — IT Budget & Purchasing Power

Dollar-prefixed STRINGS (`"$664M"`) parsed by waterfall chart — keep `$` and use K/M/B suffixes. Integer fields stay as ints.

```json
"budget_analysis": {
  "estimated_it_spend":  "$664M (8% of $8.3B total budget)",
  "security_budget":     "~$100M (15% of IT)",
  "affordability":       "Strong — gov-scale budget…",
  "budget_trend":        "Stable — FY23-25 plan ending; FY26-28 cycle opening",
  "deal_authority":      "CISO has direct authority…",
  "deal_cycle_months":   "6-18 (standard RFP) or 3-6 (cooperative contract)",
  "calculation_basis":   "Total budget × 8% IT × 15% security; deal sizing 36K users × $2/user/month × 12",
  "estimated_deal_size": 180000,
  "deal_size_basis":     "...",
  "iam_iga_budget":      11952000,
  "siem_budget":         14940000
}
```

Required ints: `estimated_deal_size`, `iam_iga_budget` (= 12% of security), `siem_budget` (= 15% of security). Required string: `deal_size_basis`.

---

## data_quality

```json
"data_quality": {
  "overall_confidence": "HIGH|MEDIUM|LOW",
  "assumptions": [
    "Managed scope of ~36,000 inferred from public org chart",
    "IT budget estimated at 8% of total budget per public-sector benchmark"
  ],
  "gaps": [
    "No incumbent SIEM surfaced — could be greenfield OR hidden legacy",
    "GSA Schedule 70 / NASPO eligibility not confirmed"
  ],
  "sources_actually_checked": [
    {"source": "preflight.dns",                "access_method": "preflight",       "layer": 1, "yielded_signal": true},
    {"source": "preflight.microsoft_tenant",   "access_method": "preflight",       "layer": 2, "yielded_signal": true},
    {"source": "preflight.web_fingerprint",    "access_method": "preflight",       "layer": 2, "yielded_signal": true},
    {"source": "preflight.security_txt",       "access_method": "preflight",       "layer": 2, "yielded_signal": false},
    {"source": "RocketReach /lookup_company",  "access_method": "rocketreach_api", "layer": 5, "yielded_signal": true},
    {"source": "web_search 'NYDFS Part 500'",  "access_method": "web_search",      "layer": 3, "yielded_signal": true}
  ]
}
```

### sources_actually_checked[] — provenance audit trail (v7.5)

Auto-populate from three places, in order. Renderer reads this for the Source Quality donut on Tab 1 (entries with `yielded_signal: true` count toward source floors).

1. **Preflight** returns `sources_actually_checked_entries[]` — copy verbatim. Each entry pre-shaped with `access_method: "preflight"` and the right layer.
2. **Gate B (RR)** — for each endpoint hit, append `{source: "RocketReach /<endpoint>", access_method: "rocketreach_api", layer: 5, yielded_signal: <bool>}`.
3. **Gate C (web searches)** — for each `web_search` query the analyst runs, append `{source: "web_search '<query truncated>'", access_method: "web_search", layer: <category>, yielded_signal: <bool>}`. `yielded_signal: false` is fine and useful — shows what was tried-and-empty.

**Discipline:** if `len(sources_actually_checked) < 8`, the dossier almost certainly underran the standard pipeline (Gate A: ~8 + Gate B: ~4 + Gate C: ~6 = ~18 baseline). Document the gap in `data_quality.gaps[]`.

---

## org_intelligence — DMU & Ghost Stakeholder Map

**FLAT keys at `org_intelligence` level — NOT nested under `.dmu`.** Putting roles under `org_intelligence.dmu.*` causes the entire DMU map to render empty.

DMU role discipline:
- **Economic Buyer** = budget owner (CIO/CISO/City Manager for $30K–$100K mid-market deals).
- **Champion** = person who FEELS pain AND has authority/influence (typically one level above inbound contact).
- **Technical Evaluator** = runs the POC (often the inbound contact if Manager/IC).
- Inbound contact defaults to Technical Evaluator unless research confirms Director-level authority.
- Vacant/unidentified roles (no name) → put in `future_stakeholders[]` ONLY. The DMU map node renders only when `name` is non-empty and not in `('unknown','—','-','n/a','tbd')`.

```json
"org_intelligence": {
  "economic_buyer":      {"name": "...", "title": "...", "confidence": "CONFIRMED|INFERRED", "linkedin": "...", "note": "..."},
  "champion":            {"name": "...", "title": "...", "email": "...", "phone": "...", "linkedin": "...", "confidence": "CONFIRMED"},
  "technical_evaluator": {"name": "...", "title": "...", "linkedin": "...", "confidence": "CONFIRMED|INFERRED"},
  "blocker":             {"name": "...", "title": "...", "confidence": "INFERRED"},
  "representative_pain_owner": {"name": "...", "title": "...", "why": "...", "source_url": "..."},
  "additional_stakeholders": [{"role": "Influencer|Sponsor|EB-delegated", "name": "...", "title": "...", "relevance": "..."}],
  "future_stakeholders":     [{"role": "...", "why": "...", "action": "..."}],
  "multi_thread_strategy":   "one-sentence strategy for working multiple stakeholders in parallel",
  "headcount_trend":         "..."
}
```

**v7.6+ (Mom Test upgrade).** `representative_pain_owner` is the operator who actually LIVES the pain (book Ch7 p97) — distinct from `economic_buyer`. For an IAM problem at a regional bank: economic_buyer = CIO/CISO; representative_pain_owner = the IAM Architect or Identity Engineering lead who actually runs the access-review meat-grinder. Talking to the pain-owner first is faster, more candid, and produces specifics. The `why` field is one sentence explaining what they do day-to-day that puts them at the pain.

---

## compliance[] — Compliance Pressure Map

Each row uses `framework`, `pressure`, `urgency`, `ad360_angle`, `log360_angle` (NOT `deadline` or `product_mapping`). Wrong keys = silent empty section.

```json
{
  "framework": "CJIS",
  "pressure": "HIGH",
  "urgency":  "Ongoing — mandatory for all CJI systems",
  "ad360_angle": "Privileged-access governance + audit trail for CJI systems",
  "log360_angle": "CJIS Section 5.4-mapped audit log retention with on-demand re-indexing",
  "evidence": "DC MPD operates under OCTO IT…",
  "evidence_urls": ["https://..."]
}
```

Allowed `pressure`: `"HIGH"` | `"MEDIUM"` | `"LOW"`.

---

## signals.positive[] / signals.negative[]

`positive[]` must include `points` as int (timeline won't render without it):

```json
{
  "id": "sig-001",
  "signal": "NERC CIP mandatory — no SIEM confirmed",
  "signal_symbol": "⚡",
  "signal_category": "compliance_deadline",
  "points": 10,
  "age_days": 0,
  "source": "NERC regulatory [A]",
  "confidence": "HIGH",
  "evidence": "detail text",
  "evidence_urls": [],
  "obstacle": "Multi-year turnaround calendar — no OT change window before next outage",
  "workaround": "Engineering laptop with dual NIC occasionally bridges IT/OT for compliance evidence collection"
}
```

**v7.6+ (Mom Test upgrade).** Each entry SHOULD include:
- `id` — stable hyphen-prefixed slug.
- `signal_symbol` ∈ {⚡ pain, ⚓ goal, ☐ obstacle, ⤴ workaround, ^ background, ☑ purchasing, $ money, ♀ key-person} per `references/mom-test-discipline.md`.
- For pain/obstacle signals (⚡ or ☐): `obstacle` + `workaround` pair (book p105 — the workaround IS the earlyvangelist test #4, non-negotiable).

Add a top-level `signals.evidence_index = { "<id>": "sourced" | "inferred" | "assumed" }` map. The renderer reads it and renders a soft confidence pill (inferred=yellow, assumed=gray) next to the tier pill for any signal whose strength is below `sourced`. Empty map is fine — defaults to `sourced` for any unindexed signal.

Add a top-level `signals.last_90_days_timeline[]`: chronological list of dated real events from the last 90 days, each `{date: "YYYY-MM-DD", event, source_url, category, evidence_strength}`. Category aligned with existing `signal_category` taxonomy. Powers the Tab 1 Last-90-Days Timeline card. Empty on HOT/WARM fires `[depth-lint] timeline_empty_for_hot_lead`.

`negative[]` uses key `flag` (NOT `signal`):

```json
{
  "flag": "Post-bankruptcy fiscal conservatism",
  "signal_category": "budget_pressure",
  "impact": -8,
  "age_days": 630,
  "source": "Court records [A]",
  "evidence": "detail text",
  "evidence_urls": []
}
```

---

## pre_mortem[]

Keys are `why_it_could_happen` and `mitigation` (NOT `description`/`prevention`).

```json
{
  "scenario": "CFO vetoes as non-essential spend",
  "why_it_could_happen": "explanation of how this loss unfolds",
  "evidence_urls": [],
  "mitigation": "how to prevent this scenario",
  "earliest_signal": "the first observable sign this scenario is developing"
}
```

---

## scoring.scenarios[] — What-If Scenarios (HOT/WARM only)

3 (or more) cards that show how the headline score shifts in response to a specific signal the rep should listen for on the discovery call. Renders the *"What-If Scenarios"* section. Required for HOT and WARM tiers; optional for COOL/COLD.

Author **one positive** (deal-accelerating signal), **one negative** (stall risk), **one pivot** (decision-tree fork). `before_score` must equal the dossier's `risk_adjusted_composite` (NOT raw `composite`) so the cards align with the headline number; `after_score = before_score + delta`. `trigger` should be a quoted utterance the rep could literally hear on a call, not an abstract signal category.

```json
{
  "label": "Splunk renewal < 6 months out",
  "delta": +6,
  "before_score": 71,
  "after_score": 77,
  "before_tier": "WARM",
  "after_tier": "HOT",
  "kind": "positive",
  "logic": "Imminent SIEM renewal collapses the standard 12-month sales cycle into a 90-day consolidation window.",
  "trigger": "If they say 'our Splunk contract is up for renewal this quarter' or mention indexed-pricing concerns."
}
```

`kind` controls card accent color: `"positive"` (green), `"negative"` (red), `"pivot"` (amber), `"neutral"` (indigo). If `kind` is omitted, the renderer infers from `delta` sign.

---

## recommended_outreach[]

Keys are `template_name`, `triggered_by[]`, `rationale` (NOT `template`/`trigger`/`notes`).

`template_id` values (v7.4+, 13 templates): `compliance_gap`, `renewal_window`, `breach_incident`, `competitor_displacement`, `peer_benchmark`, `technical_deep_dive`, `org_change`, `cost_consolidation`, `insight_drop`, `hybrid_cloud_migration`, `audit_deadline`, `executive_briefing_offer`, `event_followup`.

`voice` values (v7.4+): `technical` / `executive` / `consultative`. Legacy `google` / `apple` / `microsoft` are still accepted — the renderer resolves them through `_LEGACY_VOICE_ALIASES`.

```json
{
  "slot": 1,
  "template_name": "Compliance Gap",
  "template_id": "compliance_gap",
  "voice": "consultative",
  "triggered_by": ["NERC CIP-007 logging gap", "no SIEM at mandatory BES operator"],
  "subject": "Subject line",
  "body": "Full email body text",
  "rationale": "Why this template for this prospect"
}
```

---

## demo_playbook (ELISS v7.4+)

Persona-anchored AD360 + Log360 demo blueprint. Renders as a structured card in Tab 1 between Competitive Threat Matrix and Signal Detail. Optional but strongly recommended for HOT/WARM leads. Both `ad360` and `log360` sub-blocks are individually optional — populate whichever this prospect actually fits.

```json
"demo_playbook": {
  "persona": "Role + 1–2 sentence operating context (e.g. 'IT Director at a CJIS-bound municipality reporting to a Council-elected official')",
  "opening_hook": "90-second cold open, dossier-grounded reframe (NOT a product feature)",
  "ad360": {
    "value_moments": [
      {
        "title": "Self-service password reset with auditable trail",
        "why_it_matters": "Tied to a specific dossier fact — helpdesk volume, audit finding, recent hire",
        "tell_show_tell": "Tell: claim. Show: the one screen named. Tell: takeaway the prospect repeats to their CIO."
      }
    ],
    "discovery_questions": ["Open-ended question tied to a dossier hypothesis", "..."],
    "top_objections": [
      {"objection": "Verbatim objection quote", "response": "Customized response for this prospect, not the generic playbook"}
    ],
    "cta": "Specific micro-commitment — not 'want to see Log360?'"
  },
  "log360": { "...same shape..." }
}
```

Source data for value moments + objections: AD360 features in product-icp.md lines 21–43, Log360 features lines 47–72, displaced-competitor playbook lines 124–142, objection bank lines 145–154.

---

## recommendations — Strategic Recommendations + First-Call Decision Tree

The Strategic Recommendations section renders ONLY from this top-level `recommendations` block. `scoring.recommended_action` does NOT populate it.

```json
"recommendations": {
  "action": "PURSUE NOW",
  "next_steps": [
    "Step 1: discovery call within 5 business days, target Deputy-CISO first",
    "Step 2: confirm GSA/NASPO contract vehicle (compress procurement to 3-6 months)",
    "Step 3: prepare 1-page compliance-to-Log360 mapping doc"
  ],
  "ad360_talking_points":  ["AD lifecycle automation…", "NIST 800-53 IA-2/AC-2/AC-6 native control mapping"],
  "log360_talking_points": ["Flat-file storage avoids Splunk indexed-pricing wall", "UEBA over AD event logs"],
  "objections": [
    {"objection": "We already have Splunk", "response": "Log360 deploys alongside, not instead…"},
    {"objection": "Procurement will take 18 months", "response": "If on GSA Schedule 70, this collapses to 3-6 months…"}
  ],
  "outreach": {
    "channel": "Email + LinkedIn",
    "timing":  "Within 5 business days",
    "hook":    "Compliance gap maps directly to your framework — happy to send a one-page control mapping"
  },
  "decision_tree": {
    "root_question": "Does the org have a current SIEM/IAM in production?",
    "branches": [
      {"signal": "Yes — Splunk/Sentinel confirmed", "action": "Pivot to consolidation TCO; surface renewal date"},
      {"signal": "No — greenfield confirmed",       "action": "Lead with compliance gap + bundled deal sizing"},
      {"signal": "Contact deflects to procurement", "action": "Engage Deputy CISO directly; confirm contract vehicle"}
    ]
  }
}
```

---

## sources — top-level dict of category arrays (Source Quality Donut)

```json
"sources": {
  "Company":    [{"url": "https://...", "tier": "A|B|C", "label": "description"}],
  "Person":     [{"url": "https://...", "tier": "B", "label": "LinkedIn profile"}],
  "Technology": [{"url": "https://...", "tier": "B", "label": "RR techstack"}],
  "Financial":  [{"url": "https://...", "tier": "A", "label": "ProPublica 990"}],
  "Compliance": [{"url": "https://...", "tier": "A", "label": "NERC CIP standards"}]
}
```

Add every searched/fetched URL — donut counts flat entries across all categories.

---

## Tags applied throughout

- `[A]` Tier-A: gov filings, .gov sites, company press releases
- `[B]` Tier-B: established press, LinkedIn, RocketReach
- `[C]` Tier-C: aggregators, inferred
- `[CONFIRMED]` verified facts | `[ESTIMATED]` derived numbers | `[INFERRED]` reasoned conclusions
- `ᴿᴿ` immediately after any RocketReach-sourced value
- Mark every RR-sourced JSON field with `_rocketreach_<field>: true`

### RR provenance pill — DO NOT duplicate the label (v7.4.1)

The `ᴿᴿ` glyph already renders as an orange "RR" pill via the renderer's regex rewrite (verified at `generate_report.py:3332`). The pill carries its own visible label. Therefore:

- **Wrong:** `Industry: Insurance — General | RR ᴿᴿ` → renders as "RR [RR-pill]" (visually duplicated)
- **Wrong:** `Department breakdown (RR ᴿᴿ):` → renders as "(RR [RR-pill]):"
- **Wrong:** `RR techstack ᴿᴿ` → renders as "RR techstack [RR-pill]"
- **Right:** `Industry: Insurance — General | ᴿᴿ` → renders as "[RR-pill]" (one label, clean)
- **Right:** `Department breakdown ᴿᴿ:` → renders as "[RR-pill]:"
- **Right:** `techstack ᴿᴿ` → renders as "techstack [RR-pill]"

Rule: **never prefix a value with literal "RR " when the same value already carries the `ᴿᴿ` glyph.** The pill is the label. Belt-and-suspenders here looks broken, not thorough.

When the source-tier letter follows (`[A]`/`[B]`/`[C]`), keep it after the pill: `Industry: Insurance — General ᴿᴿ [B]` is correct because Tier-B is *additional* provenance metadata (reliability), not a duplicate of the RR brand.

## Source floors (Light Edition)

| Tier | Sources | Signals | Named DMU |
|---|---|---|---|
| HOT  | ≥10 | ≥6 | ≥2 |
| WARM | ≥7  | ≥4 | ≥1 |
| COOL | ≥4  | ≥2 | — |

Sources count = preflight (~8) + RR endpoints (~5) + searches (6) → naturally clears HOT floor.
