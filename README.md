# Lead Insight Hub — Catalyst Edition

B2B lead-intelligence webapp migrated from Supabase to Zoho Catalyst.

## Stack

- **Frontend**: Vite + React 19 + TypeScript + TanStack Router (SPA, no SSR)
- **Backend**: Single Advanced I/O Function (Express on Node 18)
- **Database**: Catalyst Data Store (6 tables: leads, lead_signals, user_roles, dossier_requests, app_settings, audit_events)
- **Storage**: Catalyst Stratus (`dossiers` bucket)
- **Auth**: Catalyst Native Auth
- **Hosting**: Catalyst Slate (frontend) + Catalyst Functions (backend)
- **Data center**: IN

## Project IDs

- Project ID: `31210000000133001`
- ZAID: `50042133518`
- Org ID: `60066539659`
- DC: `in`

## Directory layout

```
catalyst.json                  # project manifest (functions + client)
catalyst-config.json           # env vars (GITIGNORED)
functions/api/                 # Express app — Advanced I/O Function
  index.js
  routes/{signup,auth,me,leads,dossiers,stats,admin,audit}.js
  lib/{auth,db,stratus,parser,audit,storeDossier,mailer}.js
functions/eliss-generator/     # Python 3.9 Job Function — ELISS Light
functions/eliss-heavy-generator/ # Python 3.9 Job Function — ELISS Heavy
functions/dossier-sweeper/     # Node 18 Job Function — global self-heal + audit retention
app/                           # Vite SPA
  src/
  dist/                        # build output → deployed by Slate
```

## Local dev

```
# Function on :3000
node ".../catalyst.js" serve

# SPA on :5173 (proxies /server → :3000)
cd app && npm run dev
```

## Deploy

```
cd app && npm run build
node ".../catalyst.js" deploy
```
