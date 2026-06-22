# ELISS Dossier Template v7.5.0 (Mom Test upgrade)

## Conversational Output Format

Present the dossier in conversation using this structure. The order is intentional — the VP-level summary comes first, supporting detail follows.

### Markdown conventions for `full_dossier_markdown` (ELISS v7.0.2+)

Tab 2 of the rendered report shows the full `full_dossier_markdown` prose. Tab 1 already renders every structured data point from the JSON as visualizations and cards (score gauge, radar, budget waterfall, DMU node map, competitive matrix, signal timeline, etc.), so **Tab 2 must not duplicate Tab 1 data — it must complement it with analyst synthesis**. Use these conventions; the renderer in `scripts/generate_report.py` converts them into styled visual elements.

**Rule 1 — Non-duplicative analyst voice.** Each section is a 1-2 sentence TL;DR followed by 2-4 tight paragraphs of synthesis that connect dots Tab 1's individual cards cannot. Do NOT restate the score, headcount, title, contact email, dimension breakdowns, or other card-rendered facts (including the v7.4+ `demo_playbook{}` structured artifact — Tab 2's DEMO PLAYBOOK section is the rep's *narrative* briefing; Tab 1's card is the *structured* artifact for copy-paste into Salesforce). Before including a paragraph, confirm it carries analyst *reasoning* that Tab 1 doesn't already show.

**Rule 2 — Blockquote TL;DR** (renders as an italic left-bordered callout):
```markdown
> Coppell is eight weeks out from a council-level decision about what follows Privacy Solutions credit-monitoring. That's the forcing function.
```

**Rule 3 — Key-value bullets** (render as a two-column grid with an uppercase indigo label pill + value):
```markdown
- **Contact authority:** Technical Evaluator — not Champion; Josh Littrell owns the decision
- **Deal size estimate:** $55K bundle at DIR-TSO-4099 pricing
```

**Rule 4 — Labelled callout boxes** — paragraphs that open with a known sentinel like `**Why:**`, `**Mitigation:**`, `**Action:**`, `**Trigger:**`, `**Watch for:**`, `**Note:**`, or `**Key insight:**` render as color-accented callout boxes (purple for `Why`, green for `Mitigation`, blue for `Action`, amber for `Trigger`, red for `Watch for`, cyan for `Note`/`Key insight`). Use liberally where the prose naturally has a labelled beat:
```markdown
**Watch for:** Microsoft Sentinel/Defender XDR is the likely-but-unconfirmed SIEM incumbent. First discovery question.
```

**Rule 5 — Tier + confidence pills** — every sourced claim gets an inline `[A]` / `[B]` / `[C]` tier pill (renders as a colored badge). `[CONFIRMED]` / `[ESTIMATED]` / `[INFERRED]` confidence pills go next to quantified claims (renders as colored pills). The metadata line uses plain ` · ` (U+00B7 middle dot with spaces) as a field separator — NOT `&nbsp;` or `&amp;nbsp;`, which render as literal text because the renderer HTML-escapes ampersands.

**Rule 6 — Target density.** HOT dossiers should land at 18K–25K chars of `full_dossier_markdown`. Significantly more usually means the Rule 1 non-duplication check wasn't applied.

**Rule 7 — RocketReach provenance marker (ELISS v7.1+).** Every value sourced from the RocketReach API must display an inline `ᴿᴿ` marker immediately after the value. The renderer converts this to an orange `RR` pill with a "Sourced from RocketReach premium account (Tier-B, verified)" tooltip so the rep reading the report instantly knows which claims are RR-verified vs. free-OSINT-sourced vs. inferred.

- **Prose example:** `"Gabriel Colon-Atencioᴿᴿ [CONFIRMED] [B]"`
- **KV-bullet example:** `- **Email:** gabriel.colon@coppelltx.govᴿᴿ [CONFIRMED] [B]`
- **Phone example:** `- **Phone:** +1-972-462-0022ᴿᴿ [A-]`
- **Applies to:** name, title, email, phone, linkedin_url, skills, employer and every field populated from `/person/lookup`, `/person/search`, `/profile-company/lookup`, `/bulkLookup`, `/company/lookup/`, `/searchCompany`.

In the structured JSON (subagent fragments → consolidated dossier JSON), same provenance is carried as **per-field flags** so Tab 1 card renderers can emit the pill inline on dashboard values without needing the markdown glyph:

```json
"lead": {
  "name": "Gabriel Colon-Atencio", "_rocketreach_name": true,
  "email": "gabriel.colon@coppelltx.gov", "_rocketreach_email": true, "email_grade": "A-",
  "linkedin_url": "https://...", "_rocketreach_linkedin_url": true
},
"company": {
  "num_employees": 448, "_rocketreach_num_employees": true,
  "revenue": 72000000, "_rocketreach_revenue": true,
  "techstack": ["Microsoft 365","SharePoint"], "_rocketreach_techstack": true
},
"org_intelligence": {
  "champion": {"name":"Josh Littrell", "_rocketreach": true, "linkedin_url":"...", "_rocketreach_linkedin_url": true}
}
```

Using per-field flags rather than a single `_rocketreach` boolean keeps granularity — a DMU member whose `name` was verified by RR but whose `phone` was pulled from a conference bio only marks the name as RR-sourced.

**Rule 7b — `meta.rocketreach_budget` (ELISS v7.1+).** At dossier finalization, copy `client.budget_summary()` output verbatim into `meta.rocketreach_budget`. Schema:

```json
"meta": {
  "version": "7.1.0",
  "analyst": "ELISS v7.1.0",
  "rocketreach_budget": {
    "endpoints_called": {"account": 1, "company_lookup": 2, "person_lookup": 18, "person_search": 4, "bulk_lookup": 1, "profile_company_lookup": 3, "company_search": 2, "check_status": 0},
    "credits_consumed": {"person_export": 21, "company_export": 2, "person_search": 4, "company_search": 2},
    "session_totals": {"account_checks": 1, "company_lookups": 2, ...},
    "first_call_at": "2026-04-24T01:12:00Z",
    "last_call_at":  "2026-04-24T01:14:30Z",
    "total_calls": 31
  }
}
```

Rendered as a small footnote under Tab 1's Data Quality panel so the rep can see at a glance "this dossier cost 21 person_export + 2 company_export credits." Omit the block entirely when `RR_API_KEY` is unset and no RR calls were made.

```markdown
# ELISS Intelligence Dossier

**Lead:** [Full Name] · **Company:** [Company Name] · **Email:** [email] · **Generated:** [Today's Date] · **Analyst:** ELISS v7.1.0 — ManageEngine Intelligence

---

## SCORE SUMMARY

| Dimension | Score | Max | Confidence | Key Driver |
|---|---|---|---|---|
| Fit | X | 25 | HIGH/MED/LOW | [one phrase, e.g. "1,200-emp healthcare, AD confirmed"] |
| Intent | X | 25 | HIGH/MED/LOW | [e.g. "Active SIEM eval + compliance audit"] |
| Timing | X | 30 | HIGH/MED/LOW | [e.g. "Splunk renewal ~Q3 2026; HIPAA deadline aligned"] |
| Budget | X | 20 | HIGH/MED/LOW | [e.g. "IT Director, ~$200K authority"] |
| **COMPOSITE** | **X** | **100** | **[Overall]** | |

**Final Score:** X/100 | **Tier:** [HOT/WARM/COOL/COLD] | **Confidence:** [HIGH/MEDIUM/LOW]
**Risk-Adjusted Composite (ELISS v5.6+):** [Raw − sum of Deal Execution Risks] — [one-line interpretation, e.g. "Still HOT, but focus mitigation on the unconfirmed-incumbent risk first"]
**Validation Applied:** [List any caps, decay, triangulation, or structural negative modifiers — or "None"]
**Recommended Action:** [PURSUE NOW / NURTURE / MONITOR / DEPRIORITIZE]
**ICP Match:** [Strong / Moderate / Weak] — [one sentence why]

---

## EXECUTIVE BRIEF

[3–5 sentences. Who is this person, what's their situation, why do they need AD360/Log360 right now (or not), what's the #1 risk, and what should the sales rep do first. Write this like a 30-second pre-call briefing.]

---

## PERSON PROFILE

- **Name:** [Full name] [CONFIRMED]
- **Title:** [Title] [CONFIRMED/ESTIMATED]
- **Seniority:** [C-Suite / VP / Director / Manager / IC]
- **Decision Authority:** [Budget owner / Influencer / Evaluator]
- **Tenure:** [X years] [CONFIRMED/ESTIMATED]
- **Career Path:** [2-3 sentences — where they came from, trajectory]
- **Public Presence:** [Talks, articles, social activity — or "Limited"]
- **Personalization Hooks:** [What topics they care about, what language to use, conversation openers based on their background]

---

## COMPANY PROFILE

- **Company:** [Name] | **Website:** [domain]
- **Industry:** [Vertical — Sub-vertical]
- **Employees:** [Count] [CONFIRMED/ESTIMATED] (Source: [source])
- **Est. Revenue:** [$X–$Y] [ESTIMATED] (Basis: [show math])
- **HQ:** [City, Country] | **Ownership:** [Public/Private/PE/VC]
- **Growth Stage:** [Early / Growth / Scale / Mature]
- **Recent News:** [2-3 most relevant recent developments]

---

## TECHNOLOGY & SECURITY POSTURE

- **AD/Identity Environment:** [What's confirmed about their AD setup — this is the #1 signal for AD360]
- **Security Stack:** [Known security tools, SIEM, IAM solutions]
- **Cloud Posture:** [Cloud-native / Hybrid / On-prem]
- **Digital Maturity:** [Pioneer / Adopter / Follower / Laggard]

**Competitive Threat Matrix (ELISS v5.6+):**

Never write "None detected" as the full competitive picture. If no incumbent is directly confirmed, infer the most plausible competitors from the tech-stack profile and list them with explicit basis.

| Competitor | Presence Likelihood | Evidence / Basis | Displacement Angle | Threat Level |
|---|---|---|---|---|
| [Vendor] | Likely / Possible / Unlikely | [What the inference rests on — direct evidence, stack profile, recent event, hiring signal] | [From product-icp.md playbook — the specific winning frame vs. this competitor] | 🔴 Critical / 🟡 Moderate / 🟢 Low |

**Competitive Readiness Score:** X/10 — [One-line justification against the most likely incumbent. Weigh product fit, pricing leverage, brand recognition in segment, channel coverage.]

**Displacement Opportunity:** [If a Likely/Critical competitor is named, state the primary play here. If truly greenfield, state what would still threaten the deal — usually "incumbent arrives late via procurement RFP".]

**Contract Renewal Intelligence (ELISS v5.5+):**

| Incumbent | Est. Renewal | Confidence | Basis |
|---|---|---|---|
| [Vendor name] | [YYYY-MM or "Q3 2027"] | HIGH/MED/LOW | [Source: press release, SAM.gov contract, job posting wording, etc.] |

**Renewal-Window Timing Impact:** [Which incumbent's renewal is closest? Does it fire a Timing tier (e.g. "Splunk renewal Q3 2026 → Strong trigger, +18 Timing") or the `recently_renewed_lockout` negative modifier? If no incumbents detected, write "N/A — greenfield."]

---

## ORGANIZATIONAL INTELLIGENCE

**Decision-Making Unit (mapped):**
| Role | Person | Title | Relevance |
|---|---|---|---|
| Economic Buyer | [Name or "Unknown"] | [Title] | Controls budget |
| Technical Evaluator | [Name or "Unknown"] | [Title] | Runs POC |
| Champion | [Name or "Unknown"] | [Title] | Feels the pain |
| Potential Blocker | [Name or "Unknown"] | [Title] | [Why they might resist] |

**Multi-Threading Strategy:** [How to approach multiple stakeholders — who to reach first, what angle for each]

**Local Autonomy Assessment (ELISS v5.5+):**
- **Classification:** [HIGH / MEDIUM / LOW]
- **Parent Entity:** [Parent/global org name, or "N/A — standalone"]
- **Global Incumbents Detected:** [Any parent-level incumbents (Splunk, SailPoint, Microsoft) that mandate local standardization, or "None"]
- **Rationale:** [1–2 sentences. E.g. "AIG Israel runs local security tooling under $200K threshold independently, but SIEM is mandated globally via Splunk → MEDIUM autonomy for AD360 (feasible), LOW autonomy for Log360 (blocked)."]
- **Impact:** [Which dimensions/modifiers this affects. LOW autonomy fires the `low_local_autonomy` (−12) negative modifier.]

**Ghost Stakeholders — Open Roles in the Hiring Pipeline (ELISS v5.6+):**

Open roles currently being hired that will own part of the evaluation once filled. These people don't exist yet at the company, but they will — and their first 90 days usually define the tool shortlist. Check careers page, LinkedIn Jobs, governmentjobs.com (public sector), and press releases for any security / IT leadership / SIEM / IAM / cloud roles posted in the last 90 days.

| Open Role | Status | Est. Arrival | Role Scope | Risk | Opportunity | Action |
|---|---|---|---|---|---|---|
| [Title, e.g. "Information Security Engineer"] | Posted / Interviewing / Offer-stage / Unknown | [60–90 days / Q3 2026 / Unknown] | [Will own SIEM eval / Will drive IAM decision / Will shape RFP] | [Why this is a risk — e.g. "new hire bias toward their previous vendor"] | [Why this is an opportunity — e.g. "blank slate, no loyalty to existing tools yet"] | [Specific play — e.g. "Monitor job close; reach out to hiring manager (Josh) to mention AD360/Log360 familiarity as 'plus' in the JD"] |

If no relevant open roles detected after active search, write "No ghost stakeholders detected (confirmed via careers page + LinkedIn Jobs review [date])." An empty card without that confirmation means the analyst didn't look.

---

## IT BUDGET & PURCHASING POWER

- **Est. Annual IT Spend:** [$X–$Y] [ESTIMATED]
- **Calculation:** [Show the math: employees × rev/emp × IT% = budget]
- **Est. Security Budget:** [$X–$Y] (midpoint $Z; subset of IT)
- **IAM & IGA Sub-Budget:** [$X] [ESTIMATED] — 12% of $Z security budget midpoint
- **SIEM Sub-Budget:** [$X] [ESTIMATED] — 15% of $Z security budget midpoint
- **AD360/Log360 Affordability:** [Trivial / Comfortable / Feasible / Stretch]
- **Est. Deal Size (Year 1):** [$X] — [Show the sizing basis — see rubric below]
- **Budget Trend:** [Growing / Stable / Shrinking]
- **Contact's Deal Authority:** [$X limit]
- **Procurement:** [Self-serve / Standard / Enterprise / Government]
- **Est. Deal Cycle:** [X–Y months]

**Budget Sub-Allocation (ELISS v5.4+):**
- IAM & IGA Budget = 12% of Security Budget — addressable market for AD360
- SIEM Budget = 15% of Security Budget — addressable market for Log360
- Cross-check: AD360 component <30% of IAM sub-budget = "Comfortable"; >50% = "Stretch"
- Cross-check: Log360 component <30% of SIEM sub-budget = "Comfortable"; >50% = "Stretch"

**Deal Sizing Rubric (use explicitly — do not skip or default to $40K):**
1. **Start with list-price math:** `headcount × ~$1–2/user/month × 12 = full list price/year`. Use $1 for a single product (AD360 *or* Log360 alone), $2 for the combined AD360+Log360 bundle. This is the ceiling for a greenfield full-stack buy.
2. **Apply scenario scaling:**
   - **Greenfield full-stack** (no major competitor, ICP sweet spot): **80–100%** of list
   - **Sidecar / coexist** (some competitor presence, ME as complement): **20–40%** of list
   - **Subsidiary / business-unit only** (incumbent competitor at parent, ME at a division): **10–20%** of list
   - **Point-tool** (single product, e.g. ADManager Plus only): **5–15%** of list
3. **Cross-check against security budget and sub-budgets:** Deal should be **0.05%–8%** of estimated security budget. Additionally, cross-check AD360 component against IAM & IGA sub-budget (12% of security) and Log360 component against SIEM sub-budget (15% of security). If any component exceeds 50% of its sub-budget, flag as "Stretch."
4. **Apply floors and ceilings:** Floor **$20K** (minimum viable ME enterprise deal), ceiling **$800K** (above this, you're competing with Tier-1 vendors on enterprise RFP, not ME's strength).
5. **Show the math** in `deal_size_basis` — reviewer must be able to follow from headcount → list → scenario → final number.

---

## COMPLIANCE MAPPING

| Framework | Pressure | AD360 Angle | Log360 Angle | Urgency |
|---|---|---|---|---|
| [Framework] | HIGH/MED/LOW | [Specific hook] | [Specific hook] | [Deadline or trigger] |

**Compliance-Driven Urgency:** [Is there an audit, deadline, or finding creating time pressure?]

---

## BUYING SIGNALS & RISK FLAGS

**Positive Signals:**
- [Signal] — Source: [source] — Age: [freshness] — Points: +X — Confidence: [H/M/L]

**Risk Flags:**
- [Flag] — Impact: −X points — Evidence: [source] — Mitigation: [what to do about it]

**Net Assessment:** [1-2 sentences: is this prospect accelerating toward purchase or stalled?]

---

## SCORING RATIONALE

**Fit (X/25):** Company Size X/8 + Industry X/7 + Title X/6 + Tech X/4. [Justify each.]

**Intent (X/25):** [Which categories scored, which evidence, triangulation applied (>15 from one category → ×0.80)?]

**Timing (X/30):** [Which trigger factor, evidence, freshness. If renewal-window trigger applied, name the incumbent and renewal window.]

**Budget (X/20):** Authority X/8 + Capacity X/7 + Procurement X/5. [Justify each.]

**Validation:** [Which structural rules fired and impact — caps, decay, triangulation, structural negative modifiers — or "None"]

---

## DEAL EXECUTION RISKS (ELISS v5.6+)

Soft friction factors separate from the structural negative modifiers above. These don't disqualify the lead but are the reasons a HOT score can still stall. Each row carries a weight in the −2 to −5 range; the sum is subtracted from the raw composite to produce the **Risk-Adjusted Composite** shown in the Score Summary.

| Risk Factor | Weight | Evidence | Mitigation | Mitigation Credibility |
|---|---|---|---|---|
| [e.g. "Champion new to role, limited political capital"] | −3 | [Evidence from dossier — tenure, DMU position] [optional: footnote-style URLs that map to `evidence_urls` in JSON] | [Specific mitigation play] | HIGH / MEDIUM / LOW |
| [e.g. "Unconfirmed-but-likely Microsoft Sentinel incumbent"] | −5 | [Stack profile, inference basis] | [Complement-don't-displace messaging] | HIGH / MEDIUM / LOW |
| [e.g. "Small deal size may get deprioritized by field reps"] | −2 | [Deal sizing output] | [Channel / DIR / inside sales path] | HIGH / MEDIUM / LOW |

**Evidence URLs (ELISS v5.7+):** Each row in the JSON `scoring.deal_execution_risks[]` array can include an `evidence_urls` field — an array of strings — that the report generator renders as inline numbered link chips next to the evidence text. This lets the rep verify any claim in one click. Backward compatible: if `evidence_urls` is omitted or empty, the row renders without chips, exactly as in v5.6.

**Total Risk Adjustment:** −X
**Risk-Adjusted Composite:** [Raw composite] − [X] = **[Adjusted]**/100
**Interpretation:** [One line. E.g. "Raw 90 → Adjusted 77. Still HOT, but the unconfirmed-Sentinel risk is the first thing to neutralize on a discovery call."]

---

## STRATEGIC RECOMMENDATIONS

**Action:** [PURSUE NOW / NURTURE / MONITOR / DEPRIORITIZE]

**Next Steps:**
1. [Specific action + timing + owner]
2. [Specific action + timing]
3. [Specific action + timing]

**AD360 Talking Points:**
- [Hook personalized to their AD/identity pain]
- [Compliance angle specific to their frameworks]
- [ROI/cost frame for their size]

**Log360 Talking Points:**
- [Hook personalized to their security/SIEM situation]
- [Competitive differentiation if competitor detected]
- [Compliance automation angle]

**Objection Prep:**
- "[Most likely objection]" → [Response from product-icp.md playbook]
- "[Second objection]" → [Response]

**Outreach Strategy:** [Channel + timing + personalization hook from their social/conference presence]

---

## DEMO PLAYBOOK (ELISS v7.4+)

The persona-anchored demo blueprint for this prospect. Tab 1 renders a structured card from `demo_playbook{}` (opening hook + per-product value moments + discovery questions + objections + CTA). **This Tab 2 section is the prose narrative the rep reads in the 30 minutes before the call** — what the rep tells the SE to prep, in plain English. HOT/WARM dossiers must populate this; COOL/COLD may omit.

> [Blockquote: one-sentence demo thesis — the single value moment the rep wants the prospect to remember 24 hours after the call.]

**Persona anchor:** [Role + 1–2 sentence operating context. e.g., "IT Director at a CJIS-bound municipality reporting to a Council-elected official; technical enough to read a correlation rule, political enough to flinch at rip-and-replace."]

**Opening hook (90-second cold open):** [The dossier-grounded narrative the rep opens with. NOT a product feature — a reframe of the prospect's specific situation that earns the next 12 minutes. Cite a public artifact already referenced elsewhere in this dossier.]

### AD360 — Three Value Moments (NOT a feature tour)

Each moment: title, why-it-matters in one sentence tied to a dossier fact, then a Tell-Show-Tell script.

**Value Moment 1 — [Title, e.g. "Self-service password reset with auditable trail"]**
- **Why it matters for this prospect:** [Tie to a specific dossier fact — helpdesk volume, audit finding, recent hire, compliance pressure.]
- **Tell-Show-Tell:** *Tell:* [the claim, one sentence] / *Show:* [the one screen or workflow named, not a tour] / *Tell:* [the takeaway sentence the rep wants the prospect to repeat to their CIO afterwards].

**Value Moment 2 — [Title]**
- **Why it matters for this prospect:** [Dossier-anchored reason]
- **Tell-Show-Tell:** *Tell:* [claim] / *Show:* [workflow] / *Tell:* [takeaway]

**Value Moment 3 — [Title]**
- **Why it matters for this prospect:** [Dossier-anchored reason]
- **Tell-Show-Tell:** *Tell:* [claim] / *Show:* [workflow] / *Tell:* [takeaway]

**Discovery questions to ask DURING the AD360 segment:**
- [Question 1 — open-ended, tied to a hypothesis from the dossier]
- [Question 2 — designed to surface incumbent-tool pain]
- [Question 3 — designed to identify the economic buyer]

**Top 2 objections to expect on AD360 (from product-icp.md playbook):**
- *"[Objection verbatim]"* → [Response framework, customized to this prospect's situation. Not the generic playbook response — the version that incorporates this dossier's specifics.]
- *"[Second objection]"* → [Customized response]

**CTA after AD360 segment:** [A specific micro-commitment — not "want to see Log360?". Something like "Should we map this to your password-reset SLA before moving on?" or "Want me to put this against your current Okta config in a side-by-side doc?"]

### Log360 — Three Value Moments (NOT a feature tour)

Same structure. Each moment must connect to a signal in this prospect's dossier — their incumbent SIEM's per-GB cost, a specific compliance control they need to evidence, a recent breach in their vertical, an OCR resolution agreement, or a known audit window.

**Value Moment 1 — [Title]**
- **Why it matters for this prospect:** [Dossier fact]
- **Tell-Show-Tell:** *Tell:* [claim] / *Show:* [workflow] / *Tell:* [takeaway]

**Value Moment 2 — [Title]**
- **Why it matters for this prospect:** [Dossier fact]
- **Tell-Show-Tell:** *Tell:* [claim] / *Show:* [workflow] / *Tell:* [takeaway]

**Value Moment 3 — [Title]**
- **Why it matters for this prospect:** [Dossier fact]
- **Tell-Show-Tell:** *Tell:* [claim] / *Show:* [workflow] / *Tell:* [takeaway]

**Discovery questions to ask DURING the Log360 segment:**
- [Question 1]
- [Question 2]
- [Question 3]

**Top 2 objections to expect on Log360:**
- *"[Objection]"* → [Customized response]
- *"[Second objection]"* → [Customized response]

**Closing CTA (end of demo):** [The specific ask. Should NOT be "send me a proposal" — should be a concrete next step the prospect can commit to before they leave the call. e.g., "Let's schedule the 60-minute architecture deep-dive with your SecEng lead by Friday" or "Can you forward the one-page CJIS mapping to your CISO before next council session?"]

**Demo-Day Risk to Watch:** [The single most likely thing that will derail this demo, drawn from the dossier — e.g., "Prospect's CIO joins late and asks 'why not just expand Sentinel'; have the cost-tier comparison ready in slide form" or "Champion's manager is the actual decision-maker and isn't on the invite — get a 15-min follow-up booked with them before the demo ends".]

---

## PRE-MORTEM (ELISS v5.6+)

**If we lose this deal, the most likely reasons will be:**

List 3–5 specific, evidence-grounded loss scenarios. Each must be tied to something in THIS dossier — generic reasons ("we didn't follow up fast enough") are not acceptable. For each scenario, name the mitigation and the earliest signal the rep should watch for.

1. **[Loss scenario title]** — [Why this could happen, grounded in dossier evidence]
   → **Mitigation:** [Specific play]
   → **Earliest signal to watch for:** [What the rep will see if this risk is materializing]

2. **[Loss scenario title]** — [Evidence]
   → **Mitigation:** [Play]
   → **Earliest signal to watch for:** [Signal]

[Continue for 3–5 total]

---

## REP READINESS CHECKLIST (ELISS v5.6+)

Before the rep sends their first outreach, they should be able to tick all of these. Each item is a concrete fact or preparation specific to this account — not generic sales hygiene.

- [ ] I have read [Contact]'s career history and know [specific detail that shapes tone — e.g. "military IT background, not marketing-pitch receptive"]
- [ ] I know NOT to [specific anti-pattern for this account — e.g. "lead with the breach as if they lived through it"]
- [ ] I have [specific artifact] ready to attach/reference [e.g. "CJIS audit-log checklist one-pager"]
- [ ] I can articulate why AD360/Log360 [complements / displaces / coexists] with [most likely incumbent]
- [ ] I know who [champion/economic buyer] is and can reference [specific shared context — association, prior role, etc.]
- [ ] I have verified [procurement path — DIR contract, existing MSA, etc.]
- [ ] I can frame the deal in terms the [economic buyer role] responds to — [compliance / risk / cost / outcome]
- [ ] I have a specific ask for the first meeting ([discovery call / POC scoping / executive briefing])

---

## RESEARCH SOURCES

Tag each source with its reliability tier (ELISS v5.6+):
- **[A]** = Authoritative — official gov filings (SEC, .gov, SAM.gov), company press releases, earnings transcripts, peer-reviewed research, regulatory action notices
- **[B]** = Reputable secondary — established tech/business press (Reuters, WSJ, The Record, SC Media, Comparitech), industry analyst notes, primary LinkedIn profiles
- **[C]** = Aggregator / inferred — ZoomInfo, RocketReach, LeadIQ, Glassdoor, rumor blogs, or any analyst inference

**Person:** [URL] [A/B/C], [URL] [A/B/C]
**Company:** [URL] [A/B/C]
**Technology:** [URL] [A/B/C]
**Financial:** [URL] [A/B/C]
**Compliance:** [URL] [A/B/C]

---

## DATA QUALITY

**Overall Confidence:** [HIGH / MEDIUM / LOW]
**Top Assumptions:** [2-3 biggest assumptions affecting the score]
**Data Gaps:** [What's missing and how it changes the picture]
**To Improve:** [Specific actions to increase confidence]
```

---

## JSON Schema for Report Generation

After presenting the conversational dossier, write a JSON file with this schema. The `generate_report.py` script consumes this to produce HTML/PDF reports.

```json
{
  "meta": {
    "version": "6.2.5",
    "generated": "2026-04-23",
    "analyst": "ELISS v6.2.5"
  },
  "lead": {
    "name": "Full Name",
    "email": "email@company.com",
    "title": "VP of IT Security",
    "seniority": "VP",
    "authority": "Budget owner",
    "tenure": "4 years",
    "linkedin": "url or null",
    "personalization_hooks": ["hook1", "hook2"]
  },

  // === lead.title discipline (v7.5.2) ===
  // The renderer splices `lead.title` directly into the Tab 1 lead-sub
  // header (`<title> at <company> • <email>`) and the Person Profile field.
  // It is real estate for *who this person is*, NOT for the verification
  // process. If RR + LinkedIn + web search all fail to verify the title,
  // write `"Title to be confirmed"` (or empty string — the renderer falls
  // back to that placeholder). Document the verification effort in
  // `data_quality.gaps[]` and the qualitative narrative in
  // `org_intelligence.champion.note` only — never the title field.
  //
  // Anti-patterns the renderer now strips (substituted with
  // "Title to be confirmed"):
  //   - "Unknown — verification incomplete after N OSINT angles"
  //   - "Unverified after ..."
  //   - "unknown role" / "role unknown" / "unknown title" / "title unknown"
  //   - bare "Unknown" (case-insensitive)
  //   - any title starting with "Unknown —" / "Unknown -"
  //
  // The header line should always read as a clean identity line, not a
  // process log.
  "company": {
    "name": "Company Name",
    "domain": "company.com",
    "industry": "Financial Services",
    "sub_industry": "Banking",
    "employees": 3200,
    "employees_confidence": "CONFIRMED",
    "revenue_estimate": "$1.4B–$1.8B",
    "hq": "New York, USA",
    "ownership": "Public",
    "growth_stage": "Mature",
    "recent_news": ["News item 1", "News item 2"],
    "micro_segment": "Regional bank, 50–200 branches, mid core-consolidation, OCC-examined",
    "operating_model": "SecOps team of ~28 in two regional hubs running 24×5 in-house coverage with weekend on-call rotations; IAM split across an Identity Engineering team and the Cyber Defense Center. Change management runs through a weekly CAB with mandatory Risk and Compliance sign-off."
  },
  "_company_note": "ELISS v7.5+ (Mom Test upgrade): `micro_segment` is REQUIRED — a who-where slice from `references/vertical-playbook.md` (NOT the bare vertical name). `operating_model` is REQUIRED — 2–3 sentences in customer language describing day-to-day operating reality (team size, shift pattern, change-window cadence, approval chain). Populated by Subagent A.",
  "technology": {
    "ad_environment": "Confirmed — Active Directory + Azure AD hybrid",
    "security_stack": ["Tool1", "Tool2"],
    "cloud_posture": "Hybrid",
    "digital_maturity": "Adopter",
    "competitors_detected": ["Splunk"],
    "displacement_angle": "TCO — Splunk's per-GB pricing vs. Log360 flat rate",
    "competitive_threat_matrix": [
      {"competitor": "Splunk", "presence_likelihood": "Likely", "basis": "Direct evidence — press release Q3 2023", "basis_urls": ["https://www.splunk.com/en_us/newsroom/press-releases.html"], "displacement_angle": "TCO assault — $/GB vs. flat pricing; integrated DLP/CASB included", "threat_level": "Critical"},
      {"competitor": "Microsoft Sentinel", "presence_likelihood": "Possible", "basis": "Enterprise E5 licensing common; customer is partial MS shop", "displacement_angle": "Complement for on-prem + multi-cloud gaps; avoid direct displacement", "threat_level": "Moderate"},
      {"competitor": "CrowdStrike Falcon", "presence_likelihood": "Unlikely", "basis": "No EDR hiring signals or press mentions", "displacement_angle": "N/A — different tier (EDR vs. SIEM)", "threat_level": "Low"}
    ],
    "competitive_readiness_score": 7,
    "competitive_readiness_basis": "7/10 vs. Splunk — strong on price and compliance specificity; weaker on custom analytics at scale. Recommend POC-driven comparison.",
    "renewal_intelligence": [
      {"incumbent": "Splunk", "estimated_renewal": "Q3 2026", "confidence": "MEDIUM", "basis": "Press release announced Splunk selection Q3 2023; standard 3-year enterprise cycle"}
    ]
  },
  "_technology_note": "ELISS v5.6+: competitive_threat_matrix[] is REQUIRED. Never leave empty or write 'None detected' as the full picture. When no direct evidence exists, produce inferred rows with Likely/Possible/Unlikely likelihood labels and explicit basis. competitive_readiness_score is a 1–10 integer against the most likely incumbent. ELISS v5.7+: each row may include an optional `basis_urls` array that renders as inline numbered link chips next to the basis text.",
  "scoring": {
    "fit": {"score": 22, "max": 25, "confidence": "HIGH", "breakdown": {"company_size": 8, "industry": 7, "title": 5, "tech_alignment": 2}},
    "intent": {"score": 18, "max": 25, "confidence": "MEDIUM", "signals": [{"category": "Compliance need", "points": 10, "evidence": "SOX audit Q2"}, {"category": "Hiring", "points": 6, "evidence": "CISO posting"}], "triangulation_applied": false},
    "timing": {"score": 18, "max": 30, "confidence": "MEDIUM", "factor": "Strong trigger", "evidence": "Splunk renewal estimated Q3 2026 (6–12 month window); SOX audit deadline aligned"},
    "budget": {"score": 14, "max": 20, "confidence": "MEDIUM", "breakdown": {"authority": 5, "capacity": 7, "procurement": 2}},
    "composite": 72,
    "final_score": 72,
    "tier": "WARM",
    "overall_confidence": "MEDIUM",
    "validation": {"stale_cap": false, "confidence_cap": false, "decay_applied": false, "decay_weeks": 0},
    "negative_modifiers": [],
    "deal_execution_risks": [
      {"risk": "Champion new to role, limited political capital", "weight": -3, "evidence": "VP hired ~8 months ago per LinkedIn", "evidence_urls": ["https://www.linkedin.com/in/example-vp/"], "mitigation": "Multi-thread to Director of IT Security early", "mitigation_credibility": "MEDIUM"},
      {"risk": "Likely Microsoft Sentinel coexistence", "weight": -5, "evidence": "Partial MS shop with E5 licensing", "evidence_urls": ["https://example.com/press-release-microsoft-partner", "https://learn.microsoft.com/azure/sentinel/"], "mitigation": "Lead with complement-not-displace positioning; on-prem and CJIS gaps", "mitigation_credibility": "HIGH"}
    ],
    "total_risk_adjustment": -8,
    "risk_adjusted_composite": 64,
    "icp_match": "Strong",
    "icp_match_reason": "3,200-emp bank with AD + compliance pressure",
    "earlyvangelist": {
      "has_problem": {"value": true, "evidence": "Open OCC MRA on user-access-review cadence (last exam cycle)", "source_url": "https://www.occ.gov/news-issuances/enforcement-actions/..."},
      "knows_problem": {"value": true, "evidence": "Job posting for IAM Architect names 'access review automation' as #1 priority", "source_url": "https://www.linkedin.com/jobs/view/1234567890"},
      "has_budget": {"value": true, "evidence": "FY26 budget amendment for Identity Modernization filed Q1", "source_url": "https://example.gov/legistar/agenda-2026-03-12"},
      "has_makeshift_solution": {"value": true, "evidence": "IAM lead manually reconciles CSV exports against AD before each quarterly review", "source_url": null},
      "count": 4,
      "rationale": "4/4 pips — earlyvangelist-strong. The workaround (manual CSV reconciliation) is the single most actionable evidence: that pain is real today, every quarter, and there's a named operator who owns it."
    }
  },
  "_scoring_note": "ELISS v5.6+: deal_execution_risks[] and risk_adjusted_composite are REQUIRED. Execution risks are soft friction factors (−2 to −5 each), separate from the structural negative_modifiers list. Tier is determined by raw composite; risk_adjusted_composite is shown alongside to focus mitigation energy. An empty deal_execution_risks[] array is almost always a sign the analyst hasn't looked hard enough. ELISS v5.7+: each risk row may include an optional `evidence_urls` array (list of URLs); the report renders these as inline numbered link chips next to the evidence text. Backward compatible — v5.6 dossiers without `evidence_urls` render unchanged.",
  "budget_analysis": {
    "estimated_it_spend": "$136M–$216M",
    "it_pct_revenue": "9.5%",
    "security_budget": "$20M–$43M",
    "iam_iga_budget": "$3.8M",
    "iam_iga_basis": "12% of $31.5M security budget midpoint",
    "siem_budget": "$4.7M",
    "siem_budget_basis": "15% of $31.5M security budget midpoint",
    "affordability": "Trivial",
    "estimated_deal_size": "$75K",
    "deal_size_basis": "REQUIRED field. Show math: 3,200 emp × $2/user/mo × 12 = $76.8K list (AD360+Log360 bundle), scenario: greenfield full-stack at 95% = $73K → rounded to $75K. Cross-check: 0.25% of $30M security budget → inside 0.05-8% band → valid. AD360 component $38K / $3.8M IAM = 1.0% ✓. Log360 component $37K / $4.7M SIEM = 0.8% ✓.",
    "budget_trend": "Growing",
    "deal_authority": "$200K",
    "procurement": "Standard",
    "deal_cycle_months": "2–4",
    "calculation_basis": "3,200 emp × $500K rev/emp = $1.6B → 9.5% IT → 17% security"
  },
  "_budget_analysis_note": "estimated_deal_size, deal_size_basis, iam_iga_budget, and siem_budget are REQUIRED — do not omit. The report generator defaults to $40K when deal_size is missing, which breaks the budget waterfall. IAM & IGA budget = 12% of Security Budget; SIEM budget = 15% of Security Budget. Always calculate using the Deal Sizing Rubric and Budget Sub-Allocation Rules in the conversational template above.",
  "compliance": [
    {"framework": "SOX", "pressure": "HIGH", "ad360_angle": "Access certification, segregation of duties", "log360_angle": "Audit trail, change monitoring", "urgency": "Q3 2026 audit"},
    {"framework": "PCI-DSS", "pressure": "MEDIUM", "ad360_angle": "Privileged access, password policies", "log360_angle": "Log monitoring, file integrity", "urgency": "Annual assessment"}
  ],
  "org_intelligence": {
    "economic_buyer": {"name": "Jane Smith", "title": "CIO"},
    "technical_evaluator": {"name": "Unknown", "title": ""},
    "champion": {"name": "Lead Contact", "title": "VP IT Security"},
    "representative_pain_owner": {
      "name": "Marcus Chen",
      "title": "IAM Architect",
      "why": "Runs the quarterly user-access-review meat-grinder; reconciles CSV exports manually before every review cycle. The person who actually lives the open MRA, distinct from the CIO who hears about it at quarterly Risk Committee.",
      "source_url": "https://www.linkedin.com/in/example-iam-architect/"
    },
    "blocker": {"name": "Unknown", "title": "", "risk": ""},
    "local_autonomy": {
      "classification": "HIGH",
      "parent_entity": "N/A — standalone",
      "global_incumbents": [],
      "rationale": "Standalone US entity; no parent-level security stack mandates detected.",
      "impact": "No modifier fired; pursue normally."
    },
    "future_stakeholders": [
      {
        "role": "Information Security Engineer",
        "status": "Posted (open req)",
        "estimated_arrival": "60-90 days",
        "role_scope": "Will own SIEM/IAM technical evaluation day-to-day",
        "risk": "New hire bias toward previous vendor; could arrive with CrowdStrike or Splunk loyalty",
        "opportunity": "Blank slate — no tool loyalty yet; reachable before they start",
        "action": "Monitor governmentjobs.com for closure; reach out to hiring manager (Josh Littrell) to mention AD360/Log360 skillset as 'plus' in the JD"
      }
    ],
    "multi_thread_strategy": "Approach CIO via champion intro; position as compliance risk mitigation"
  },
  "_org_intelligence_note": "DMU `title` fields should be the concise job title only. future_stakeholders[] is REQUIRED (ELISS v5.6+); an empty array is acceptable only if the analyst has actively searched careers page + LinkedIn Jobs + relevant job boards and confirmed no relevant open roles (note the check in data_quality.gaps). `local_autonomy.classification` must be HIGH/MEDIUM/LOW — LOW fires the `low_local_autonomy` (−12) negative modifier.",
  "signals": {
    "positive": [
      {"id": "sig-001", "signal": "CISO hiring", "source": "LinkedIn job posting", "age_days": 14, "points": 6, "confidence": "HIGH", "evidence_urls": ["https://www.linkedin.com/jobs/view/1234567890"], "signal_category": "hiring", "signal_symbol": "♀"},
      {"id": "sig-002", "signal": "Splunk 3-year renewal window opening", "source": "USAspending contract end date 2026-09-30", "age_days": 7, "points": 8, "confidence": "HIGH", "evidence_urls": ["https://www.usaspending.gov/award/CONT_AWD_12345"], "signal_category": "procurement_cycle", "signal_symbol": "$", "obstacle": "Multi-year incumbent inertia + Splunk's regulator-familiar audit reports", "workaround": "IT team building parallel ELK cluster in dev to test displacement risk before RFP"},
      {"id": "sig-003", "signal": "FY27 budget amendment for endpoint security", "source": "Council Legistar agenda 2026-03-12 item 7", "age_days": 21, "points": 10, "confidence": "HIGH", "evidence_urls": ["https://city.legistar.com/..."], "signal_category": "budget_event", "signal_symbol": "$"},
      {"id": "sig-004", "signal": "SLCGP Year 3 subaward — $180K for identity management", "source": "CISA SLCGP announcement + state DOHS subrecipient list", "age_days": 45, "points": 8, "confidence": "HIGH", "evidence_urls": ["https://www.cisa.gov/cybergrants"], "signal_category": "grant_funding", "signal_symbol": "$"},
      {"id": "sig-005", "signal": "HHS OCR Resolution Agreement mandates privileged-access review by 2026-12-31", "source": "HHS Breach Portal entry + Resolution Agreement PDF", "age_days": 120, "points": 10, "confidence": "HIGH", "evidence_urls": ["https://ocrportal.hhs.gov/..."], "signal_category": "audit_finding", "signal_symbol": "⚡", "obstacle": "Examiner-driven prioritization queue + no dedicated headcount for access-review automation", "workaround": "IAM lead manually reconciles CSV exports against AD console before each quarterly review"}
    ],
    "negative": [],
    "net_assessment": "Moving toward purchase — compliance deadline creates urgency",
    "last_90_days_timeline": [
      {"date": "2026-02-15", "event": "HHS OCR Resolution Agreement entered (privileged-access review deadline 2026-12-31)", "source_url": "https://ocrportal.hhs.gov/...", "category": "audit_finding", "evidence_strength": "sourced"},
      {"date": "2026-03-12", "event": "Council Legistar agenda item 7 — FY27 budget amendment for endpoint security", "source_url": "https://city.legistar.com/...", "category": "budget_event", "evidence_strength": "sourced"},
      {"date": "2026-04-02", "event": "CISO job req posted on LinkedIn", "source_url": "https://www.linkedin.com/jobs/view/1234567890", "category": "hiring", "evidence_strength": "sourced"},
      {"date": "2026-04-15", "event": "SLCGP Year 3 subaward announced — $180K identity management", "source_url": "https://www.cisa.gov/cybergrants", "category": "grant_funding", "evidence_strength": "sourced"},
      {"date": "2026-05-10", "event": "Splunk renewal window opened — USAspending shows contract end 2026-09-30", "source_url": "https://www.usaspending.gov/award/CONT_AWD_12345", "category": "procurement_cycle", "evidence_strength": "sourced"}
    ],
    "evidence_index": {
      "sig-001": "sourced",
      "sig-002": "sourced",
      "sig-003": "sourced",
      "sig-004": "sourced",
      "sig-005": "sourced"
    }
  },
  "_signals_note": "ELISS v5.7+: each signal entry may include an optional `evidence_urls` array (list of URLs); renders as inline numbered link chips in the report. ELISS v6.0+: each signal entry may include a `signal_category` field (one of: 'hiring', 'compliance', 'procurement_cycle', 'breach_incident', 'technology_change', 'partnership', 'compliance_deadline', 'budget_event', 'audit_finding', 'grant_funding', 'executive_change', 'mergers_acquisitions', 'vendor_evaluation', 'conference_speaking', 'general'). The report generator color-codes the Buying Signals Timeline by category. Omitting the field is treated as 'general'. Procurement-cycle signals (procurement_cycle, budget_event, audit_finding, grant_funding, compliance_deadline, vendor_evaluation) are especially important — they indicate WHERE in the procurement cycle the prospect is, not just that they're interested. See search-playbook.md Layer 4b for the 16-category taxonomy and source queries for each. ELISS v7.5+ (Mom Test upgrade): each signal entry SHOULD include an `id` (stable, hyphen-prefixed slug), a `signal_symbol` ∈ {⚡ pain, ⚓ goal, ☐ obstacle, ⤴ workaround, ^ background, ☑ purchasing, $ money, ♀ key-person} per `references/mom-test-discipline.md`, and — for pain/obstacle signals — an `obstacle` + `workaround` pair (the makeshift current solution; the workaround IS the earlyvangelist test #4). `signals.last_90_days_timeline[]` is a chronological list of dated real events (hires, news, filings, M&A, RFPs, layoffs) populated by Subagent C; renders as the new Last-90-Days Timeline card on Tab 1 (reuses the existing freshness-weighted timeline component). `signals.evidence_index` is a sibling lookup mapping each signal `id` to its evidence strength (`sourced` | `inferred` | `assumed`); the renderer falls back to `sourced` for any signal not in the index. Empty `evidence_index` is acceptable; mixed-strength signals render with a confidence pill next to the existing tier pill.",
  "recommendations": {
    "action": "NURTURE",
    "next_steps": ["Step 1", "Step 2", "Step 3"],
    "ad360_talking_points": ["Point 1", "Point 2"],
    "log360_talking_points": ["Point 1", "Point 2"],
    "objections": [{"objection": "We already have Splunk", "response": "TCO comparison..."}],
    "outreach": {
      "channel": "Email",
      "timing": "Tuesday morning",
      "hook": "Reference their SOX audit deadline",
      "advisory_posture": "You are calling on a mid-core-consolidating regional bank as a ManageEngine identity-and-audit advisor, not pitching a tool. Your job in this call is to understand how the post-merger AD consolidation is shaping their next examiner cycle, then propose one tactical step they could take in the next 30 days that doesn't require buying anything yet.",
      "vision": "Walking into the next OCC exam cycle with the quarterly user-access-review automated end-to-end — the IAM lead's two-week CSV reconciliation collapses to a one-click attestation export, and the open MRA closes ahead of deadline.",
      "framing": "Industry advisor, not vendor. Most regional banks in mid-core consolidation hit the same wall — the examiner asks for evidence the bank's own GRC tooling wasn't built to produce. Worth 30 minutes to compare notes on how peer-banks under the same OCC examiner are closing this gap.",
      "weakness": "I don't yet know whether the IAM Architect's manual reconciliation has visibility from the Risk Committee, or whether the FY26 budget amendment carries headcount or only tooling. That shapes whether the answer is automation alone or automation + a managed-service partner.",
      "pedestal": "You sit at the exact intersection most CISOs delegate to — close enough to the operator pain to know what would actually work, senior enough to commit time. The CIO will hear the problem from you before the auditor names it again.",
      "ask": "30-minute working session with you and the IAM Architect Marcus Chen — currency is your time. Outcome: I walk you through the access-review automation pattern that two peer OCC-examined banks have used, you tell me what would break in your environment. No tooling pitch until you ask for one."
    }
  },
  "_outreach_note": "ELISS v7.5+ (Mom Test upgrade): `recommendations.outreach` gains five VFWPA beats (`vision`, `framing`, `weakness`, `pedestal`, `ask` — mnemonic 'Very Few Wizards Properly Ask', book Ch6 p83–85) plus `advisory_posture` (the Advisory Flip, Ch6 p87). The renderer prefers these when populated, falling back to the legacy `hook` when not. `ask` MUST specify a concrete advancement currency — time, reputation, or cash — per the book's Ch5 warning that compliments and stalls are not advancement. Existing `channel`/`timing`/`hook` keys retained for backward compatibility.",
  "executive_brief": "3-5 sentence summary",
  "data": {
    "industry_operational_lens": "For a mid-core-consolidating regional bank under OCC supervision, system availability means transaction continuity and audit-trail integrity — every minute a payments or examination-evidence system is degraded is measured in stalled wires and MRA exposure. Identity is the first place an examiner looks; the open MRA on user-access-review cadence is already shaping the next exam cycle, and the FY26 budget amendment for identity modernization is the institution's response to it. The IAM Architect is running quarterly access reviews on top of CSV exports and a parent-platform tooling mandate that constrains what they can change between exams.",
    "discovery_discipline": {
      "zoom_strategy": "zoom_now",
      "zoom_rationale": "Banking-OCC-examined is a vertical-playbook zoom-now segment — security/compliance is a known top-3 must-solve. Open with the specific problem (open MRA on access-review cadence) rather than confirming the category.",
      "good_questions": [
        {"question": "Talk me through the last access review cycle — where did Marcus spend the most time chasing approvers?", "template": "Talk me through the last time…", "anchor_fact_ref": "org_intelligence.representative_pain_owner — IAM Architect Marcus Chen runs the manual reconciliation"},
        {"question": "What are the implications when the open MRA misses its remediation date — who hears about it first, the Board's Risk Committee or the examiner?", "template": "What are the implications of that?", "anchor_fact_ref": "signals.positive[sig-005] — HHS OCR Resolution Agreement / OCC MRA"},
        {"question": "How are you dealing with the parent-platform tooling mandate today on the IAM side — what does your team get to choose, and what's already chosen for you?", "template": "How are you dealing with it now?", "anchor_fact_ref": "company.operating_model — parent-company tooling constraint"},
        {"question": "Where does the FY26 budget amendment money actually come from — Risk, IT, or Cyber's own line?", "template": "Where does the money come from?", "anchor_fact_ref": "signals.positive[sig-003] — FY27 budget amendment Council Legistar 2026-03-12"},
        {"question": "What else have you tried for access-review automation — the parent's GRC platform, a SOAR playbook, or something homegrown?", "template": "What else have you tried?", "anchor_fact_ref": "scoring.earlyvangelist.has_makeshift_solution — manual CSV reconciliation"}
      ],
      "bad_questions": [
        {"question": "Do you think automated access reviews would be a good idea?", "why_bad": "People lie to be nice. Opinions about hypothetical tools are uncalibrated — only behavior against the current workaround matters."},
        {"question": "Would you buy a SIEM that handled CJIS retention?", "why_bad": "Anything involving the future is an over-optimistic lie. Replace with 'how are you dealing with retention now' to anchor on present behavior."},
        {"question": "How much would you pay for an access-review automation tool?", "why_bad": "People will lie if they think it's what you want to hear. Price discovery comes from current spend on workarounds, not hypotheticals."},
        {"question": "Do you ever struggle with the quarterly access review?", "why_bad": "Fluff-inducer — 'do you ever' produces a generic average that doesn't describe any real instance. Use 'talk me through the last one' instead."}
      ],
      "anti_patterns": [
        "'I noticed your company...' — feature-rep boilerplate; banned in opening_hook and outreach.hook.",
        "'Are you currently struggling with...' — problem-shaming, produces defensive deflection.",
        "Treating a compliment ('that's interesting, send me more info') as a buying signal. A reply that isn't advancement in time, reputation, or cash is a stall, not a yes."
      ]
    },
    "rep_list_of_3": [
      {"question": "Has the OCR examiner named the specific evidence format for the December 2026 follow-up, or is it open to interpretation?", "why_it_matters": "Determines whether automation alone closes the MRA or whether the examiner wants a specific GRC artifact we'd need to integrate. Desk research can't reach this — only the operator knows.", "dmu_role": "representative_pain_owner"},
      {"question": "Does the parent-platform tooling mandate carve out room for a 'tactical' tool that supplements the GRC platform, or is the policy 'platform-of-record only'?", "why_it_matters": "Determines whether AD360+Log360 can land as a tactical complement or has to displace a parent decision. This is the deal-shape question.", "dmu_role": "economic_buyer"},
      {"question": "Of the FY26 budget amendment, what percentage is locked to identity modernization vs. negotiable into a broader compliance-tooling refresh?", "why_it_matters": "Tells us whether the deal sizing should be IAM-only or bundled with Log360 audit-trail. The number isn't in the public agenda.", "dmu_role": "economic_buyer"}
    ],
    "research_vs_ask": {
      "settled_by_research": [
        {"fact": "Open OCC MRA on user-access-review cadence (last exam cycle)", "source_url": "https://www.occ.gov/news-issuances/enforcement-actions/..."},
        {"fact": "FY26 budget amendment for identity modernization filed Q1", "source_url": "https://city.legistar.com/..."},
        {"fact": "IAM Architect Marcus Chen runs quarterly manual CSV reconciliation", "source_url": "https://www.linkedin.com/in/example-iam-architect/"},
        {"fact": "Splunk renewal window opens Q3 2026 (USAspending contract end)", "source_url": "https://www.usaspending.gov/award/CONT_AWD_12345"},
        {"fact": "Parent platform GRC tooling mandate present (inferred from public subsidiary status)", "source_url": null}
      ],
      "must_ask_live": [
        {"question": "OCR examiner's specific evidence-format expectation for Dec 2026 follow-up", "why_unsettleable": "Examiner correspondence is non-public; only the IAM Architect or General Counsel knows."},
        {"question": "Whether the parent's tooling mandate is policy-of-record or platform-of-record", "why_unsettleable": "Internal policy distinction; no public artifact."},
        {"question": "FY26 budget amendment line-item breakdown (IAM-only vs broader compliance refresh)", "why_unsettleable": "Public agenda shows total, not split."}
      ]
    },
    "deal_premortem": {
      "if_lost": "The parent platform's GRC vendor offers an access-review module bundled at marginal cost, and the IAM Architect's tactical preference loses to a parent-level platform decision before the examiner deadline forces a tactical buy.",
      "must_be_true_to_win": [
        "We reach the IAM Architect before the parent platform's annual vendor review cycle (next: Q3 2026)",
        "Marcus Chen sees the access-review automation pattern working at a peer OCC-examined bank, not just on a slide",
        "The FY26 budget amendment carves out a tactical line-item that isn't subject to parent-platform vendor approval",
        "The Risk Committee hears the operator's pain framing (not the vendor's product pitch) before the December examiner follow-up"
      ]
    }
  },
  "_data_note": "ELISS v7.5+ (Mom Test upgrade): the `data` block holds the new Mom-Test-discipline surfaces — `industry_operational_lens` (one-paragraph framing in customer language per `references/vertical-playbook.md`; required to use ≥2 phrases from the matched section's Customer Language list, lint-checked by `[depth-lint] industry_language_missing`); `discovery_discipline` (good vs bad question banks per `references/mom-test-discipline.md`, plus zoom_strategy and anti_patterns); `rep_list_of_3` (per book p54, the 3 murky-must-learn questions only the live conversation can settle); `research_vs_ask` (the dossier's spine per cheatsheet p116 — what desk research settled vs what only the call can answer); `deal_premortem` (per book p101, the if-lost reason + must-be-true-to-win conditions, layered over not replacing `pre_mortem[]`). All fields populated by the parent synthesis prompt (full skill) or the single synthesis prompt (`/eliss-light`).",
  "pre_mortem": [
    {
      "scenario": "Microsoft bundles Sentinel/Defender into existing E5 at marginal cost",
      "why_it_could_happen": "Customer is partial MS shop; E5 includes Defender XDR already",
      "evidence_urls": ["https://www.microsoft.com/en-us/security/business/microsoft-365-e5", "https://azure.microsoft.com/en-us/products/microsoft-sentinel/#pricing"],
      "mitigation": "Lead NOW with complement-not-displace positioning; focus on on-prem + CJIS audit log gaps Sentinel can't close affordably",
      "earliest_signal": "In discovery, customer references 'we already have Microsoft security tools'"
    },
    {
      "scenario": "New InfoSec Engineer arrives with CrowdStrike or Palo Alto loyalty",
      "why_it_could_happen": "Open req; hiring timeline overlaps with our eval window",
      "mitigation": "Reach hiring manager before the hire starts; get AD360/Log360 familiarity into JD",
      "earliest_signal": "Job posting closes; new name appears on LinkedIn as starting in the role"
    },
    {
      "scenario": "Procurement forces formal bid >$50K despite DIR contract availability",
      "why_it_could_happen": "City procurement policies may require bid regardless of cooperative contract",
      "mitigation": "Pre-verify DIR path with procurement team; size deal under formal-bid threshold if possible",
      "earliest_signal": "Gabriel defers budget questions to procurement in first call"
    }
  ],
  "_pre_mortem_note": "ELISS v5.6+: pre_mortem[] is REQUIRED. 3–5 specific, evidence-grounded loss scenarios with mitigations and earliest-signal watch points. Generic reasons ('we didn't follow up fast enough') are not acceptable — each scenario must tie to evidence elsewhere in the dossier. ELISS v5.7+: each scenario may include an optional `evidence_urls` array that renders as inline numbered link chips next to the why_it_could_happen text.",
  "rep_readiness_checklist": [
    "I have read the contact's career history and know their background shapes their receptivity",
    "I know NOT to lead with the breach as if the contact lived through it personally",
    "I have the CJIS audit-log checklist one-pager ready to attach",
    "I can explain why Log360 complements (not replaces) Microsoft Sentinel",
    "I know who Josh Littrell is and can reference the TAGITM/CGCIO community",
    "I have verified Texas DIR contract availability for AD360+Log360",
    "I can articulate the $40K deal in compliance/audit terms, not feature terms",
    "I have a specific ask for the first meeting (scoped 2-week POC)"
  ],
  "_rep_readiness_note": "ELISS v5.6+: rep_readiness_checklist[] is REQUIRED. 5–8 concrete, account-specific items the rep should confirm before first contact. Each item is a tactical fact — not generic sales hygiene.",
  "recommended_outreach": [
    {
      "slot": 1,
      "template_id": "compliance_gap",
      "template_name": "Compliance Gap",
      "voice": "consultative",
      "subject": "CJIS Section 5.4.1 — three considerations for Coppell",
      "body": "Hi Gabriel,\n\nThe HHS OCR Resolution Agreement Coppell entered last December includes a December 2026 deadline for privileged-access review. The CJIS audit-logging requirement (5.4.1) layers on top of that with an indefinite-retention obligation for any record touching CJI.\n\nMost municipalities I work with run into the same wall — Splunk handles the SIEM half well, but the indexed-retention cost past 90 days is what forces the conversation. Log360's flat-file retention with on-demand re-indexing is purpose-built for that gap; AD360 closes the privileged-access review side in the same console.\n\nI put together a one-page CJIS-to-Log360 control mapping for a similar-size Texas city last quarter — happy to send it over if that would be useful before we set up time.\n\nBest,\n<rep name>",
      "rationale": "Compliance gap is a hard-rule trigger here — Coppell has both a public OCR Resolution Agreement (Dec 2026 deadline) and CJIS retention pressure. Consultative voice fits Gabriel's IT Director role at a public-sector org; framework-led framing reads as peer-respectful, not salesy.",
      "triggered_by": ["HHS OCR Resolution Agreement Dec-2026", "CJIS 5.4.1 audit-log retention"]
    },
    {
      "slot": 2,
      "template_id": "competitor_displacement",
      "template_name": "Competitor Displacement",
      "voice": "technical",
      "subject": "Your Splunk-to-Sentinel posture — quick architectural note",
      "body": "Hi Gabriel,\n\nNoticed Coppell's running Splunk for the SIEM tier with what looks like a Sentinel/Defender XDR overlay on the M365 side (the public council Q4 IT update mentioned the E5 upgrade). That two-tool topology works, but the indexed-retention cost on Splunk past 90 days plus the KQL retention pricing on Sentinel is where most cities your size start consolidating.\n\nLog360's correlation engine can ingest both — keep Sentinel's M365-native detections, route on-prem AD + CJIS logs into Log360 for the retention tier, drop Splunk indexer count by ~40% in our Texas-city reference deployments. Happy to walk through the specific routing topology with our SE on a 25-min call.\n\nBest,\n<rep name>",
      "rationale": "Splunk + Sentinel hybrid stack is the strongest competitive trigger in the dossier. Technical voice fits Gabriel's hands-on technical role; the architectural framing (specific routing, indexer-count delta) demonstrates we read the environment, not just the company name.",
      "triggered_by": ["Splunk incumbent SIEM", "Sentinel M365 overlay", "council E5 upgrade Q4"]
    },
    {
      "slot": 3,
      "template_id": "breakup",
      "template_name": "Breakup / Final Touch",
      "voice": "executive",
      "subject": "Closing the loop",
      "body": "Hi Gabriel,\n\nNo reply is itself an answer — appreciate that.\n\nIf the OCR deadline shifts or the Splunk renewal lands earlier than expected, send one line and I'll re-open. The CJIS mapping doc is yours either way: <link>.\n\nBest,\n<rep name>",
      "rationale": "Breakup is mandatory in slot 3. Executive voice with a single async-value link (the CJIS mapping) leaves the door open without nagging. Generosity here is what converts the silence — passive-aggressive breakups never do.",
      "triggered_by": ["sequence close"]
    }
  ],
  "_recommended_outreach_note": "ELISS v7.2+ (voices renamed v7.4+): recommended_outreach[] is OPTIONAL but strongly recommended for HOT/WARM leads. Three dossier-driven follow-up emails. Slot 1 priority cascade (v7.4): event_followup > breach_incident > audit_deadline > renewal_window > compliance_gap > executive_briefing_offer > hybrid_cloud_migration > LLM-picked. Slot 2 is LLM-picked from soft library (competitor_displacement / peer_benchmark / technical_deep_dive / org_change / cost_consolidation / hybrid_cloud_migration). Slot 3 is ALWAYS the breakup (Executive voice). Voice values: 'technical' / 'executive' / 'consultative' (legacy 'google' / 'apple' / 'microsoft' resolved through renderer alias map for backward compatibility). template_id values: compliance_gap / renewal_window / breach_incident / competitor_displacement / peer_benchmark / technical_deep_dive / org_change / cost_consolidation / breakup / hybrid_cloud_migration / audit_deadline / executive_briefing_offer / event_followup. See references/outreach-playbook.md for the full 13-template library, voice guides, and authoring constraints. Each email body is fully Claude-authored per prospect — NOT mail-merge templating — and must reference at least one specific dossier fact.",
  "demo_playbook": {
    "persona": "IT Director at a CJIS-bound municipality reporting to a Council-elected official; technical enough to read a correlation rule, political enough to flinch at rip-and-replace.",
    "opening_hook": "The Coppell OCR Resolution Agreement has Council on the clock — the demo is about closing the privileged-access review gap and the indexed-retention cost wall before the auditor's December 2026 follow-up, not about feature parity with Splunk.",
    "ad360": {
      "value_moments": [
        {
          "title": "Self-service password reset with auditable trail",
          "why_it_matters": "Coppell's helpdesk runs ~40 password tickets/week per the council Q4 IT update, and the OCR Resolution Agreement requires every credential change be auditable end-to-end.",
          "tell_show_tell": "Tell: every reset writes a tamper-evident audit record routed to Log360. Show: the reset workflow + the auto-generated audit row appearing in Log360 in real time. Tell: one console for both — the auditor sees the chain of custody without cross-system joins."
        },
        {
          "title": "Quarterly privileged-access review the OCR Agreement demands",
          "why_it_matters": "The Dec 2026 deadline names privileged-access review as a control; today the IT team rebuilds the report manually from CSV exports.",
          "tell_show_tell": "Tell: a one-click privileged-access certification with manager attestation. Show: the certification workflow + the auditor-ready export. Tell: this is the exact artifact Council's outside counsel will ask for in December."
        },
        {
          "title": "Hybrid AD-to-Entra audit reporting for the M365 E5 upgrade",
          "why_it_matters": "The Q4 council update committed to M365 E5 — but Entra audit reporting at the city's tenant size leaves on-prem AD changes invisible to the auditor.",
          "tell_show_tell": "Tell: AD360 unifies on-prem AD audit events with Entra changes in one stream. Show: a hybrid identity-change timeline pulling both sides. Tell: this is what closes the gap that the E5 upgrade alone won't."
        }
      ],
      "discovery_questions": [
        "What's your current mean-time-to-resolve on a password ticket, and who signs the OCR-mandated quarterly privileged-access review today?",
        "Is the E5 upgrade in production yet, or still being staged — and who's responsible for the AD-to-Entra audit reconciliation?",
        "Has the OCR follow-up auditor named the specific evidence format they'll want in December?"
      ],
      "discovery_anchors": [
        {"anchor_fact": "Council Q4 IT update — ~40 password tickets/week + OCR mandate", "source_url": "https://city.legistar.com/..."},
        {"anchor_fact": "Council Q4 IT update committed to M365 E5", "source_url": "https://city.legistar.com/..."},
        {"anchor_fact": "HHS OCR Resolution Agreement — Dec 2026 follow-up", "source_url": "https://ocrportal.hhs.gov/..."}
      ],
      "top_objections": [
        {
          "objection": "We're standardized on Okta for SSO, why would we add AD360?",
          "response": "Okta handles cloud SSO well — AD360 sits beside it for on-prem AD lifecycle and audit, which is where the CJIS audit-log scope actually lands. They coexist in 80% of comparable Texas-city deployments."
        },
        {
          "objection": "Sounds expensive — Council won't approve another tool",
          "response": "AD360 + Log360 at the city's seat band on DIR-TSO-4099 lands inside the Splunk indexed-retention overage you're already paying. Happy to send the math against your Q3 Splunk invoice before the next budget cycle."
        }
      ],
      "cta": "Should we line up a 30-minute privileged-access workflow walkthrough with Josh before the next council session?"
    },
    "log360": {
      "value_moments": [
        {
          "title": "CJIS-grade flat-file retention at a fraction of indexed-tier cost",
          "why_it_matters": "Splunk's indexed retention past 90 days is the line item that forces this conversation; CJIS requires indefinite retention for records touching CJI.",
          "tell_show_tell": "Tell: Log360's flat-file retention with on-demand re-indexing keeps the cost flat regardless of CJI volume. Show: the retention tier configuration + a re-indexing query against 180-day-old data. Tell: this is how peer Texas cities cut Splunk indexer count ~40% without losing audit scope."
        },
        {
          "title": "UEBA for insider threat without standing up a separate tool",
          "why_it_matters": "The OCR Resolution Agreement names insider-threat detection as a control; today the city has SIEM correlation but no behavioral baseline.",
          "tell_show_tell": "Tell: UEBA is built into Log360 — no separate license, no separate deployment. Show: an insider-threat alert pulling from AD audit logs + file-access patterns. Tell: this is one of the three controls the auditor will mark closed without additional procurement."
        },
        {
          "title": "Pre-built CJIS + HIPAA compliance dashboards",
          "why_it_matters": "Coppell touches both CJIS (police) and HIPAA (city EMS records) — today the IT team rebuilds compliance evidence from raw Splunk queries every audit cycle.",
          "tell_show_tell": "Tell: pre-built dashboards for both CJIS 5.x and HIPAA Privacy/Security rules. Show: the CJIS 5.4.1 audit-log retention dashboard with current evidence + the HIPAA access-attestation dashboard. Tell: the auditor can pull this directly — the IT team doesn't write a single query."
        }
      ],
      "discovery_questions": [
        "What's your annual Splunk indexed-retention cost, and how much of that is CJIS-scoped data sitting past 90 days?",
        "Has the OCR auditor mentioned whether they want HIPAA controls evidenced alongside CJIS in December, or separately?",
        "Who runs the SOC analyst seat today — internal or MSSP — and what's their alert-fatigue posture?"
      ],
      "discovery_anchors": [
        {"anchor_fact": "USAspending Splunk contract end date 2026-09-30 (renewal window)", "source_url": "https://www.usaspending.gov/award/CONT_AWD_12345"},
        {"anchor_fact": "HHS OCR Resolution Agreement — Dec 2026 follow-up", "source_url": "https://ocrportal.hhs.gov/..."},
        {"anchor_fact": "Council Q4 IT update — SOC analyst staffing", "source_url": "https://city.legistar.com/..."}
      ],
      "top_objections": [
        {
          "objection": "We already have Splunk and Sentinel — adding a third SIEM is non-starter",
          "response": "Log360 isn't a third SIEM — it's the retention tier that lets Splunk's indexer count drop. Keep Sentinel for M365-native detections, keep Splunk for hot data, route the CJIS retention overflow to Log360. That's the consolidation math."
        },
        {
          "objection": "How do we know the UEBA is real and not just keyword alerting?",
          "response": "Fair — that's a demo-worthy show, not tell. Happy to bring our SE on for a 60-min architecture deep-dive where they run UEBA against a sanitized municipal log set and you can see the baseline-shift detection live."
        }
      ],
      "cta": "Can you forward the one-page CJIS-to-Log360 control mapping to your CISO before next council session, and we'll set up the 60-min architecture deep-dive with your SecEng lead by Friday?"
    }
  },
  "_demo_playbook_note": "ELISS v7.4+: demo_playbook{} is OPTIONAL but strongly recommended for HOT/WARM leads. Renders as a structured Tab 1 card (between Competitive Threat Matrix and Signal Detail) with per-product blocks for AD360 and Log360; the Tab 2 prose mirrors this in narrative form (see DEMO PLAYBOOK section spec earlier in this template). Each product block needs 3 value moments (NOT a feature tour), 3 discovery questions, 2 objection/response pairs, and a CTA. Every value moment MUST tie to a specific dossier fact — generic moments defeat the purpose. Source data for moments + objections: references/product-icp.md (AD360 features lines 21–43, Log360 features lines 47–72, displaced-competitor playbook lines 124–142, objection bank lines 145–154). The demo playbook is the rep's pre-call mental model; the Tab 1 card is the structured artifact for copy-paste into Salesforce. ELISS v7.5+ (Mom Test upgrade): each product block SHOULD include a `discovery_anchors[]` sibling array — indexed identically to `discovery_questions[]`, each entry `{anchor_fact, source_url}` — so `anchors[i]` explains *why* `questions[i]` is the right question (cites the dossier fact it's anchored on). The renderer reads anchors as an optional decoration; old leads without anchors still render fine. Lint `[depth-lint] discovery_question_unanchored` fires on HOT when a question lacks an anchor or fails the anchor-fact substring check.",
  "full_dossier_markdown": "# ELISS Intelligence Dossier\n\n**Lead:** ... | **Company:** ... | **Email:** ...\n\n---\n\n## SCORE SUMMARY\n\n| Dimension | Score | Max | Confidence | Key Driver |\n|---|---|---|---|---|\n| Fit | X | 25 | ... | ... |\n\n(... ENTIRE conversational dossier verbatim — every section from SCORE SUMMARY through DATA QUALITY. Use markdown tables, headings, bold, lists exactly as presented in conversation.)",
  "sources": {
    "person": [{"url": "https://linkedin.com/in/example", "tier": "B"}],
    "company": [{"url": "https://example.com/about", "tier": "A"}],
    "technology": [{"url": "https://zoominfo.com/...", "tier": "C"}],
    "financial": [{"url": "https://sec.gov/...", "tier": "A"}],
    "compliance": [{"url": "https://reuters.com/...", "tier": "B"}]
  },
  "_sources_note": "ELISS v5.6+: each source entry is {url, tier} where tier is 'A' (authoritative — gov, SEC, company press), 'B' (reputable secondary — Reuters, WSJ, The Record, primary LinkedIn), or 'C' (aggregator/inferred — ZoomInfo, RocketReach, LeadIQ). Claims resting entirely on Tier-C sources cap at MEDIUM confidence. Legacy flat-URL-array form is accepted for backward compat but discouraged.",
  "data_quality": {
    "overall_confidence": "MEDIUM",
    "assumptions": ["Revenue estimated from headcount"],
    "gaps": ["No confirmed tech stack data"],
    "improve": ["Confirm AD environment via discovery call"],
    "sources_actually_checked": [
      {"source": "crt.sh", "access_method": "web_fetch", "layer": 2, "yielded_signal": true},
      {"source": "MXToolbox", "access_method": "web_fetch", "layer": 2, "yielded_signal": true},
      {"source": "PingCastle Azure Tenant Resolution", "access_method": "web_fetch", "layer": 2, "yielded_signal": true},
      {"source": "DNSDumpster", "access_method": "web_fetch", "layer": 2, "yielded_signal": false},
      {"source": "LinkedIn company page", "access_method": "web_search", "layer": 1, "yielded_signal": true},
      {"source": "Glassdoor", "access_method": "web_search", "layer": 1, "yielded_signal": true},
      {"source": "Hudson Rock infostealer check", "access_method": "web_fetch", "layer": 3, "yielded_signal": false},
      {"source": "Ransomware.live", "access_method": "web_search", "layer": 3, "yielded_signal": true},
      {"source": "Texas AG Catastrophe Notice", "access_method": "web_fetch", "layer": 3, "yielded_signal": true},
      {"source": "USAspending.gov", "access_method": "web_search", "layer": 4, "yielded_signal": false},
      {"source": "SAM.gov", "access_method": "web_search", "layer": 4, "yielded_signal": false},
      {"source": "Coppell Legistar", "access_method": "web_fetch", "layer": 4, "yielded_signal": true},
      {"source": "grants.gov CISA SLCGP", "access_method": "web_search", "layer": 4, "yielded_signal": true},
      {"source": "RocketReach API — Colon-Atencio lookup", "access_method": "rocketreach_api", "layer": 5, "yielded_signal": true},
      {"source": "RocketReach API — company lookup coppelltx.gov", "access_method": "rocketreach_api", "layer": 5, "yielded_signal": true}
    ]
  },
  "_data_quality_note": "ELISS v6.1+: sources_actually_checked[] is REQUIRED. Each entry records which source was hit during research, how it was accessed (web_search | web_fetch | rocketreach_api | preflight | inferred), which layer it served, and whether it yielded a usable signal. This makes the gap between 'catalog of 300 sources' and 'sources actually queried on this lead' explicit rather than hidden. The report generator renders this as a Research Coverage panel in Tab 1. ELISS v7.0+: access_method='preflight' entries come from the offline preflight.py harvester (merged from preflight.sources_actually_checked_entries[]) and count toward the HOT-floor of 20 sources without consuming Claude's tool budget."
}
```

Save this file as `eliss_dossier_[CompanySlug]_[YYYY-MM-DD].json` in the workspace.

---

## Tab 2 Markdown Style Examples (ELISS v7.2+)

The `full_dossier_markdown` field is the entire Tab 2 narrative. It must be authored to match the **Coppell gold standard** (file: `D:\MY VIBE CODING PROJECTS\ELISS - Project\Dossiers\ELISS_City_of_Coppell_Colon-Atencio_2026-04-30.html`). Below are three worked examples showing the exact markdown patterns the renderer in `scripts/generate_report.py` transforms into rich Tab 2 visual elements.

### Example 1 — SCORE SUMMARY (open with thesis blockquote, 5-column table, recommendation paragraph)

```markdown
## SCORE SUMMARY

> [Lead] is in the [time-bound window] where [structural fact] — and [the budget/political/regulatory event that creates the opening] has not yet been [spent / closed / cemented]. Whoever lands [credible artifact] in front of [contact name] between now and [date] has a structurally higher win probability than competitors arriving after [event].

| Dimension | Score | Max | Confidence | Key Driver |
|---|---|---|---|---|
| Fit | 21 | 25 | HIGH | 289-emp TX muni [A] · Microsoft hybrid AD/Entra confirmed [A] · Asst Director technical-evaluator role [A] |
| Intent | 25 | 25 | HIGH | Oct 2024 RansomHub breach [A] · 8 active compliance frameworks [A] · 2x ISE hiring postings [B] |
| Timing | 24 | 30 | HIGH | Imminent need — FY26-27 budget-build window OPEN (Apr-Jul 2026) [A] · post-breach T+18mo · TMLIRP cyber-renewal underwriter pressure |
| Budget | 14 | 20 | MEDIUM | $900K est. security budget [ESTIMATED] · DIR-CPO-4875/5241 cooperative path [A] · IT line item not publicly disclosed |

**Final Score:** 84/100 · **Tier:** HOT · **Confidence:** HIGH
**Risk-Adjusted Composite:** 84 − 16 = **68**/100 — Raw HOT, adjusted high-WARM.
**Recommended Action:** PURSUE NOW — multi-thread Gabriel → Josh → Mike Land within 30 days, anchor to the FY26-27 budget-build window.

**Why this scores HOT:** [3-4 sentence summary tying together the structural facts]
```

**What renders:**
- `> ...` line → indigo left-bordered blockquote (`md-blockquote`)
- 5-column table with sticky header + zebra striping (`md-table`)
- `[A]` / `[B]` / `[C]` after each claim → green / amber / grey tier badges (`md-tier-{a,b,c}`)
- `[ESTIMATED]` / `[CONFIRMED]` / `[INFERRED]` → blue / green / grey status pills (`md-pill-*`)

### Example 2 — EXECUTIVE BRIEF + COMPETITIVE SECTION (callout blocks)

```markdown
## EXECUTIVE BRIEF

> The deal isn't won by displacing SailPoint. It's won by being the day-2 AD operational layer SailPoint doesn't deliver, with a credible NYDFS §500.06 audit-trail story.

[Lead] presents a HOT-tier opportunity (91/100 raw, 74 risk-adjusted) anchored by three converging structural facts: (1) the CISO seat has been vacant since approximately April 2025 [A] when [predecessor] departed for [company] — see https://example.com/source — (2) [contact] was hired into [role] in [date] from [prior employer] [B] making them a fresh program owner, and (3) the regulatory pipeline ([deadline 1] https://gov-source.example, [deadline 2] https://regulator.example) creates demonstrable demand for the [product fit] story.

**Why this is HOT now:** The window for being the "incumbent recommendation" the new CISO inherits closes the day a successor is announced. Past F500 FinServ CISO transitions show 30–60 day decision-freeze immediately after arrival, then a $100K–$500K first-90-days assessment-tooling spend [B].

**Mitigation for the multi-incumbent lock-in:** `SailPoint IdentityIQ` (active hiring per req JR2503062 — see https://aig.wd1.myworkdayjobs.com/...JR2503062), `CyberArk PAM`, `Okta`, and `Splunk Enterprise Security` are all entrenched. Position AD360 as the AD/Entra operational layer beneath SailPoint and Log360 as the compliance-reporting + UEBA layer beneath Splunk. Coexist, never displace.

**Key insight:** [contact]'s 15-month tenure is the constraint, not the opening. Frame everything around 90-day operational wins he can socialize upward without risking face.

**Trigger to watch:** [Q2 2026 earnings call mention of SIEM consolidation OR post-Cisco-acquisition Splunk renewal reassessment]. Either pulls the renewal forward and shifts Timing from Imminent (24) to Active procurement (30), score 91 → 96.

**Risk:** if `Microsoft Sentinel` is confirmed as the cloud-workload primary SIEM during discovery, Log360 must reposition as compliance-reporting layer ONLY. Score impact: −6.
```

**What renders:**
- `**Why:** …` → purple-accent callout box labeled "Why" (`md-callout-why`)
- `**Mitigation:** …` → green-accent callout (`md-callout-mitigation`)
- `**Key insight:** …` → cyan-accent callout (`md-callout-note`)
- `**Trigger to watch:** …` → amber-accent callout (`md-callout-trigger`)
- `**Risk:** …` → red-accent callout (`md-callout-watch`)
- All `https://...` URLs auto-link to clickable `↗` chips (`md-link`)
- `` `SailPoint IdentityIQ` `` etc. → monospace pills (`md-code`)

**Callout label aliases recognized by the parser** (`generate_report.py:CALLOUT_KIND` at `:3466`):

| Label (case-insensitive) | Renders as | Color |
|---|---|---|
| `Why`, `Why it shifts`, `Why it could happen` | `md-callout-why` | purple |
| `Mitigation`, `Resolution` | `md-callout-mitigation` | green |
| `Action`, `Next step`, `Next steps` | `md-callout-action` | blue |
| `Trigger`, `Trigger to watch`, `Earliest signal` | `md-callout-trigger` | amber |
| `Watch for`, `Risk` | `md-callout-watch` | red |
| `Note`, `Key insight`, `Insight` | `md-callout-note` | cyan |

### Example 3 — BUYING SIGNALS (per-claim URLs + tier markers + RR glyph)

```markdown
## BUYING SIGNALS TIMELINE

### Positive signals (10)

- **Executive change** (Sep 1 2025, freshness 0.95): Chief Digital Officer [name] appointed — fresh CDO triggers identity-fabric and data-access-governance reviews [A]. https://lifeinsurance.example/article
- **Compliance deadline** (Jan 17 2025, freshness 0.90): DORA in force across EU; [company] subsidiaries directly subject [A]. https://eiopa.europa.eu/dora
- **Hiring** (Sep 2025, freshness 0.75): SailPoint Engineer (req JR2503062) + PAM Analyst + 263+ security listings on LinkedIn [B]. https://linkedin.com/jobs/aig-security-jobs

### Negative signals (2)

- **Budget event** (May 2024, freshness 0.80): [Company] Next expense-reduction program targets $500M annual run-rate savings [A]. https://carriermanagement.example/article
- **Vendor evaluation** (continuous, freshness 0.90): Multi-year sunk-cost in `SailPoint IIQ` + `CyberArk PAM` + `Okta CIAM` + `Splunk ES` — replacement path closed for 24–36 months [A].
```

**RocketReach provenance pattern** — append the `ᴿᴿ` Unicode glyph (U+1D3F U+1D3F, two superscript-R characters) directly after any RR-sourced value:

```markdown
- **Name:** Marco Lisboaᴿᴿ
- **Title:** VP, Identity & Access Managementᴿᴿ
- **LinkedIn:** https://www.linkedin.com/in/marcolisboaᴿᴿ
- **Employees:** 27,739 [CONFIRMED]ᴿᴿ
- **HQ:** 1271 Avenue of the Americas Fl 37, New York, NY 10020 ᴿᴿ
```

The renderer's regex at `generate_report.py:3332` rewrites the glyph into the orange `.rr-pill` span with the standard "Sourced from RocketReach premium account" tooltip.

### Density floor checklist (HOT-tier dossiers)

After authoring `full_dossier_markdown`, run a self-check:

```bash
python -c "
import re
md = open('full_dossier_markdown.md', encoding='utf-8').read()
print('md-link bare URLs:    ', len(re.findall(r'https?://[^\\s)\\]\\[]+', md)))   # target >= 20
print('[A]/[B]/[C] markers:  ', len(re.findall(r'\\s\\[[ABC]\\]', md)))             # target >= 40
print('[CONFIRMED]/etc pills:', len(re.findall(r'\\[(CONFIRMED|ESTIMATED|INFERRED)\\]', md)))  # target >= 6
print('callout blocks:       ', len(re.findall(r'\\*\\*(Why|Mitigation|Action|Trigger|Watch for|Risk|Note|Key insight)[^:]*:\\*\\*', md)))  # target >= 6
print('blockquote opens:     ', len(re.findall(r'(?m)^>\\s', md)))                  # target >= 1
"
```

If any count falls below the floor, rewrite the relevant section before stamping the dossier complete.
