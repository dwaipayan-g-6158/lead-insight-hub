# 02 — Frontend (Vite + React)

The user-facing SPA. Single-page app, no SSR. Built with Vite to a static bundle, deployed via Catalyst's Web Client Hosting.

## Stack

| Concern | Tool |
| --- | --- |
| Build | Vite 5 (`app/vite.config.ts`) |
| UI library | React 19 + TypeScript |
| Routing | TanStack Router with auto code-splitting |
| Styling | Tailwind CSS + shadcn/ui (Radix primitives) |
| Charts | Recharts |
| Toasts | Sonner |
| Forms | react-hook-form + zod (where validation matters) |
| HTTP | Native `fetch` wrapped in `app/src/lib/api.ts` |

## Dev server

```powershell
cd app
npm install        # first time only
npm run dev        # serves on http://localhost:5173
```

Vite proxies any `/server` request to `http://localhost:3000` (the Catalyst function `catalyst serve` runs there). That proxy is the dev-time equivalent of the production path-prefix routing — the SPA always calls `/server/api/...`; only the suffix changes.

In production, the SPA is served from `https://lead-insight-hub-60066539659.development.catalystserverless.in/app/` and the API lives at `/server/api/...` on the same origin.

## File layout

```
app/
├── vite.config.ts            # Vite + Tailwind + TanStack Router plugin
├── src/
│   ├── main.tsx              # React entry, router instantiation
│   ├── routeTree.gen.ts      # GENERATED — do not edit
│   ├── routes/
│   │   ├── __root.tsx        # Layout shell, AuthGate, AppShell
│   │   ├── index.tsx         # "/" → DashboardPage
│   │   ├── leads.tsx         # "/leads" parent layout
│   │   ├── leads.index.tsx   # "/leads" → LeadsListPage
│   │   ├── leads.$leadId.tsx # "/leads/:leadId" → LeadDetailPage
│   │   ├── upload.tsx        # "/upload" → UploadPage
│   │   ├── admin.tsx         # "/admin" → AdminPage (admin-gated)
│   │   └── signup.tsx        # "/signup" → SignUpPage (public)
│   ├── components/           # Feature components (see below)
│   ├── lib/
│   │   ├── api.ts            # Typed API client
│   │   └── auth.tsx          # Catalyst Native Auth session hook
│   └── components/ui/        # shadcn primitives (do not modify by hand)
```

## Route map

| Route | Source | Component | Auth |
| --- | --- | --- | --- |
| `/` | `app/src/routes/index.tsx` | `DashboardPage.tsx` | User |
| `/leads` | `app/src/routes/leads.index.tsx` | `LeadsListPage.tsx` | User |
| `/leads/:leadId` | `app/src/routes/leads.$leadId.tsx` | `LeadDetailPage.tsx` | User |
| `/upload` | `app/src/routes/upload.tsx` | `UploadPage.tsx` | User |
| `/admin` | `app/src/routes/admin.tsx` | `AdminPage.tsx` | Admin |
| `/signup` | `app/src/routes/signup.tsx` | `SignUpPage.tsx` | Public |

Auth gating is implemented in `__root.tsx` via `AuthGate.tsx` — unauthenticated users are bounced to Catalyst's hosted login. Admin gating is enforced both client-side (`AdminPage.tsx` checks role) and server-side (`requireAdmin` middleware in `functions/api/`). The client check is convenience; the server is authoritative.

## Key components

The components carrying real logic (not shadcn primitives):

### `AppShell.tsx`
Top-level chrome: header, nav, account menu. Renders the `ActiveRequestsPill` so it floats above all routes.

### `AuthGate.tsx`
Wraps protected routes. Checks the Catalyst Native Auth session via `lib/auth.tsx`. On 401, redirects to the hosted login URL configured in `__root.tsx`.

### `DashboardPage.tsx`
Stats grid (total leads, HOT count, average score), recent activity list, "Create Dossier" CTA. Reads from `GET /server/api/stats` (paginated).

### `LeadsListPage.tsx`
The lead inbox. Search box, tier filter (HOT/WARM/COOL/COLD), ICP rating filter (1-5 stars). Each row shows lead name, company, composite score, tier badge, and creation date. Clicking a row navigates to `/leads/:leadId`.

### `LeadDetailPage.tsx`
The dossier viewer. Renders:
- A summary card (score, tier, key drivers) at the top.
- An iframe pointing at the Stratus signed URL for the HTML dossier.
- A "Regenerate" button that opens `CreateDossierModal` pre-filled with this lead's intake.
- A copy-to-clipboard handler for the three recommended outreach emails (via `postMessage` from the iframe).

The iframe is **sandboxed and cross-origin** (Stratus serves on `dossiers-development.zohostratus.in`, not the app origin). That means the parent page cannot read iframe DOM directly — interactions like "copy outreach" go through `postMessage`. See memory rule `reference_lead_insight_hub_dossier_html_access`.

### `CreateDossierModal.tsx`
The intake form. Fields: `lead_name`, `email`, `linkedin_url`, `company_url`, `notes`. Validation rules:
- At least one of `email + lead_name`, `linkedin_url`, or `company_url` is required.
- `email` and `company_url` are checked for shape (regex, not network).

**The 5-tap heavy-mode gate:** tapping the modal title five times within 3 seconds toggles a hidden "Heavy" checkbox. When checked, the POST body carries `_x: "h"` and the API dispatches `eliss-heavy-generator` instead of `eliss-generator`. The heavy mode is also allow-listed server-side via `featureFlags.js::isHeavyAllowed()` — the UI tap is necessary but not sufficient.

### `ActiveRequestsPill.tsx`
Floating pill that lists in-flight dossier requests for the current user. Polls `GET /server/api/dossiers/active` every 10 seconds. Shows stage badges (`preflight`, `synthesis`, `rendering`, …) and an estimated remaining time. Clicking a pill opens `DossierActivityPopup`.

### `DossierActivityPopup.tsx`
Detailed progress UI for a single request. Shows the stage timeline, elapsed time, token usage, RocketReach call count, and the `rr_degraded` banner when RR coverage was incomplete.

### `UploadPage.tsx`
CSV / HTML bulk import. Used to backfill dossiers from legacy systems. Calls `POST /server/api/leads/upload`. See [`user-manual/04-csv-upload.md`](../user-manual/04-csv-upload.md) for the supported format.

### `AdminPage.tsx`
User management UI. Lists project users, shows their app role, allows promoting a user to admin or deactivating them. Calls `GET/POST/DELETE /server/api/admin/users`. Admin-gated server-side.

### `SignUpPage.tsx`
Self-service signup. Posts to `POST /server/api/auth/signup` (the only public endpoint). On success, the user receives a Catalyst confirmation email and is redirected to the hosted login.

## API client (`app/src/lib/api.ts`)

A thin typed wrapper around `fetch` with these surface functions:

| Function | Method | Path | Purpose |
| --- | --- | --- | --- |
| `me()` | GET | `/server/api/me` | Current user + role |
| `listLeads(params)` | GET | `/server/api/leads` | Paginated list with filters |
| `getLead(id)` | GET | `/server/api/leads/:id` | Lead + signals + html signed URL |
| `createDossierRequest(payload)` | POST | `/server/api/dossiers/generate` | Kick off a generation job |
| `pollDossierRequest(id)` | GET | `/server/api/dossiers/:id/status` | Stage + status snapshot |
| `listActiveRequests()` | GET | `/server/api/dossiers/active` | All in-flight for current user |
| `uploadDossier(file)` | POST | `/server/api/leads/upload` | CSV / HTML bulk upload |
| `getStats()` | GET | `/server/api/stats` | Dashboard counters |
| `adminListUsers()` | GET | `/server/api/admin/users` | Admin-only |
| `adminSetRole(userId, role)` | POST | `/server/api/admin/users/:id/role` | Admin-only |

All functions handle Catalyst's session cookie automatically (`credentials: 'include'`) and surface failures as `Error` with a parsed JSON `message`.

## Build output

`npm run build` produces:

```
app/dist/
├── index.html          # SPA entrypoint
├── assets/
│   ├── index-<hash>.js
│   ├── index-<hash>.css
│   └── ... (route chunks, lazy-loaded)
├── favicon.ico
└── ...
```

This directory is what `client.source` in `catalyst.json` points at. Catalyst Web Client Hosting serves it from the project's primary domain with path-based routing — `/server/*` goes to the API function, everything else falls through to `index.html` (SPA fallback).

> Mobile responsiveness was audited 2026-05-15 with findings in `qa-audit-2026-05-15/FOLLOWUPS.md`. The fixes for sticky positioning, sheet close, and verdict headline truncation have shipped.

## Cross-references

- The REST endpoints the client talks to → [03-api-function.md](./03-api-function.md)
- Catalyst Auth session flow → [10-security-and-rbac.md](./10-security-and-rbac.md)
- Why the iframe is cross-origin sandboxed → [07-integrations.md](./07-integrations.md) (Stratus section)
- Heavy-mode allowlist behavior → [05-eliss-heavy-generator.md](./05-eliss-heavy-generator.md)
