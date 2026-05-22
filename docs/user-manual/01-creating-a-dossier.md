# 01 — Creating a Dossier

The core workflow. End-to-end, from intake to a finished scored dossier you can act on.

## Open the intake modal

From any page, click **Create Dossier** in the top-right or the dashboard CTA. A dialog appears with five fields.

> _Screenshot placeholder: `./screenshots/intake-modal.png`_

## Fill the form

You don't need every field — but the more you give, the better the dossier.

| Field | Required? | Example | Tip |
| --- | --- | --- | --- |
| **Lead name** | Recommended | `Perry Amo-Mensah` | If you have a contact, fill this. Improves personalization. |
| **Email** | One of these is needed | `pmensah@burlingtonnc.gov` | Email domain drives every preflight probe — best single input. |
| **LinkedIn URL** | One of these is needed | `https://linkedin.com/in/pamomens/` | Useful when email is private or you only know the LinkedIn profile. |
| **Company URL** | One of these is needed | `https://burlingtonnc.gov` | A fine standalone input — the dossier will discover names from there. |
| **Notes** | Optional | "Warm intro from Mayor's office; need to act before Q3 budget freeze" | Free-form context the system passes to research. |

### The minimum rule

You must provide at least one of:
- Email **with** a lead name, OR
- LinkedIn URL, OR
- Company URL.

LinkedIn URL alone (no lead name, no email, no company URL) is **not enough** — the system can't derive a domain from a LinkedIn profile alone. The form blocks submit until the minimum is met.

## Submit

Click **Create Dossier**. Three things happen:

1. The modal closes.
2. A toast confirms the request was accepted.
3. A pill appears in the bottom-right showing the new request in flight.

You can now navigate anywhere else in the app — the pill follows you.

> _Screenshot placeholder: `./screenshots/intake-submitted.png`_

## Watch the progress

Click the floating pill (bottom right). A popup expands showing the stage progression:

```
queued       → request is in the queue, hasn't started yet
preflight    → free-source OSINT (DNS, government records, breach catalogs)
rocketreach  → premium contact + firmographic enrichment
synthesis    → Claude is generating the dossier (the longest stage)
rendering    → producing the HTML
lint         → quality check (may trigger a retry if the result is thin)
upload       → saving to storage
done         → finished, click to view
```

Most light dossiers finish in **3-5 minutes**. Heavy dossiers (see below) take **8-13 minutes**.

> _Screenshot placeholder: `./screenshots/active-pill-popup.png`_

## When it finishes

The pill turns green and shows "Done". Click it to jump to the lead detail page, or close the popup and navigate to **Leads** at your convenience — the dossier is saved.

## The "Heavy mode" power tool

For HOT-suspected leads — named exec, complex compliance posture, big-money targets — there's a deeper research mode. It runs four parallel research subagents instead of one, producing a denser dossier with more sources and a richer competitive analysis.

**The tradeoff:** ~3× the wall-time, ~3× the cost. Use it sparingly.

### How to enable heavy mode

1. Open the intake modal as usual.
2. **Tap the modal title 5 times within 3 seconds.** A hidden "Heavy" checkbox appears.
3. Check the box.
4. Fill the form and submit.

The 5-tap gate is intentional friction — you should have to think about whether to spend the extra time and cost. If you accidentally enable it, just uncheck the box before submitting.

> _Screenshot placeholder: `./screenshots/heavy-mode-toggle.png`_

### When to use heavy

| Use heavy when... | Use light when... |
| --- | --- |
| Named exec at a Fortune-1000 | Cold-email volume play |
| Complex compliance posture (HIPAA, FedRAMP, CJIS) | First-touch on a startup |
| Public company with multiple incumbent vendors | Quick research before a meeting in 10 min |
| Big deal size — clearly worth the extra wait | Re-running an existing lead (use refresh; not heavy) |

There's no automated rule. Trust your judgment — and your manager's, if budget is tight.

## What if the intake is wrong?

If you submitted with a typo or wrong email, **let the dossier finish** if it's already running — cancelling mid-flight is not always reliable. Once done, ignore that dossier and create a new one with the correct intake. The system never overwrites; both will live in your **Leads** list, and you can delete the wrong one.

## What if the same person is already being processed?

The system detects when you (or someone on your team) is currently running a dossier for the same email / LinkedIn / company URL. Instead of starting a duplicate, it returns the existing request ID with a 409 status. The UI surfaces a "Already in progress — click to track" toast.

## Regenerating later

Once a dossier is done, you can regenerate it (e.g., if you want fresh data 3 months later). On the lead detail page, click **Regenerate**. The intake is pre-filled with the previous values — confirm or edit, then submit.

**Regeneration always creates a NEW lead row.** The old dossier stays exactly as it was — frozen in time, with its old URL. Both the old and new versions show in your **Leads** list. This is by design: if you sent the old dossier to a teammate and they bookmarked the URL, that URL never breaks.

## Up next

→ [Reading the dossier](./02-reading-the-dossier.md)
