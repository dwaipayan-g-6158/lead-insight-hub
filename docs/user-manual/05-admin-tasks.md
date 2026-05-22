# 05 — Admin Tasks

This page is for users with the application **admin** role. If you don't see an **Admin** tab in the nav, skip this — none of this applies to you.

## What admins can do

- Invite new users (by sending the signup link or pre-creating accounts).
- Change a user's application role (`user` ↔ `admin`).
- Deactivate or remove users.
- View the audit / activity feed across all users.
- Delete leads (their own and others').
- View aggregate stats not visible in the user dashboard.

## Two role concepts (worth re-stating)

This often confuses people. There are **two separate role systems** at play:

| System | Role values | Source | What it controls |
| --- | --- | --- | --- |
| **Catalyst project-user** | App Administrator, App User | Catalyst Console (set by the project owner) | Access to the Catalyst back-end console — deploys, function logs, raw Data Store edits |
| **Application admin** | `admin`, `user` | `user_roles` table inside this app | Access to the Admin tab in this UI — user management, lead deletion |

Being a Catalyst App Administrator does **not** automatically make you an application admin. The two are independent. The app reads its own `user_roles.role` field — never Catalyst's.

If you need admin in this app, ask an existing application admin to grant it via the Admin → User Management panel.

## User management

Click **Admin** in the top nav. The user list page shows every signed-up user.

> _Screenshot placeholder: `./screenshots/admin-user-list.png`_

Columns:
- **Email** — the user's account email.
- **First Seen** — when they signed up.
- **Last Active** — most recent authenticated request (60s throttled — won't update more than once a minute even if they're actively clicking).
- **Confirmed** — yes/no — has the user clicked the email confirmation link?
- **App Role** — `admin` or `user`.
- **Actions** — per-row buttons (see below).

### Change a user's role

1. Find the user in the list.
2. Click the **Actions** menu.
3. Select **Make admin** or **Make user**.
4. Confirm in the dialog.

The change is immediate. The user does not need to log out; their next authenticated request reads the new role.

### Deactivate a user

1. Actions → **Deactivate**.
2. Confirm.

Deactivation prevents the user from signing in. Their existing leads are preserved. Reactivate at any time via Actions → **Activate**.

### Resend confirmation email

If a new user hasn't confirmed their email and lost the original message:

1. Actions → **Resend confirmation**.
2. The system regenerates the link and sends it.

### Invite a new user (without self-signup)

Currently this requires either:
1. Asking them to sign up self-service via `/signup`.
2. Pre-creating an account via Catalyst console (Console → User Management → Add User), then promoting them to admin in this UI.

A built-in invite flow with token-based pre-confirmation is a backlog item — not in v1.0.0.

## Lead deletion (admin)

From any lead detail page, admins see a **Delete** button next to **Regenerate**.

1. Click **Delete**.
2. Confirm in the dialog (twice — to discourage accidents).

What gets deleted:
- The `leads` row.
- All matching `lead_signals` rows (via `ON DELETE CASCADE`).
- The Stratus HTML file at the lead's `storage_path`.
- The corresponding `dossier_requests` row's `lead_id` reference becomes a dangling pointer (the request row itself is kept for history).

**Not recoverable.** Catalyst's automated daily backups *may* contain the row, but recovery is an ops task requiring console access. Don't delete unless certain.

## Audit and activity

There is **no dedicated audit-events table at v1.0.0**. What you can see:

- **Per-user activity:** `last_seen_at` on each user row.
- **Per-lead history:** `CREATEDTIME`, `MODIFIEDTIME`, `report_date`.
- **Per-request history:** `dossier_requests` rows track every generation attempt, including failures.

If you need a richer audit log (e.g., "who deleted lead X at what time"), file a CR. The natural shape is a new `audit_events` table written by the admin route handlers.

## Aggregate stats

The dashboard's stats cards show **only your own** leads. To see aggregate stats across all users:

Currently — there's no in-app view at v1.0.0. Admins with Catalyst console access can run ZCQL queries against the `leads` and `dossier_requests` tables (Console → Data Store → table → Execute Query). Common queries:

```sql
-- Total leads by tier across all users
SELECT tier, COUNT(*) FROM leads GROUP BY tier;

-- Generation success rate, last 30 days
SELECT status, COUNT(*) FROM dossier_requests
WHERE CREATEDTIME > '<30 days ago>'
GROUP BY status;

-- Most-active users
SELECT user_id, COUNT(*) FROM leads GROUP BY user_id ORDER BY 2 DESC LIMIT 10;
```

A dedicated admin analytics dashboard is a backlog item.

## What admins shouldn't do

- **Don't directly edit `leads` table data via Catalyst console** — the application has no audit trail for direct edits, and you'll diverge from the source HTML. Use the application UI.
- **Don't reset another user's password** — Catalyst Auth owns this. The user must use the "Forgot password" flow.
- **Don't share your admin credentials** — promote a different user to admin instead.

## Cross-references

- The user-management API surface and security gates → [`../architecture/03-api-function.md`](../architecture/03-api-function.md) (`/admin/*` routes)
- Why the App Administrator vs application `admin` distinction matters → [`../architecture/10-security-and-rbac.md`](../architecture/10-security-and-rbac.md)
- How to triage user-reported issues that come into your admin queue → [`../maintenance/02-issue-triage.md`](../maintenance/02-issue-triage.md)

## Up next

→ [Troubleshooting common issues](./06-troubleshooting.md)
