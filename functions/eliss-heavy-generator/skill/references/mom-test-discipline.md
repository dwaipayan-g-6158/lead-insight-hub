# Mom Test Discipline — Contract for every narrative-producing prompt

> **Status.** BINDING contract. Cited by `SKILL.md` parent synthesis + Subagents A/B/C/D. Render-time verification gate (`scripts/generate_report.py`) enforces violations as `[depth-lint]` warnings. HOT leads regenerate on violation; WARM render with soft warnings; COOL render with info notes.
>
> **Source.** Rob Fitzpatrick, *The Mom Test* (entire book — Intro, Ch1–8, Cheatsheet). Page citations below refer to the PDF at `C:\Users\dGiri\Downloads\The-Mom-Test-by-@robfitz.pdf`. The dossier exists to operationalize the book's rules at the artifact level — by the time the rep reads it, the discipline is already baked into every question, every signal, every outreach beat.

---

## The 3 Rules (p13) — applied to dossier composition

| Rule | Applied to dossier |
|---|---|
| **Talk about *their life*, not your idea.** | Every `discovery_question`, every `opening_hook`, every `outreach.framing` references the prospect's operational reality (per `vertical-playbook.md` § matched industry) — *not* AD360/Log360 features. Feature mentions belong only in `recommendations.tactical_actions[]` and the technical deep-dive section, not in the question bank. |
| **Ask about specifics in the past, not generics or opinions about the future.** | All good-questions use past-tense anchors: *"Talk me through the last…"*, *"How are you dealing with it now?"*. Future/hypothetical phrasings (*"Would you ever…"*, *"How would you handle…"*) are banned and lint-blocked. |
| **Talk less and listen more.** | Dossier is the desk research; the rep's live time is reserved for the `must_ask_live[]` short-list. The `rep_list_of_3` keeps the live conversation focused — no more than 3 murky-must-learn questions per persona on the meeting agenda. |

---

## Good question bank (p14–21, p101) — verbatim templates

Every entry in `data.discovery_discipline.good_questions[]` must be a prospect-specific instance of one of these templates, anchored to a dossier fact via `demo_playbook.{ad360,log360}.discovery_anchors[i]`:

- **"Why do you bother?"** — surfaces motivation, the job-to-be-done behind the surface request (the MTV story, p34: "we don't want analytics, we want to feel like rockstars").
- **"What are the implications of that?"** — converts a pain into a quantifiable cost or downstream effect. Determines whether the pain is on-fire or merely background-tax.
- **"Talk me through the last time that happened."** — replaces the generic "do you have this problem?" with the specific instance. If they can't recall one, the problem isn't real.
- **"Talk me through your workflow."** — exposes the *obstacle* and the *workaround* (p105) in their actual sequence.
- **"What else have you tried?"** — surfaces the makeshift solution (earlyvangelist test #4, p72) and the alternatives they've already rejected.
- **"How are you dealing with it now?"** — price-anchors the problem: if they're already paying X in time/money to work around it, that's the willingness-to-pay ceiling.
- **"Where does the money come from?"** — the B2B DMU must-ask (p21). Identifies the economic buyer distinct from the representative pain-owner (p97).
- **"What would have to be true for this to be a huge success?"** — the deal pre-mortem (p101). Used in `data.deal_premortem.must_be_true_to_win[]`.
- **"If this deal were to fail, why?"** — the inverse pre-mortem (p101). Used in `data.deal_premortem.if_lost`.
- **"Who else should I be talking to?"** — used at the end of the meeting, not the dossier, but flagged in `recommendations.tactical_actions[]` for next-step planning.

---

## Bad question bank (p14–21) — never generate, always flag

Entries in `data.discovery_discipline.bad_questions[]` cite a specific bad-question phrasing from this list and explain *why* it's bad. The renderer shows them in red as a "do not ask" column to the rep.

- **"Do you think it's a good idea?"** → "people lie to be nice." Opinions are useless; only behavior matters.
- **"Would you buy a product that did X?"** → "anything involving the future is an over-optimistic lie." People imagine the future too rosily.
- **"How much would you pay for X?"** → "people will lie if they think it's what you want to hear." Price discovery comes from observing current spend on workarounds, not hypotheticals.
- **"Do you ever [X]?"** / **"Would you ever [X]?"** / **"What do you usually [X]?"** → fluff-inducers (p15). The answer is always a generic average that doesn't describe any real instance.
- **"Are you currently struggling with [X]?"** → problem-shaming; produces defensive deflection.
- **"Do you need better visibility into [X]?"** → vendor-language, signals the rep is about to pitch, kills candor.
- **"How important is [security/compliance/uptime] to your business?"** → forces a positive answer that means nothing.

---

## Banned phrasings (lint-blocked)

The render gate (`scripts/generate_report.py`) scans `demo_playbook.{ad360,log360}.opening_hook`, `recommendations.outreach.hook` / `vision` / `framing` / `ask`, and every `discovery_questions[i]` for these substrings. A match fires `[depth-lint] opening_hook_generic` on HOT (regenerate) / SOFT on WARM / INFO on COOL.

- `"I noticed your company..."` — feature-rep boilerplate, screams cold outreach.
- `"Are you currently struggling with..."` — see bad question bank.
- `"Do you need better visibility into..."` — vendor-language.
- `"Would you ever consider..."` — future-hypothetical fluff.
- `"How important is security to your..."` — forced-positive question.
- `"I wanted to reach out because..."` — opening boilerplate with no anchor.
- `"Hope this email finds you well"` — pure boilerplate, no anchor.
- `"Just checking in"` — anti-pattern signal (p67), no advancement.
- `"I think you might benefit from..."` — vendor-language.

A compliment received in a meeting does NOT count as a buying signal (Ch5 warning). Outreach must always seek **advancement** in a currency of time, reputation, or cash — never a compliment.

---

## Customer-language rule

When `company.industry` (or close proxy in `company.tags`, SIC, NAICS) matches a `vertical-playbook.md` section, the following fields MUST use ≥2 phrases from that section's **Customer language** list:

- `data.industry_operational_lens` (the field anchoring Tab 1)
- `demo_playbook.{ad360,log360}.opening_hook`
- `recommendations.outreach.vision` and `framing` (the VFWPA beats)

Violation fires `[depth-lint] industry_language_missing`. The lint scans the customer-language list using case-insensitive substring match.

---

## Signal symbol taxonomy (p105, p118)

Every entry in `signals.positive[]` and `signals.negative[]` gets a `signal_symbol` per the book's note-taking shorthand. The renderer prepends the symbol visually to each signal.

| Symbol | Type | Meaning |
|---|---|---|
| `⚡` | Pain | A pain point or active problem ("things suck because…") |
| `⚓` | Goal | A job-to-be-done or desired outcome ("we want to…") |
| `☐` | Obstacle | What's blocking them from solving it (policy, contract, budget, legacy) |
| `⤴` | Workaround | The makeshift current solution (= earlyvangelist criterion #4) |
| `^` | Background | Operational context (org structure, ops cadence, regulator) |
| `☑` | Purchasing | A purchasing-criterion or evaluation question they've stated |
| `$` | Money | Money/budget/spend signal |
| `♀` | Key person | A named decision-maker / influencer / blocker |
| `!` | Emotion-strong | Excitement, frustration, or embarrassment overlay (use with another symbol) |

Categorize using a single primary symbol; emotion overlays are optional. The render-gate validates `signal_symbol ∈ {⚡, ⚓, ☐, ⤴, ^, ☑, $, ♀}`.

---

## Obstacle + Workaround on every problem (p105)

Every evidence-backed problem (whether on `signals.positive[]` or a dedicated `evidence_backed_problems[]`) MUST carry an `obstacle` (what's blocking resolution) and `workaround` (what they're cobbling together today). This is a non-negotiable book rule — the workaround IS the earlyvangelist signal #4. Examples from the book and from the playbook:

- *Banking — privileged access*: obstacle = "examiner-driven prioritization queue"; workaround = "scheduled SQL scripts the IAM lead reconciles before each quarterly access review."
- *Oil & Gas — OT visibility*: obstacle = "turnaround calendar, no patch window for 6 months"; workaround = "engineering laptop with dual NIC that occasionally bridges IT/OT."
- *Healthcare — EHR access*: obstacle = "clinical workflow primacy"; workaround = "shared department Epic logins on workstations on wheels."

If the dossier can't infer an obstacle or workaround from the harvest, the field reads `"insufficient evidence — must_ask_live"` and the question is added to `data.research_vs_ask.must_ask_live[]`.

---

## Earlyvangelist test (p72) — 4-pip scorecard

Every dossier gets a `scoring.earlyvangelist` object scoring four booleans, each with evidence + source:

1. **has_problem** — the prospect demonstrably has the problem (incident, breach, audit finding, regulator notice, public statement).
2. **knows_problem** — they have acknowledged the problem (job posting language, conference talk, board minutes, CISO public quote).
3. **has_budget** — money exists or is being assembled (recent capex, grant award, RFP posted, hiring of a buyer role).
4. **has_makeshift_solution** — they've already built a workaround (= obstacle/workaround pair above) and live with its pain.

A 4-pip is the strongest enterprise buyer signal in the book. 3-pip is HOT-worthy. 2-pip is WARM. 0–1 is COOL or earlyvangelist-uninteresting (lead is real but the buying moment is not).

---

## Customer slicing → micro-segment (Ch7, p89–96)

The book's central diagnostic, p93: *"If you aren't finding consistent problems and goals, you don't yet have a specific enough customer segment."* The dossier MUST pin `company.micro_segment` to a who-where slice from `vertical-playbook.md`, not the bare vertical name.

Bad: `"banking"`, `"healthcare"`, `"manufacturing"`.
Good: `"regional bank, 50–200 branches, mid core-consolidation, OCC-examined"`, `"academic medical center with a research arm, R1 flagship, NIH grant + HIPAA + IRB"`.

The micro-segment is the prospect-specific slice the rep speaks to — anchoring every other narrative field.

---

## Research-vs-Ask split (p116, cheatsheet) — the dossier's spine

The cheatsheet rule: *"If a question could be answered via desk research, do that first."* The dossier IS the desk research. It answers everything answerable up front so the rep's scarce live time is spent on what only the conversation can reach.

- `data.research_vs_ask.settled_by_research[]` — every fact the dossier already established, with source URL. The rep does NOT burn a live question on these.
- `data.research_vs_ask.must_ask_live[]` — the murky-must-learn shortlist. Becomes the seed for `data.rep_list_of_3` per role.

This is the organizing spine of the whole upgrade. Without a populated `research_vs_ask`, the dossier degrades into a vendor brochure.

---

## List of 3 (p54) — per persona

`data.rep_list_of_3` is the 3 murkiest must-learn questions for this specific prospect, scoped optionally per DMU role. Each item: `{question, why_it_matters, dmu_role}`. The renderer surfaces this on Tab 1 as a compact pre-meeting card.

Rule of thumb: if more than 3 questions feel essential, the dossier hasn't done enough research. Cut the list to 3 by moving the answerable ones to `settled_by_research[]`.

---

## Look-before-you-zoom (p48)

Per-prospect `data.discovery_discipline.zoom_strategy` is one of:

- **`zoom_now`** — the prospect's industry has security/compliance/identity as a known top-3 must-solve (banking audit, healthcare HIPAA, defense CMMC, public-sector ATO). Open with the specific problem already stated. The vertical playbook tags these as zoom-now-safe.
- **`confirm_category_first`** — security may not be the top-3 must-solve; open broadly to let the prospect tell you what their priority actually is. Used for verticals where IT is a cost center, not a regulator-driven function.

Default to `confirm_category_first` if ambiguous. The render gate doesn't enforce this — it's a soft posture flag the rep reads on Tab 1.

---

## Commitment & Advancement (Ch5)

Every `recommendations.outreach.ask` must specify a concrete advancement currency:

- **Time** — a calendar-booked meeting with a named operator, a working-session with the team, a shadow-shift, attendance at a postmortem.
- **Reputation** — an introduction to a peer/partner/board member, an LOI, a quote, a reference.
- **Cash** — a paid pilot, a PoC contract, signed SOW.

A reply that is *only* a compliment, *only* a "let me think about it," or *only* a "send me more info" is **not advancement** — it's a stall (the book's warning). The render gate flags outreach `ask`s that don't specify one of the three currencies.

---

## VFWPA outreach beats (Ch6, p83–85)

`recommendations.outreach` adds five new fields, the book's "Very Few Wizards Properly Ask" mnemonic:

- **`vision`** — what the world looks like once the operational problem is solved (in customer language, anchored on the micro-segment).
- **`framing`** — the rep's position in that vision (industry advisor, not vendor). This is the Advisory Flip (p87, Ch6) — see `advisory_posture` below.
- **`weakness`** — what the rep does *not* know yet about the prospect; what they're hoping to learn from the conversation.
- **`pedestal`** — why the prospect specifically is being asked (their operational depth, their unique view of the problem from a representative pain-owner seat).
- **`ask`** — the concrete advancement (per the previous section).

The renderer prefers VFWPA when populated; falls back to legacy `outreach.hook` when not. Existing `channel`/`timing`/`hook` keys stay for backward compatibility.

---

## Advisory Flip (Ch6, p87)

`recommendations.outreach.advisory_posture` is a one-line statement of the rep's posture: *industry advisor*, *not vendor*. The renderer surfaces this as a header on the outreach card to remind the rep of the stance before the meeting. The advisory flip puts the rep in control of the conversation by trading "I'm selling" for "I'm here to learn how your world actually works."

Example: *"You are a ManageEngine PAM/SIEM advisor calling on a regional bank, not pitching a tool. Your job in this call is to understand how their post-merger AD consolidation is shaping their next examiner cycle, then propose one tactical step they could take in the next 30 days that doesn't require buying anything yet."*

---

## Representative pain-owner (Ch7, p97)

`org_intelligence.representative_pain_owner` is the operator who actually lives the pain — distinct from `economic_buyer`. For an IAM problem at a regional bank: the economic buyer is the CIO/CISO; the representative pain-owner is the IAM Architect or the Identity Engineering lead who's actually running the quarterly access-review meat-grinder.

Talking to the pain-owner first is faster, more candid, and produces specifics. The economic buyer enters once the pain-owner co-signs the problem.

Shape: same as other DMU node entries — `{name, title, evidence, source_url}`.

---

## Density caution (Ch4, Ch8)

The book's "this stuff is fast" / "notes are useless if not reviewed" message: dossiers that are too dense get ignored. Tab 1 is ~18 blocks before this upgrade plus the new Mom Test surfaces — keep prose tight per card.

**All Mom Test cards on Tab 1 render always-open.** Earlier drafts collapsed Earlyvangelist / Pre-mortem / Discovery Discipline by default to manage density, but that risked a viewer missing the contents entirely. Per the user's decision (v7.5.5): every section is visible without an expand action. A one-line summary header sits above each card body so the reader can scan from row to row without losing the scent.

The dossier MUST stay scannable in 30 minutes. Tight prose per slot is the lever; collapsing cards is not.
