# 02 — Reading the Dossier

The dossier is dense by design — it's compressing 30-100 web searches and several enrichment API calls into a single document. Here's how to read it efficiently.

## Two tabs

Every dossier has two tabs:

- **Tab 1 — Executive Summary.** The 60-second skim. Score, verdict, key signals, demo playbook, recommended outreach. Use this to decide *whether* to engage.
- **Tab 2 — Complete Intelligence Dossier.** The full narrative report. Use this to *prepare* for the engagement.

If you're triaging a list of 20 leads, stay on Tab 1. If you're about to call a specific lead, read Tab 2.

> _Screenshot placeholder: `./screenshots/dossier-tabs.png`_

## Tab 1 — Executive Summary widgets

The page is built from ~12 cards. Here's what each one means.

### Verdict banner (top)

One sentence summarizing why this lead matters. Example: "City IT shop with a recent breach, fresh CISO hire, and a Log360-ready compliance posture — Sentinel SIEM is likely incumbent."

### Score gauge

Big circular gauge showing the composite score (0-100) and tier (HOT / WARM / COOL / COLD).

**Tier thresholds:**
- HOT: 75-100 — engage now.
- WARM: 50-74 — engage with a hook.
- COOL: 30-49 — nurture, don't push.
- COLD: 0-29 — deprioritize.

### 4-dimension radar

Spider chart with Fit, Intent, Timing, Budget. Areas closer to the edge are stronger.

| Dimension | Max | What strong looks like |
| --- | --- | --- |
| **Fit** | 25 | Right industry, size, and seniority of contact |
| **Intent** | 25 | Visible buying signals — RFPs, audit findings, breach response, security hires |
| **Timing** | 30 | Active procurement window, contract renewal soon, post-incident remediation |
| **Budget** | 20 | Spend signals consistent with our deal size + a budget owner identified |

The radar tells you *why* the tier is what it is. A HOT lead with low Budget is one to engage **with budget-friendly framing**, not just any pitch.

### Dimension bars

Same data as the radar, but in horizontal bars with the actual numeric score (e.g., `Fit 22/25`). Look for: low confidence on a dimension (means the score is uncertain, not necessarily low).

### Score-attribution segments

A stacked bar showing which sub-factors contributed to each dimension. Useful when you want to know "*why* did Fit score 22?" — drill in here.

### Intent-signal donut

Distribution of intent points across categories: compliance, security incident, AD pain, security hiring, tech investment, content engagement, direct inquiry.

### Compliance pressure heatmap

A grid of regulatory frameworks (HIPAA, PCI, SOX, GDPR, CJIS, FedRAMP, etc.) with HIGH / MEDIUM / LOW pressure per framework and a one-liner explaining AD360 / Log360 fit. Use this to anchor your compliance pitch.

### Buying-signal timeline

Dots on a horizontal axis — each dot is a signal, plotted by age (recent on the right). Hover to see details. Tight cluster of recent signals = strong intent right now.

### Budget waterfall

Stacked bars showing estimated IT spend → security budget → IAM-IGA sub-budget → SIEM sub-budget → expected deal size. If your deal lands in "Comfortable" affordability (<30% of sub-budget), you're well-positioned.

### DMU (Decision-Making Unit) org-chart

Names and roles of: economic buyer, champion, technical evaluator, blocker, plus future stakeholders (open reqs) and ghost stakeholders (suspected but unconfirmed).

### Demo playbook

Persona-anchored opening hook + 3 value moments per product (AD360 + Log360) + discovery questions + top objections with responses + CTA. **Read this before any demo or deep-dive call.**

### Recommended outreach (3 emails)

Three dossier-driven follow-up emails:

- **Slot 1** — fires from hard-rule triggers (breach <90 days, renewal <120 days, compliance gap). Send first.
- **Slot 2** — softer angle (competitor displacement, peer benchmark, technical deep-dive).
- **Slot 3** — always the Breakup / Final Touch. Highest-converting touch in the sequence.

Each email has a **Copy** button. Use the email verbatim or as a starting point.

> _Screenshot placeholder: `./screenshots/recommended-outreach.png`_

## Tab 2 — Complete Intelligence Dossier

The full narrative report, rendered in 17 sections:

1. **Score Summary** — table with key drivers per dimension.
2. **Executive Brief** — 3-5 sentence write-up.
3. **Person Profile** — career path, tenure, public presence, personalization hooks.
4. **Company Profile** — industry, employees, revenue, HQ, growth stage, recent news.
5. **Technology & Security Posture** — AD environment, security stack, cloud, competitive threat matrix, competitive readiness score.
6. **Organizational Intelligence** — DMU detail, additional stakeholders, multi-thread strategy, ghost stakeholders.
7. **IT Budget** — sub-budgets, affordability, deal authority, deal cycle, expected deal size.
8. **Compliance Mapping** — per-framework AD360 / Log360 fit.
9. **Buying Signals** — positive + negative signals with age, category, points, evidence.
10. **Deal Execution Risks** — softer friction (champion new to role, multi-dept sign-off, etc.) with mitigations.
11. **Scoring Rationale** — why this lead scores what it does.
12. **Strategic Recommendations** — next steps, AD360 talking points, Log360 talking points, common objections.
13. **Pre-Mortem** — 3-5 specific ways this deal could fail.
14. **Rep Readiness Checklist** — 5-8 tactical facts the rep must know.
15. **Demo Playbook** — same as Tab 1, but in narrative form.
16. **Recommended Outreach** — same 3 emails with rationale.
17. **Research Sources** — every URL, grouped by tier (A / B / C source quality).

## Reading the source-tier badges

Throughout Tab 2 you'll see badges next to claims:

| Badge | Meaning |
| --- | --- |
| **[A]** (green) | Tier-A source — authoritative (SEC filings, official .gov pages, the vendor's own newsroom). |
| **[B]** (amber) | Tier-B source — reputable secondary (TechCrunch, RocketReach, industry analyst reports). |
| **[C]** (grey) | Tier-C source — third-party / inferential. |

When you cite a dossier finding back to a customer, prefer Tier-A claims. A HIGH-confidence claim should have at least one Tier-A source.

## Reading the **ᴿᴿ** pill

Orange chips with the **ᴿᴿ** glyph mean "this datum came from RocketReach." Reliable contact info, verified emails, and confirmed firmographics carry this pill. A dossier with several **ᴿᴿ** pills is a confidence boost; one with none means the OSINT was good enough to render but RocketReach didn't have data (the "OSINT-only" banner explains this case explicitly).

## What the "Partial" badge means

Sometimes the system marks a dossier **Partial** instead of **Complete**:

- The depth-lint quality gate found some thin sections that couldn't be improved within budget.
- RocketReach had no firmographics for this org (`.gov`, `.edu`, smaller nonprofit).
- For heavy dossiers: one or more of the four research subagents failed.

A Partial dossier is still useful — just treat the empty sections as "we don't know" rather than "the answer is nothing." The header banner says exactly which gap caused the partial label.

## Copy patterns

| To copy | How |
| --- | --- |
| One recommended email | Click the **Copy** button on that email card |
| The whole dossier as a link | Use the browser's "Copy URL" — the URL is permanent until the lead is deleted |
| A specific URL from Tab 2 | Right-click → Copy link |

## Up next

→ [Managing the lead list](./03-managing-leads.md) — filters, search, and the regenerate flow.
