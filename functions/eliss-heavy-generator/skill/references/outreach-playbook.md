# ELISS Outreach Playbook v7.4 — Recommended Follow-Up Email Sequence

This playbook governs the **`recommended_outreach[]`** field on every dossier
JSON. The renderer turns it into the "Recommended Outreach — Follow-Up Email
Sequence" section at the bottom of Tab 1 (Executive Summary).

The goal of these emails is **a reply, not a click**. Enterprise security
buyers (CISOs, IAM Architects, Security Engineering leads, IT Directors at
mid-market and public-sector orgs) get 50+ vendor emails a week. The rep
sends the dossier-driven sequence below because each email *demonstrates that
ELISS read the prospect's environment first*. That's the entire pitch — if
the email could have been sent to anyone, it isn't worth sending.

---

## How a sequence is built

For every dossier you produce three emails as `recommended_outreach[]`,
ordered by `slot` (1, 2, 3). The rep sends them roughly 4–7 days apart over
two to three weeks.

### Slot 1 — Hard rules fire first (in priority order)

Evaluate triggers against the dossier in this order. The first match wins
slot 1; remaining triggers, if any, move to slot 2.

| Priority | Trigger condition (dossier evidence) | Template | Voice |
|---|---|---|---|
| 1 | Event / webinar / whitepaper engagement within last 30 days — warm hand-raise, the prospect is already in-funnel | **Event Follow-Up** | Technical (Consultative if Director+) |
| 2 | Recent breach, ransomware claim, OCR/HHS resolution, or audit finding within last 90 days (cite `signals.positive[].signal_category` in `breach_incident` or `audit_finding`) | **Breach / Incident Response** | Executive |
| 3 | Specific dated audit within next 60–180 days (HHS OCR follow-up, PCI re-attestation, NYDFS Section 500.06 annual, CJIS triennial, FISMA OIG, SOX year-end) — clock-driven, distinct from #5 | **Audit Deadline** | Consultative |
| 4 | Competitor renewal window <120 days (cite `technology.renewal_intelligence[]` or USAspending contract end date) | **Renewal Window** | Consultative |
| 5 | Compliance gap detected, HIGH pressure, no specific dated audit (HIPAA, PCI-DSS, SOX, GDPR, SOC2, CJIS, FedRAMP) — cite `compliance[]` rows where `pressure: HIGH` | **Compliance Gap** | Consultative |
| 6 | C-level recipient (CISO/CIO/CTO/COO), no prior touch, sector-level board concern surfaced in dossier, and no #1–#5 trigger fired | **Executive Briefing Offer** | Executive |
| 7 | Active Azure/M365 migration evidence with on-prem AD (`technology.cloud_posture: "Hybrid"` + tenant/migration signals) — slot 1 only if #1–#6 didn't fire; otherwise slot 2 | **Hybrid Cloud Migration** | Technical |

If none of the seven fire, slot 1 is LLM-picked from the soft library below
using the strongest dossier signal.

### Slot 2 — LLM-picked from soft angles

Pick the next-strongest angle from the soft library, avoiding duplication of
slot 1. Match voice to recipient and signal:

| Template | When to pick | Voice |
|---|---|---|
| **Competitor Displacement** | Current SIEM/IAM stack identified (Splunk, QRadar, Sentinel, Okta, SailPoint, CyberArk, etc.) | Technical |
| **Peer Benchmark** | Peer companies in same vertical/size band already use AD360/Log360 — cite peer org names if known | Executive |
| **Technical Deep-Dive** | Recipient is CTO / Security Architect / SecEng lead with technical content history (blog posts, GitHub, conference talks) | Technical |
| **M&A / Org Change** | Recent merger, CISO turnover, restructuring, layoffs, or new exec hire in the security org | Consultative |
| **Cost Consolidation** | Budget freeze, layoffs, cost-cutting press, or `signals.negative[]` mentioning budget pressure | Executive |
| **Hybrid Cloud Migration** | Slot 2 default when active Azure/M365 migration + on-prem AD evidence is in the dossier | Technical |

### Slot 3 — Always Breakup

Slot 3 is **always** the **Breakup / Final Touch** template. Executive voice.
Polite close, leaves the door open, gives the prospect a frictionless way to
re-engage later. Do not skip — the breakup converts more replies than the
opening cold email.

### Hard-rule overflow

If two slot-1 triggers fire (e.g., a breach AND a renewal window AND a
compliance gap), the higher-priority one takes slot 1 and the next-highest
moves to slot 2 (displacing the LLM pick). Slot 3 stays Breakup.

---

## Voice guides

Each email picks ONE voice. The voice tag renders as a colored badge on the
card. Do not mix voices within a single email — pick one and stay disciplined.

### Technical voice — `voice: "technical"`

- **Vibe:** technical depth up front, data-forward, "let's whiteboard this"
- **Subject lines:** specific, technical, often a question. *"Your Splunk-to-Sentinel migration — what's the AD360 angle?"* / *"Quick note on your DC topology + Log360 correlation rules"*
- **Opener:** lead with a specific technical observation from the dossier — a stack item, an architecture choice, a public engineering blog post. No pleasantries.
- **Body:** 4–6 sentences. Reference architecture, integration points, specific product capabilities (UEBA, SOAR runbooks, AD audit log forwarding). One concrete number or comparison.
- **CTA:** offer a working session, not a "demo." *"Happy to walk through how we'd structure the failover for a tenant your size — 25 minutes Thursday?"*
- **Tone signature:** confident, specific, slightly nerdy. No marketing verbs ("empower", "unlock", "transform"). The rep sounds like a Solutions Engineer, not a BDR.

### Executive voice — `voice: "executive"`

- **Vibe:** minimal, executive, outcome-first, almost no jargon
- **Subject lines:** under 6 words. *"One thought on the audit"* / *"After last week's breach"* / *"Worth a 15-minute call"*
- **Opener:** one sentence stating the outcome the prospect cares about. Nothing about the rep, the rep's company, or the product.
- **Body:** 3–5 sentences total. No bullet lists. No links unless absolutely necessary. State the value, name the specific signal, ask for time.
- **CTA:** short and time-boxed. *"15 minutes next week?"*
- **Tone signature:** quiet confidence. Reads like a note from a peer, not a vendor. White space is the message.

### Consultative voice — `voice: "consultative"`

- **Vibe:** consultative, framework-driven, governance-led
- **Subject lines:** name the framework or compliance axis. *"CJIS audit-log retention — three options for Coppell"* / *"NIST 800-53 AU-6 mapping for Log360"*
- **Opener:** acknowledge the prospect's specific compliance/governance pressure (HIPAA OCR finding, PCI 4.0 deadline, NYDFS Part 500, SLCGP grant requirements). Reference the public artifact (resolution agreement, council agenda, audit report).
- **Body:** 6–9 sentences. Use a "here's how we think about X" framing. Cite Gartner / Forrester / NIST / regulator-issued guidance. Connect a specific control family to a specific product capability. End with a non-pushy hand-off to a Solutions Architect.
- **CTA:** offer a structured next step — a compliance mapping doc, a 30-min governance review, an SE intro. *"Would a one-page CJIS mapping be useful before we set up time?"*
- **Tone signature:** respectful, longer-form, unhurried. Treats the prospect as a peer evaluator. The rep sounds like a consultative AE working with a regulated buyer.

### Voice → recipient affinity (use as a tiebreaker)

- C-level recipients (CISO, CIO, CTO, COO) → Executive voice reads best
- Director / VP recipients in regulated verticals → Consultative voice
- Hands-on Architect / SecEng / IAM Engineer → Technical voice
- Public sector (city, county, state, federal) → Consultative voice (governance-led) almost always wins

---

## Template library (13 templates, pick 3)

Each section below is the recipe Claude follows when authoring that template
fresh per prospect. **Do not paste these as canned text** — Claude must
write each email end-to-end using the dossier's specific facts.

### #1 — Compliance Gap (Consultative voice)

- **Triggered by:** HIPAA / PCI-DSS / SOX / GDPR / SOC2 / CJIS / FedRAMP / NYDFS / SLCGP / state breach-notification framework cited in `compliance[]` with `pressure: HIGH`.
- **Subject pattern:** *"\<framework name\> \<control family\> — three considerations for \<company\>"*
- **Body anchors (must include):**
  1. Name the specific framework + the specific control or finding (e.g., "CJIS Section 5.4.1 — audit logging").
  2. Cite the public artifact you found (HHS Resolution Agreement URL, PCI QSA report, council agenda item, regulator press release).
  3. Map ONE Log360 or AD360 capability to that control with a sentence of detail.
  4. Acknowledge the incumbent if known ("if you're already on Splunk for the SIEM half of this…") — never dismiss.
- **CTA:** offer a one-page mapping doc OR a 30-min review with a security architect.

### #2 — Renewal Window (Consultative voice)

- **Triggered by:** competitor renewal <120 days. Sources: USAspending.gov contract end dates, ZoomInfo intent renewal signals, public RFP postings, RocketReach budget signals.
- **Subject pattern:** *"\<incumbent\> renewal — quick note on the consolidation math"*
- **Body anchors:** the specific renewal date with source citation; the consolidation angle (one platform replacing two or three line items); a concrete cost framing tied to `budget_analysis.iam_iga_budget` or `siem_budget`; a respectful nod to the incumbent ("Splunk is excellent at \<X\>; the gap we typically close is \<Y\>").
- **CTA:** offer a TCO sketch or a 25-min architecture review.

### #3 — Breach / Incident Response (Executive voice)

- **Triggered by:** breach within 90 days, ransomware claim site listing, HHS OCR resolution, public incident disclosure, security advisory published. Verify carefully — never reference an incident the company hasn't publicly acknowledged.
- **Subject pattern:** *"After last \<week/month\>"* or *"On \<framework\> response"*
- **Body anchors:** acknowledge the public disclosure with a citation; do NOT speculate, do NOT lead with product, do NOT use any language that could read as exploitative; offer a single specific next step (often: a peer-org playbook, a UEBA detection-rule pack, a forensic log-retention reference).
- **CTA:** "15 minutes next week" — nothing more.
- **Hard rule:** if the contact themselves was publicly named in the incident, soften further. The rep should never sound like they smell blood.

### #4 — Competitor Displacement (Technical voice)

- **Triggered by:** identified incumbent in `technology.competitive_threat_matrix[]` (Splunk, QRadar, Sentinel, Okta, SailPoint, CyberArk, BeyondTrust, etc.).
- **Subject pattern:** *"Your \<incumbent\> footprint — \<specific technical angle\>"*
- **Body anchors:** name the incumbent, name a specific architectural limitation (not a marketing dig — an actual technical observation, e.g., "Sentinel's KQL retention pricing past 90 days"), name the migration path with a real integration detail, name the on-prem / hybrid / sovereignty angle if applicable.
- **CTA:** working session with an SE to walk through a parallel-run.

### #5 — Peer Benchmark (Executive voice)

- **Triggered by:** peer companies in same vertical / size band identified as ManageEngine customers (`leads_log.json` peer signal, public case studies, prior-engagement intelligence).
- **Subject pattern:** *"\<peer org\> went the same direction"*
- **Body anchors:** name the peer; one-sentence outcome the peer achieved; one-sentence acknowledgement of why this prospect is similar; one-sentence offer.
- **Hard rule:** never name a peer without verified public consent or a published case study URL. If unsure, anonymize ("a peer city government in a comparable population band").

### #6 — Technical Deep-Dive (Technical voice)

- **Triggered by:** recipient persona is technical (CTO, Principal Architect, Security Engineering Manager, IAM Engineer). Bonus signal: published engineering content (blog, GitHub, conference talk) referenced in `lead.personalization_hooks[]`.
- **Subject pattern:** *"\<specific technical capability\> — implementation note for \<company\>"*
- **Body anchors:** reference a specific public artifact the recipient produced; tie it to a specific AD360/Log360 capability (correlation rules, UEBA model behavior, AD audit log forwarding, SOAR runbook chaining); offer a real architecture document, not a generic deck.
- **CTA:** working session with the SE; offer to share an architecture deep-dive doc.

### #7 — M&A / Org Change (Consultative voice)

- **Triggered by:** recent merger announcement, divestiture, CISO/CIO turnover, restructuring, exec hire, or layoffs in the security org.
- **Subject pattern:** *"Identity governance during \<transition type\>"*
- **Body anchors:** acknowledge the transition with a citation (press release, LinkedIn announcement, news article); name the specific identity / audit risk that transition creates (orphaned accounts, privilege drift, audit-trail gaps during integration); offer a 90-day stabilization framework.
- **CTA:** governance review with an SE; offer the M&A identity-cleanup checklist.

### #8 — Cost Consolidation (Executive voice)

- **Triggered by:** budget freeze, layoffs, cost-cutting press, downgraded earnings guidance, or `signals.negative[]` mentioning budget pressure.
- **Subject pattern:** *"One platform, three line items"*
- **Body anchors:** acknowledge the cost pressure once (no condolences, no marketing); state the consolidation outcome ("AD360 + Log360 typically replaces \<incumbent IAM\> + \<incumbent SIEM\> + \<incumbent PAM\> for \<company size\> orgs"); reference the deal sizing math from `budget_analysis.estimated_deal_size`.
- **CTA:** 15-minute call to size the consolidation.

### #9 — Breakup / Final Touch (Executive voice) — ALWAYS slot 3

- **Triggered by:** always — slot 3 is reserved.
- **Subject pattern:** *"Closing the loop"* or *"My last note"*
- **Body anchors:** three sentences max. Acknowledge no reply is itself an answer. Leave a single clean re-entry point ("if \<specific trigger\> changes, send me one line and I'll re-open"). Provide one piece of asynchronous value (a link to a relevant playbook, a one-page guide, a peer-conversation note) — but only if it's genuinely useful.
- **CTA:** none. The breakup is the CTA.
- **Hard rule:** the breakup is never passive-aggressive ("guess this isn't a priority…"). It's the most generous email in the sequence. That generosity is what makes it the highest-converting touch.

### #10 — Hybrid Cloud Migration (Technical voice) — v7.4

- **Triggered by:** `technology.cloud_posture: "Hybrid"` plus active migration evidence — job postings mentioning "AD-to-Entra migration", "tenant cutover", "hybrid identity"; press releases on M365 E5 rollout; tenant-resolution preflight that resolved a Microsoft 365 tenant alongside on-prem AD signals.
- **Subject pattern:** *"Hybrid identity — the on-prem AD half of your \<M365/Azure\> rollout"* / *"Tenant cutover: where AD audit reporting usually breaks"*
- **Body anchors (must include):**
  1. Cite the specific migration evidence (job posting URL, press release, vendor announcement).
  2. Name the orphaned-AD-trust risk during cutover (auditor cares about this; CISO cares about this).
  3. Map AD360's hybrid sync + Entra audit reporting to the migration's blast radius.
  4. Provide one concrete tenant-size comparable ("a regional bank running ~6k seats on the same hybrid pattern…") with no fabricated specifics.
- **CTA:** working session on cutover audit posture; offer a 30-min architecture walk-through with an SE.
- **Voice note:** technical voice fits because the buyer at this stage is an IAM engineer or Solutions Architect, not the CISO.

### #11 — Audit Deadline (Consultative voice) — v7.4

- **Triggered by:** a specific dated audit window opening within 60–180 days. Examples: HHS OCR follow-up site visit; PCI 4.0 re-attestation deadline; NYDFS Section 500.06 annual certification; CJIS triennial audit; FISMA OIG cycle; SOX year-end. **Distinct from `compliance_gap`**: `compliance_gap` is *pressure-framed* (the framework applies, posture is weak); `audit_deadline` is *clock-driven* (there's a date on the calendar). When both fire, **`audit_deadline` outranks `compliance_gap`** for slot 1; `compliance_gap` moves to slot 2.
- **Subject pattern:** *"\<Framework\> \<month/quarter\> audit — three pre-work items"* / *"\<Audit name\> by \<date\> — control-mapping pre-read"*
- **Body anchors (must include):**
  1. Cite the exact audit date and the public source (regulator notice, RFP, board minutes, prior audit report).
  2. Name 2–3 control families the auditor will scrutinize, by control number (e.g., "AU-6, AU-12, AC-2(3)").
  3. Offer a pre-audit one-page mapping doc connecting Log360 / AD360 capabilities to those exact controls.
  4. Acknowledge the typical finding pattern auditors hit at this prospect's size band — peer-respectful framing, not vendor-pitch framing.
- **CTA:** offer a 30-min pre-audit posture review with an SE.
- **Hard rule:** the one-page mapping must actually exist or ship within 24 hours of the email. Do not offer artifacts that don't exist.

### #12 — Executive Briefing Offer (Executive voice) — v7.4

- **Triggered by:** C-level cold outreach (CISO/CIO/CTO/COO/CFO sponsoring security spend), no prior touch, where the dossier surfaces a *board-level* concern — cyber-insurance renewal pressure, a recent peer breach in the same vertical, a sector-wide regulatory enforcement action, a public-market disclosure of cyber risk in 10-K filings. Slot 1 candidate when recipient is C-suite AND no #1–#5 trigger outranks it.
- **Subject pattern:** *"One-page briefing for \<company\>"* / *"\<Sector\> identity-risk briefing — peer comparison"*
- **Body anchors (must include):**
  1. The value-give **IS** a one-page briefing — the rep delivers it free, no meeting required.
  2. 3–5 sentences total. No bullet lists. No links unless the briefing itself is linked.
  3. Name the specific sector pattern the briefing addresses (e.g., "healthcare PHI access-review findings in 2025–26 OCR resolution agreements", "regional-bank-of-record GLBA Safeguards Rule custody-of-keys finding pattern").
  4. Frame the briefing as an artifact the recipient can forward internally without taking a calendar slot.
- **CTA:** *"Reply with 'send' and I'll route it over — no calendar needed."*
- **Hard rule:** the briefing must actually exist or be authored within 24 hours. Never offer artifacts that don't ship. Document the briefing source in `rationale`.

### #13 — Event Follow-Up (Technical voice by default; Consultative if Director+) — v7.4

- **Triggered by:** prospect engaged with a recent event within the last 30 days — webinar attendance, conference talk attendance, trade-show booth visit, gated whitepaper download, demo-replay view, podcast listener-survey response, ManageEngine User Conference registration. **Slot 1 candidate — outranks everything else** because this is *reactivation* (warm hand-raise), not initiation.
- **Subject pattern:** *"After \<event name\> — quick follow-up"* / *"\<Topic\> from \<event\> — wanted to send the deck"*
- **Body anchors (must include):**
  1. Name the specific event + date.
  2. Reference one concrete thing the recipient asked, viewed, or downloaded (engagement metadata).
  3. Offer the actual asset — slide deck, recording, demo replay — do not bait-and-switch.
  4. Explicit acknowledgement they may have just been browsing (lowers pressure, raises reply rate).
- **CTA:** offer the asset first. Only ask for time if the recipient is Director+ AND there's an active intent signal beyond the registration itself.
- **Voice rule:** Technical voice when recipient is Architect/SecEng/IAM Engineer; Consultative voice when Director+/regulated-vertical. Executive voice **never** — this email is asset-delivery, not executive narrative.

---

## What the JSON must contain

Each entry in `recommended_outreach[]` is an object with these fields:

| field | type | required | description |
|---|---|---|---|
| `slot` | int (1, 2, or 3) | ✅ | sequence position |
| `template_id` | string | ✅ | one of `compliance_gap`, `renewal_window`, `breach_incident`, `competitor_displacement`, `peer_benchmark`, `technical_deep_dive`, `org_change`, `cost_consolidation`, `breakup`, `hybrid_cloud_migration`, `audit_deadline`, `executive_briefing_offer`, `event_followup` |
| `template_name` | string | ✅ | human-readable name (e.g., "Compliance Gap") |
| `voice` | string | ✅ | one of `technical`, `executive`, `consultative` (legacy `google`/`apple`/`microsoft` accepted for backward compatibility — renderer resolves through `_LEGACY_VOICE_ALIASES`) |
| `subject` | string | ✅ | the email subject line |
| `body` | string | ✅ | the full email body (plain text, line breaks preserved with `\n`) |
| `rationale` | string | ✅ | 1–2 sentences: WHY this template + voice + angle for THIS prospect, citing specific dossier facts |
| `triggered_by` | array of strings | ✅ | short labels for the dossier signals that fired this template (e.g., `["HIPAA OCR resolution", "Splunk renewal Q3"]`). Renders as orange chips on the card. |

### Example minimal entry

```json
{
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
    { "slot": 2, "template_id": "competitor_displacement", "...": "..." },
    { "slot": 3, "template_id": "breakup", "...": "..." }
  ]
}
```

---

## Authoring rules — DO and DON'T

**DO:**

- Reference at least one specific fact from the dossier in every email body (a stack item, a hire, a public artifact, a compliance trigger).
- Match voice to recipient seniority and persona using the affinity table.
- End every CTA with a specific time window (e.g., "Thursday afternoon") or a specific deliverable ("a one-page mapping").
- Keep Executive voice under 100 words. Consultative voice can run 150–200. Technical voice 120–180.
- Cite the public source for any breach, audit, or financial trigger in the rationale (not in the email body — but the rep needs to verify before sending).

**DON'T:**

- Don't paste the same opener across emails. Each email is a fresh draft.
- Don't use marketing verbs ("empower", "unlock", "leverage", "transform", "reimagine"). They tank reply rates with security buyers.
- Don't reference a breach in any way that could read as opportunistic. Breach emails are about *response support*, not pitch.
- Don't fabricate specifics. If the dossier doesn't have a renewal date, don't invent one. Use language like "if your \<incumbent\> renewal is on the horizon…" instead.
- Don't include more than two links per email. Two is already a lot for an Executive-voice note (often zero).
- Don't sign off with a long signature block. The rep adds their own signature when sending.
