# 10 — Security & RBAC

How the application authenticates users, authorizes actions, and protects data at rest. Two-layer model: Catalyst's infrastructure auth at the platform level, the application's own role model on top.

## Authentication: Catalyst Native Auth

Every authenticated request carries a Catalyst session cookie set on the project's primary domain. The cookie is HttpOnly and Secure. Login flows:

1. **Self-signup** — `POST /server/api/auth/signup` (public). Creates a `zcatalyst_sdk.userManagement` user, sends a Catalyst confirmation email via `lib/mailer.js`.
2. **Email-link confirmation** — user clicks the link in the email, lands on Catalyst's hosted confirmation page.
3. **Login** — Catalyst's hosted login form (the SPA redirects there on 401). Returns a session cookie.
4. **Subsequent requests** — cookie auto-sent on `credentials: 'include'` from the SPA.

The Catalyst-hosted login URL is project-specific; it's configured in `app/src/components/AuthGate.tsx` and the project's Catalyst Auth settings (Console → Authentication).

There is **no password handling in this codebase** — Catalyst owns the credential store, password hashing, reset flows, and email link signing. We never see or store a password.

## The two-role model

Two separate role concepts cohabit. Confusing them is dangerous.

### Catalyst project-user role (infrastructure)

Catalyst's own concept. Every user in a Catalyst project has one of:
- **App Administrator** — full read/write across the Catalyst console for this project. Can deploy, view function logs, edit Data Store rows directly.
- **App User** — uses the application, can't see the console.

This role lives in Catalyst's `role_details` payload on each user. There are currently **1 App Administrator** (`iaminzoho@gmail.com`) and **4 App Users** in the development environment.

### Application role (RBAC)

The application's own role lives in the `user_roles.role` column:
- `admin` — can use admin-only API routes (`/server/api/admin/*`).
- `user` — standard application user.

This role is separate from the Catalyst project-user role. An App User can be application `admin`. An App Administrator might be application `user`. They're orthogonal.

### Why both exist

App Administrator gives you console access. Application `admin` gives you the ability to manage other users *within the application UI*. The product team might want a salesperson to admin the user list without giving them the keys to the Catalyst project. Conversely, an infrastructure engineer might be App Administrator without ever using the application.

## The App Administrator trap

There's a critical pitfall — never collapse the two roles by ORing them.

```javascript
// WRONG — silently over-grants application admin
const isAppAdmin =
    userRole === 'admin' ||
    /admin/i.test(catalystRoleDetails.role_name);
```

This pattern is tempting because it looks like a graceful fallback: "if the user is an App Administrator at the Catalyst level, treat them as application admin too." It fails because **Catalyst's default project-user role name is literally `"App Administrator"`** — the `/admin/i` regex matches it. Every project user gets application admin powers as a side effect.

The correct pattern is: use the `user_roles.role` column as the source of truth for application authorization. Treat Catalyst's project-user role as a fallback only when no `user_roles` row exists, and only to bootstrap the first admin. Per memory rule `feedback_catalyst_app_administrator_not_app_admin`.

The middleware in `functions/api/lib/auth.js::loadRole` follows this rule: it reads `user_roles`, auto-creates a `role='user'` row if absent, and only falls back to Catalyst's role for the very first admin bootstrap (a transitional concession).

## The middleware chain (recap)

From [`03-api-function.md`](./03-api-function.md):

```
attachCatalyst  →  requireUser  →  loadRole  →  [requireAdmin]
```

- **`attachCatalyst`** — initializes `zcatalyst_sdk` per request, attaches to `req.catalystApp`.
- **`requireUser`** — reads Catalyst session cookie; 401 if absent.
- **`loadRole`** — reads `user_roles` row, sets `req.userRole`. Auto-creates `user` row if missing. Throttles `last_seen_at` writes to once per 60 s.
- **`requireAdmin`** — applied only to `/admin/*` routes. Returns 403 unless `req.userRole === 'admin'`.

`/auth/signup` is mounted **before** `requireUser` so unauthenticated users can sign up. Everything else requires `requireUser`.

## Public vs authenticated endpoints

| Endpoint | Auth |
| --- | --- |
| `GET /server/api/health` | public |
| `POST /server/api/auth/signup` | public |
| `POST /server/api/auth/logout` | user |
| `GET /server/api/me` | user |
| `GET, GET/:id, DELETE /server/api/leads` | user |
| `POST /server/api/leads/upload` | user |
| `POST /server/api/dossiers/generate` | user |
| `GET /server/api/dossiers/active` | user |
| `GET /server/api/dossiers/:id/status` | user |
| `POST /server/api/dossiers/:id/cancel` | user |
| `GET /server/api/stats` | user |
| `GET, POST, DELETE /server/api/admin/*` | admin |

Authenticated routes are user-scoped — `GET /leads` returns only the requester's leads, never another user's. The scoping rule is `WHERE user_id = req.user.user_id` on every read.

## Stratus access control

Dossier HTML files live in the `dossiers` bucket. Object keys carry the owner's user_id (`dossiers/<user_id>/...`).

**The bucket is NOT public.** Stratus signed URLs are the only way clients can read HTML. The signing flow:

1. SPA requests `GET /server/api/leads/:id` → API.
2. API checks `req.user.user_id === lead.user_id`; 404 otherwise.
3. API calls `stratus.signUrl(app, lead.storage_path, SIGNED_URL_TTL_SECONDS)`.
4. API returns the signed URL in the response.
5. SPA's `<iframe src={signed_url}>` loads the HTML cross-origin from `dossiers-development.zohostratus.in`.

The signed URL has a 1-hour default TTL (`SIGNED_URL_TTL_SECONDS = 3600`). After expiry, a refresh of the lead detail page issues a new URL. The signed URL is **not stored anywhere persistent** — it's regenerated on every load.

**Why not direct GET on the bucket?** Stratus enforces bucket-level access; the bucket is private. Pre-signed URLs are the only client-readable path.

## CORS posture

Same-origin in production (`https://lead-insight-hub-60066539659...`); same-origin in dev because Vite proxies `/server` to localhost:3000. The Catalyst Function does not set any wildcard `Access-Control-Allow-Origin` headers. If you ever need to call the API from a different origin (e.g., from a CRM-integration browser app), add an explicit allowlist in `functions/api/index.js`.

## Input validation and injection

- **Express body parser:** JSON limit 6 MB, urlencoded limit 6 MB.
- **CSV upload:** parsed via `multer` + `node-html-parser`. Field count and per-row size are bounded.
- **ZCQL:** All user-supplied values go through parameterized inserts via the SDK (`update_row({ ROWID, ... })`). Free-form ZCQL `SELECT` strings only carry server-derived values (e.g., `ROWID = ${int(request_id)}`). Be cautious if you add a new ZCQL string with user input — sanitize first.

## Audit and access logs

- **Catalyst Function logs** — Catalyst Console → Functions → `<function-name>` → Logs. Captures every `console.error` and stdout/stderr line. Retained per Catalyst's default policy (~30 days at the time of this baseline).
- **Application-level audit** — the `audit_events` table (see `06-data-model.md`) is the org-wide activity log, written fire-and-forget by `lib/audit.js` from the login beacon (`POST /me/session-start`), dossier creation, leads search, and admin mutations. Surfaced at the `/audit` page via `routes/audit.js`.
- **Audit-log visibility is admin-gated** — every authenticated user GENERATES audit events, but **reading** the org-wide log (`GET /audit` + `/audit/summary`) is restricted to admins and the super-admin via `requireAdminOrSuperAdmin` (the `/audit` UI route is guarded the same way client-side, and the nav link is hidden for non-admins). Within that admin audience the log is fully transparent — it exposes every user's exact free-text search queries and login times — so admins can see what the whole team searched. The table is append-only (no API mutate/delete path); the only delete path is the 120-day retention sweep.
- **No PII redaction** — function logs may contain prospect emails when error paths log `console.error("unhandled:", err)`. Treat function logs as containing PII. `audit_events.target_label` likewise stores raw search queries and prospect names.

## Self-signup posture

The current configuration allows **anyone with a Zoho-deliverable email address** to sign up via `POST /server/api/auth/signup`. The flow:

1. POST creates the Catalyst user.
2. Catalyst sends the confirmation email.
3. The user must confirm before the first authenticated request will succeed.

For a beta or invite-only posture, replace the public signup route with one that requires a token (e.g., a signed link generated by `/admin/users/invite`). At v1.0.0, the team has accepted the public-signup risk for development.

## Sensitive data inventory

| Data | Where | Sensitivity |
| --- | --- | --- |
| Prospect emails (intake) | `dossier_requests.intake_email`, `leads.email` | Medium — could trigger spam/abuse if exfiltrated |
| Dossier HTML | Stratus `dossiers` bucket | Medium — contains scoring and rep notes |
| Anthropic API key | Function env var | High |
| RocketReach API key | Function env var | High |
| Catalyst session cookies | Browser, HttpOnly | High |

Rotation cadence for the high-sensitivity items → [`maintenance/07-credentials-and-rotation.md`](../maintenance/07-credentials-and-rotation.md).

## Cross-references

- The application's role enforcement code → [03-api-function.md](./03-api-function.md)
- Catalyst Auth integration details → [07-integrations.md](./07-integrations.md)
- Why signed URLs are used for the iframe → [02-frontend-vite-react.md](./02-frontend-vite-react.md)
- Credential rotation cadence → [`maintenance/07-credentials-and-rotation.md`](../maintenance/07-credentials-and-rotation.md)
