# 06 — Troubleshooting

The things that go wrong most often, and what to do about them.

## "My dossier is stuck at stage X"

Each generation goes through 6-8 stages: `queued → preflight → rocketreach → [fanout →] synthesis → rendering → lint → upload → done`.

### What each stage means

| Stage | What's happening | Typical duration |
| --- | --- | --- |
| **queued** | Waiting for a worker slot | <30 s usually |
| **preflight** | Free OSINT checks (DNS, government records, breach catalogs) | 10-30 s |
| **rocketreach** | Premium contact and firmographic enrichment | 30-60 s |
| **fanout** | (Heavy only) Four parallel research threads | 5-10 min |
| **synthesis** | AI assembling the dossier | 1-3 min light, 1-2 min heavy parent |
| **rendering** | Producing the HTML | 5-15 s |
| **lint** | Quality check | <5 s |
| **upload** | Saving to storage | 1-3 s |

### When to consider "stuck"

- **>2 minutes in queued** — possibly a Job Pool capacity issue. Wait 5 more minutes; if still queued, contact an admin.
- **>5 minutes in preflight or rocketreach** — the vendor API may be slow. Often unsticks itself.
- **>10 minutes in synthesis (light)** — Anthropic may be experiencing rate limits or overloaded. Often retries automatically; if it ends with "failed," create a new request.
- **>15 minutes total** — the function hit Catalyst's 15-minute Job timeout. The dossier is marked failed; create a new request.

### How to recover

1. **Don't cancel mid-flight.** Cancellation isn't always reliable.
2. **Wait for the system to mark it `failed`.** The active-requests pill will update.
3. **Click into the failed dossier** — the error message is on the request popup.
4. **Create a new dossier** with the same intake. Most failures are transient.

If the same dossier fails twice in a row with the same error, contact your team lead — there may be a systemic issue (key rotation needed, vendor outage).

## "I got a Partial dossier"

`Partial` means: the dossier was generated, but some quality gates didn't fully pass. It's still useful.

### Reasons a dossier is marked Partial

1. **RocketReach had no firmographics for this org.** Common for `.gov`, `.edu`, smaller nonprofits. The banner at the top of the dossier explains. You'll see fewer **ᴿᴿ** pills than usual.
2. **Some research threads ran short on time** (heavy only). One or more of the four subagents failed. The dossier has the rest, but with gaps.
3. **The lint quality gate found shortfalls** that couldn't be improved in a retry within budget.

### What to do

- **Read the Partial banner** at the top of the dossier — it tells you specifically which gap caused the label.
- **Use the dossier as-is** for triage. The score and verdict are still meaningful.
- **For high-stakes outreach**, consider regenerating — sometimes the vendor data catches up between runs.

## "The score looks wrong"

You think a lead should be HOT and it's WARM, or vice versa. Three things to check:

### 1. Read the Score Summary table

It shows which sub-factor drove each dimension. A WARM score with Fit 22/25 + Intent 25/25 + Timing 15/30 + Budget 12/20 is "all signal except Timing" — the system saw intent but no procurement window.

### 2. Check for negative modifiers

Tab 2's "Scoring Rationale" section lists structural negative modifiers (-25 for competitor purchased, -20 for layoffs, etc.). One of these can drop a HOT lead to WARM.

### 3. Check for deal execution risks

Below negative modifiers: "Deal Execution Risks" (softer friction, -2 to -5 each). These appear in the **risk-adjusted composite** number shown alongside the raw score.

### When to push back

If the dossier missed a public signal — e.g., the prospect just announced a major breach yesterday and the dossier doesn't mention it — the research was incomplete. Two recoveries:
- **Regenerate** the dossier. Fresh research may catch what was missed.
- **Add it manually** in your CRM — the system isn't always going to see everything.

## "The dossier shows wrong contact info"

The lead's email is wrong, LinkedIn URL is wrong, or the system attributed someone to the wrong DMU role.

### Where each piece comes from

- **Email** — from your intake. If you typed it wrong, the dossier carries that through.
- **LinkedIn URL** — your intake first; if not provided, the system searches.
- **DMU role** (champion, evaluator, etc.) — the AI's interpretation of public signals. Sometimes wrong, especially for new hires.

### How to verify

- The **ᴿᴿ** pill next to an email means RocketReach verified it. Trust those.
- A name without an **ᴿᴿ** pill came from the AI's synthesis — verify in LinkedIn before reaching out.
- Tab 2's "Person Profile" section lists what the system found about the contact and how it found it.

### When to regenerate

If multiple fields are wrong, regenerate with a more complete intake (add LinkedIn URL or company URL if you only used email; add notes clarifying the actual title).

## "I can't see Recommended Outreach"

Outreach is generated only for HOT and WARM tiers. COOL and COLD leads skip the section by design — the emails wouldn't be high-value.

If a HOT/WARM lead is missing outreach:
- Check the Partial banner — sometimes outreach is one of the gaps.
- Regenerate.

## "The iframe is blank or broken"

The dossier HTML loads in an iframe. Three causes for a blank iframe:

1. **Signed URL expired.** Signed URLs live 1 hour. Refresh the page and the iframe gets a new URL.
2. **Network blocked** — corporate firewalls sometimes block the Stratus subdomain. Try from a different network.
3. **Browser blocked third-party content** — check your browser's privacy settings. The dossier serves from a different origin than the app for security reasons.

If none of these apply, click **Open in new tab** next to the iframe. If the new tab also fails, the HTML itself is broken — contact an admin.

## "I can't sign in"

1. **Did you confirm your email?** Check spam.
2. **Try incognito.** Rules out cookie issues.
3. **Forgot password** link — Catalyst sends a reset email.
4. **Account deactivated?** Ask an admin.
5. **Catalyst Auth outage?** Check https://status.zoho.com/.

## "I made a mistake — can I undo it?"

| Mistake | Reversible? |
| --- | --- |
| Submitted wrong intake | Yes — let it finish, then ignore. Create a new dossier with the right intake. |
| Regenerated by accident | Yes — the old dossier still exists at the old URL. Delete the new one (admin) if you don't want it. |
| Deleted a lead (admin) | **No.** Deletion is permanent. |
| Uploaded the wrong CSV | Yes — delete the new leads (admin). |
| Sent the dossier to a customer | The URL is stable; if you regenerate later, the customer's bookmark still shows what you sent. |

## When to escalate

- Same error twice in a row with the same intake → contact admin.
- Dossier shows another user's data → **immediate escalation** to admin (security issue).
- Sign-in completely broken for everyone → contact admin (likely a Catalyst outage).

## Up next

→ [Frequently asked questions](./07-faq.md)
