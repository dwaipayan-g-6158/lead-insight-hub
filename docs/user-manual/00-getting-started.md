# 00 — Getting Started

Welcome. Lead Insight Hub turns a prospect's name, email, LinkedIn, or company URL into a fully-scored intelligence dossier — usually in 3-10 minutes. This page gets you from "logged out" to "looking at the dashboard."

## What you'll need

- A web browser (Chrome, Safari, Firefox — all current).
- An invite or self-signup email from your team.
- About 5 minutes the first time.

## Signing up (first time only)

1. Open the app: **https://lead-insight-hub-60066539659.development.catalystserverless.in/**
2. Click **Sign Up** at the bottom of the login form.
3. Enter your work email and a strong password.
4. Submit. The page tells you to check your inbox.
5. Open the confirmation email — subject `Lead Insight Hub: confirm your account`. Click the confirmation link.
6. Back in the app, sign in with the email + password you just set.

> If the confirmation email doesn't arrive in 5 minutes, check spam. If it's not there either, ask an admin to resend (admins can do this from the user-management panel — see [`05-admin-tasks.md`](./05-admin-tasks.md)).

> _Screenshot placeholder: `./screenshots/signup-flow.png`_

## Signing in (every other time)

1. Open the app URL.
2. Enter your email + password.
3. You land on the **Dashboard**.

Your session persists for several hours. If it expires while you're working, the app will bounce you back to the login screen and return you to where you were after sign-in.

## The dashboard at a glance

The dashboard is the first thing you see. Four sections:

### Top stats cards

Three or four counters at the top:
- **Total leads** — every dossier ever generated under your account.
- **HOT leads** — currently in the HOT tier (score 75-100).
- **Active requests** — dossiers being generated right now.
- **Recent leads** — the last few generated.

### Quick actions

- **Create Dossier** — opens the intake modal. This is your most common action. See [`01-creating-a-dossier.md`](./01-creating-a-dossier.md).
- **Upload CSV** — bulk-import existing dossiers from a file. See [`04-csv-upload.md`](./04-csv-upload.md).

### Recent activity

A timeline of recent events: leads created, dossiers completed, errors. Helpful for spotting "wait, did that one finish?" without leaving the dashboard.

### Charts (when you have ≥3 leads)

A small visualization of your lead distribution across tiers and ICP ratings. Updates live as you generate more.

> _Screenshot placeholder: `./screenshots/dashboard-overview.png`_

## Navigation map

The top nav (or hamburger menu on mobile) has:

| Tab | What's there |
| --- | --- |
| **Dashboard** (`/`) | The page you're on after sign-in. |
| **Leads** (`/leads`) | The full list of every dossier you've generated. Filters, search, sort. |
| **Upload** (`/upload`) | Bulk import (CSV or HTML). |
| **Admin** (`/admin`) | User management — visible only if you're an admin. |
| **Sign out** | Top-right account menu. |

> _Screenshot placeholder: `./screenshots/nav-desktop.png`_

## Floating "active requests" pill

In the bottom-right corner, you'll see a small floating pill any time you have a dossier in flight. It shows:
- How many requests are running.
- The current stage of each (e.g., "Researching", "Rendering", "Almost done").
- An estimated remaining time.

Click the pill to expand a detailed progress popup. The pill stays visible across pages — so you can browse other leads while a new one is being generated, without losing track.

> _Screenshot placeholder: `./screenshots/active-requests-pill.png`_

## Your first dossier

Ready to generate something? Head to [`01-creating-a-dossier.md`](./01-creating-a-dossier.md).

## If something goes wrong

- **Can't sign in?** Make sure you confirmed your email. If you did and it still fails, try a private/incognito window to rule out a stale cookie.
- **Stuck on a loading screen?** Refresh once. If it persists, check [`06-troubleshooting.md`](./06-troubleshooting.md).
- **Need an admin's help?** Reach out to your team lead — the user with the admin badge in the user-management panel.

## What this app is, and isn't

**It is** — a B2B lead-intelligence dossier generator. You give it a prospect, it gives you back research and scores tuned for ManageEngine AD360 and Log360 sales motions.

**It isn't** — a CRM. There's no pipeline, deal-stage tracking, or revenue attribution. The dossier helps you decide *whether* and *how* to engage a lead; logging that engagement happens in your CRM.

## Up next

→ [Creating your first dossier](./01-creating-a-dossier.md)
