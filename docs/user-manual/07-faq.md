# 07 — Frequently Asked Questions

Quick answers to the things people ask. For longer treatments, jump to the linked detail pages.

## About scoring

### What's the scoring model?

Four dimensions: Fit (out of 25), Intent (25), Timing (30), Budget (20). They sum to a composite 0-100. Tier follows from the composite: HOT 75-100, WARM 50-74, COOL 30-49, COLD 0-29.

The dimensions are **independent** — a lead can be strong in Fit and weak in Timing, or any combination. Full detail in [Reading the dossier](./02-reading-the-dossier.md).

### What's the difference between composite and risk-adjusted composite?

Composite is the raw sum of the four dimensions. Risk-adjusted is composite minus any "Deal Execution Risks" — softer friction items like "champion new to role" (-3), "multi-dept sign-off" (-3), "shrinking budget" (-3).

The **tier** is determined by the **raw composite**. The risk-adjusted number is informational — it tells you the dossier flagged some friction worth being aware of, but doesn't change the tier label.

### What's the "Confidence" rating mean?

Each dimension has a confidence level: HIGH / MEDIUM / LOW. It reflects how strong the underlying evidence was. The overall dossier confidence is the **lowest** of the four — one weak dimension drags it down.

Low confidence isn't bad — it's honest. Treat a HOT-tier dossier with LOW confidence as "the signals look right but verify before betting big."

### What does the orange **ᴿᴿ** pill mean?

The data point came from RocketReach. It's a marker of "high-quality structured source" rather than something the AI inferred.

### What if there are no **ᴿᴿ** pills at all?

RocketReach didn't have data for this organization. Common for `.gov`, `.edu`, and smaller nonprofits. The dossier renders with an "OSINT-only" banner explaining this — it's still useful, just leaner on contact info.

## About the dossier itself

### Why two tabs?

Tab 1 is the 60-second skim. Tab 2 is the in-depth read. The split lets you triage 20 leads quickly on Tab 1, then go deep on Tab 2 for the one you'll call today.

### What's the difference between HOT, WARM, COOL, and COLD?

- **HOT (75-100)** — engage immediately. Strong signal across multiple dimensions.
- **WARM (50-74)** — engage with the right hook. Good fundamentals but missing something (often Timing).
- **COOL (30-49)** — nurture, don't push. Some fit, no urgency.
- **COLD (0-29)** — deprioritize. Wrong fit or no signal.

### What are the `[A]`, `[B]`, `[C]` badges in the dossier?

Source quality tiers:
- **[A]** — authoritative (SEC filings, official .gov pages, vendor newsroom).
- **[B]** — reputable secondary (TechCrunch, RocketReach, industry analysts).
- **[C]** — third-party / inferential.

When citing back to a customer, prefer **[A]** sources.

### What's "Demo Playbook"?

A persona-anchored briefing for your next sales call: opening hook, three value moments per product, discovery questions, top objections + responses, and a CTA. Read it before any demo.

### Can I edit the dossier?

No, not at v1.0.0. The dossier is the AI's output; if you disagree, regenerate or annotate in your CRM. A future release may allow inline notes.

## About generation

### Why does it take so long?

Light dossiers do ~10-20 web searches plus ~12 RocketReach calls plus one big AI synthesis call. That's the floor for 3-5 minutes. Heavy dossiers run 4 parallel research threads with deeper search budgets — 8-13 minutes.

There's no "faster but lighter" option. The quality is what it is.

### Can I cancel a dossier mid-generation?

Yes, but it's not always reliable. Best practice: let it finish (the wall time is bounded by the 15-minute Job timeout). If you submitted with bad intake, just create a new dossier with the right values.

### Why does regenerating create a new lead instead of updating?

So that old shared links don't break. If you sent a teammate a URL to the old dossier and you regenerate, their URL still shows what you sent them — not a different document under the same URL.

Both versions appear in your **Leads** list. Delete the old one if you don't want it visible.

### What's "heavy mode" and how do I enable it?

A deeper-research mode that runs 4 parallel AI threads. ~3× the wall time and cost, ~2× the research depth. Enable via the **5-tap secret** on the intake modal title.

Use it for HOT-suspected leads, big-money targets, or complex compliance situations. See [Creating a dossier — heavy mode](./01-creating-a-dossier.md#the-heavy-mode-power-tool).

### What's the "Partial" status?

The dossier finished but with some quality gaps — usually because RocketReach had no firmographics for the org, or one of the heavy-mode research threads ran short. Still useful; just leaner. The Partial banner explains the specific reason.

## About lead management

### Can I share a dossier with a teammate?

Yes — copy the URL from your browser. It's permanent (until the lead is deleted) and signed URLs inside the iframe refresh automatically when the page reloads.

The teammate needs an account on this app to see the dossier (the URL only works for authenticated users). If they can authenticate, the system enforces that they can only see leads associated with their own account.

So: if you want to share a finding without giving them the lead, **export the dossier** (browser print, save HTML) and send that. If you want them to track it in their own dashboard, ask them to regenerate from the same intake — they'll get their own version.

### Can two people see the same lead?

No. Lead access is **per-user** — each user sees only their own dossiers. Even admins see only their own in the **Leads** list (admins have separate user-management views).

### Can I delete my own lead?

No — deletion is admin-only at v1.0.0. Ask an admin.

### How long are leads kept?

Indefinitely. No automatic expiration at v1.0.0. If storage cost becomes a concern, the team will add an archival policy in a future release.

## About signing in

### Why do I have to confirm my email?

Catalyst enforces it — for security and to confirm you control the email address. Without confirmation, you can't sign in.

### Forgot password?

Use the **Forgot password** link on the login form. Catalyst sends a reset email.

### My session expired

Sign in again. Sessions last several hours; they expire on inactivity. Catalyst, not this app, owns session timing.

## About data and privacy

### What data do we keep?

For each lead:
- The intake you provided.
- The full HTML dossier.
- All extracted structured fields (score, signals, recommendations).
- Activity timestamps.

For each user:
- Email and password (managed by Catalyst, hashed).
- App role.
- Last seen timestamp.

### Is my data shared?

The application doesn't share data outside Catalyst. The integrations (Anthropic, RocketReach) receive the data necessary to do their part — Anthropic sees prompts including the prospect identifiers, RocketReach sees the lookup parameters.

Anthropic and RocketReach have their own data-handling policies; if your prospect requires data-residency guarantees, run that question past the team lead before submitting.

### Can I export my data?

Each dossier's URL gives you the rendered HTML, which you can save. Structured per-lead data export (CSV of scores, etc.) is not built in at v1.0.0.

## More questions?

If your question isn't here, check the relevant topic page or message your team's admin.

## Up next

→ [Limitations and assumptions](./08-limitations-and-assumptions.md)
