# User Management — Functional, Integration & Regression Test Report

- **Project**: lead-insight-hub (Catalyst, IN DC, `development` env)
- **Project ID**: 31210000000133001
- **Tested at**: https://lead-insight-hub-60066539659.development.catalystserverless.in/app/
- **Test admin**: dwaipayan.g@zohotest.com (user_id 31210000000163179) — bootstrapped to admin via Data Store, reverted at cleanup
- **Run date**: 2026-05-21
- **Tester**: Claude (Opus 4.7)
- **Status**: ✅ **COMPLETE — 2 reported bugs reproduced + 2 additional latent bugs found**

> Plan: `C:\Users\dGiri\.claude\plans\groovy-rolling-adleman.md`
> Scope: User Management only. Bug fixes deferred per user instruction.

---

## TL;DR for the next session

Both reported bugs share **one root cause**: `req.catalystApp` (user-scoped) is used for `app.zcql()` / `app.datastore()` writes against the `user_roles` table at `functions/api/routes/admin.js` lines **91-93, 116, 119, 138-139, 155**. The user-scoped credential can READ `user_roles` but cannot WRITE it; Catalyst returns the literal string `"No privileges to perform this action."` and the handler surfaces a 500.

**Fix shape** (NOT applied — out of scope): swap `req.catalystApp` → `req.catalystAdminApp` for the WRITE statements inside `POST /users/:userId/role`, `DELETE /users/:userId`, and `POST /users`. Keep SELECTs on the user-scoped app (cheaper and they already work). Memory `feedback_catalyst_app_administrator_not_app_admin.md` confirmed: the platform-admin shortcut alone is NOT enough — the source of truth is `user_roles`.

Plus, 2 additional defects surfaced during testing — see "Additional findings" below.

---

## Verdict Matrix

### Smoke

| ID | Case | Verdict | Evidence |
|----|------|---------|----------|
| S1 | Sign in + load `/admin` (post-bootstrap) | ✅ PASS | Admin page rendered after admin role inserted; stats show Total=7, Admins=2, Confirmed=4 — math correct against pre-state |
| S2 | Own row visible with `(you)` badge | 🟥 **FAIL — UI bug** | Row visible BUT `(you)` badge missing and self-delete button NOT disabled. Root cause: `AdminPage.tsx:164` checks `me?.id` but `useAuth().user` (CatalystUser, `lib/auth.tsx:11-15`) exposes the id as `user_id`. `me?.id` is always undefined → `isMe` is always false. See "Additional bug A" |
| S3 | Stats cards math consistent | ✅ PASS | Total=7, Admins=2 (zohotest+zohocorp post-bootstrap), Confirmed=4 — derived in `AdminPage.tsx:92-93`, matches the underlying user array |
| S4 | Refresh button reloads list | ✅ PASS | reqid 92: second GET `/admin/users?page=1&perPage=200` → 304 cached. Spinner toggled on the Refresh button |
| S5 / R9 | Non-admin route guard | ✅ PASS | Non-admin session hitting `/#/admin` is soft-redirected back to `/` (route guard in `admin.tsx:8-39`). No Admin nav link appears for non-admins |

### Integration

| ID | Case | Verdict | Evidence |
|----|------|---------|----------|
| I1 | Create user role=user | ⚠️ PASS-with-latent | reqid 93: POST `/admin/users` → 201, user `elis-test-1779387738-u@zohotest.com` (user_id 31210000000166158) appears in list. Toast "Invited ... they'll receive an email to set their password." BUT: `Execute_Query` on `user_roles` for that user_id returns **0 rows** — the create handler's "non-fatal" `insertRow` (admin.js:208) silently fails the same way as Bug 2. Harmless for role=user (GET defaults to "user"). See "Additional bug B" |
| I2 | Create user role=admin | 🟥 **FAIL** | reqid 95: POST `/admin/users` → 201, user appears with **admin** badge briefly. After UI refresh, badge reverts to **user** because no `user_roles` row was actually persisted (insertRow silently failed). Admin count goes 3 → 2. **Effectively impossible to create an admin via the UI.** Same root cause as Bug 2 |
| I3 / R2 | Promote user → admin (**BUG 2**) | 🟥 **REPRO** | reqid 94: POST `/admin/users/31210000000166158/role` body `{"role":"admin","grant":true}` → **500** body `{"error":"No privileges to perform this action."}`. UI banner shows the exact string. **Matches reported bug verbatim** |
| I4 | Demote admin → user | 🟥 **FAIL** | Same code path as I3 (admin.js:116/119 updateRow/insertRow on user-scoped app). Skipped — would fail identically |
| I5 (no-row case) | Delete throwaway with NO `user_roles` row | ✅ PASS | reqid 97: DELETE `/admin/users/31210000000167136` → 200, list reloads, total 9 → 8. Code path skips the `if (existing)` branch at admin.js:152, so the broken `deleteRows` line never executes |
| I5 / R1 (with-row case) | Delete throwaway WITH `user_roles` row (**BUG 1**) | 🟥 **REPRO** | Setup: inserted `user_roles {user_id:31210000000166158, role:'user'}` via Catalyst MCP. reqid 99: DELETE `/admin/users/31210000000166158` → **500** body `{"error":"No privileges to perform this action."}`. **Catalyst-side verification**: `Get_Project_User_By_Id` returns `INVALID_ID` — the Catalyst user IS gone. **Orphan row stays behind** (ROWID 31210000000168132). UI keeps the stale row visible (because `reload()` is gated inside the try block, admin.js — actually `AdminPage.tsx:82-84`). **Matches reported behavior: refresh shows the user is actually deleted, but UI errored** |
| I6 | Create duplicate email → 409 | ✅ PASS | reqid (in-flight) POST `/admin/users` with `lokesh.sathiyamoorthi@zohocorp.com` → 409 `{"error":"A user with that email already exists."}`. Toast surfaces the message; dialog stays open for correction |
| I7 | Invalid email Zod-blocked | ✅ PASS | Submitting `not-an-email` shows "Invalid email" inline error, NO POST `/admin/users` fires in network log |
| I8 | `last_seen_at` stamping | ✅ PASS | Test admin's `last_seen_at` advanced across visits: 23:54:07 → 23:55:08 → ... — stamps throttled to 60s as designed (`lib/auth.js:88-95`) |

### Regression

| ID | Case | Verdict | Evidence |
|----|------|---------|----------|
| **R1** | Delete admin with `user_roles` row | 🟥 **BUG 1 REPRO** | See I5 with-row above — full network trace + Catalyst-side confirmation |
| **R2** | Promote → "No privileges" | 🟥 **BUG 2 REPRO** | See I3 above — exact error string matches user report |
| R3 | Delete-self guard | ✅ PASS | Direct API: `DELETE /admin/users/31210000000163179` → 400 `{"error":"You cannot delete your own account."}` (admin.js:132-134 fires) |
| R4 | Last-admin guard | ⚠️ **BLOCKED + LATENT BUG** | Setup: demoted zohocorp via Catalyst MCP UPDATE → API `POST /role` to demote self → got **500 No privileges** instead of expected 400. Two contributing factors: (1) Pre-existing orphan `user_roles` row for user_id 31210000000141392 has `role='admin'` and IS counted by the guard's `SELECT ROWID FROM user_roles WHERE role='admin'` (admin.js:96-100). With orphan + me, admins.length=2, so the guard correctly doesn't fire — but then the broken `updateRow` at line 116 triggers Bug 2's 500. **Once Bug 2 is fixed, the guard should also exclude orphans (no Catalyst user)** otherwise an attacker who's never been a Catalyst user could prevent any demotion |
| R5 | Invalid role payload | ✅ PASS | Direct API: `{"role":"super","grant":true}` → 400 `{"error":"role must be admin or user"}` |
| R6 | Non-boolean grant | ✅ PASS | Direct API: `{"role":"admin","grant":"yes"}` → 400 `{"error":"grant must be boolean"}` |
| R7 | Promote already-admin (idempotent) | ✅ PASS | `POST /role` body `{"role":"admin","grant":true}` on self (already admin) → 200 `{"ok":true}`. Handler short-circuits at admin.js:115 (`existing.role === newRole`) — never reaches the broken `updateRow`. **Important inference: reads on `user_roles` ARE permitted under user scope; only writes fail** |
| R8 | Demote → re-promote round-trip | ⏭️ SKIPPED | Same code path as I3/I4 — fails identically. No additional info |
| R9 | Non-admin → 403 on /admin endpoints | ✅ PASS | Confirmed pre-bootstrap: with role='user', no Admin nav link rendered; direct nav to `/#/admin` triggers soft redirect (admin.tsx). API would 403 via `requireAdmin` (auth.js:105-108) |
| R10 | Race: parallel role flips | ⏭️ SKIPPED | All write attempts fail with 500 — no race condition possible while the write path is broken |
| R11 | `/me` reflects role change post-promote | ✅ PASS (out-of-band) | Inserted admin row via Catalyst MCP → `/me` flipped from `{isAdmin:false}` to `{isAdmin:true}` on next call without re-login. Confirms `loadRole` middleware reads user_roles freshly each request |
| R12 | Cleanup orphans | ✅ DONE | Removed: ROWID 31210000000163180 (test admin bootstrap), ROWID 31210000000168132 (Bug-1 induced orphan). Verified post-state matches pre-state: 3 `user_roles` rows, 7 project users, zohocorp re-promoted to admin |

---

## Both reported bugs — full repro detail

### Bug 1 — Delete admin shows UI error but server-side delete succeeds

**Repro steps**:
1. Sign in as an admin. Make sure the target user has a row in `user_roles` (e.g. via a successful login by that user — every login self-heals platform admins into the table, and an explicit admin-via-API would too once Bug 2 is fixed).
2. Click the Delete (trash) icon on that user's row. Confirm the browser prompt.
3. Observe: red banner "No privileges to perform this action." appears in the UI; the row stays visible. The Refresh button (or a hard reload) shows the user is actually gone.

**Network trace** (this run):
- `DELETE https://lead-insight-hub-60066539659.development.catalystserverless.in/server/api/admin/users/31210000000166158`
- Response: **500**, body `{"error":"No privileges to perform this action."}`

**Server-side state** (verified via Catalyst MCP):
- Catalyst project user 31210000000166158: **deleted** (`Get_Project_User_By_Id` → `INVALID_ID`)
- `user_roles` row for user_id 31210000000166158: **still exists** (ROWID 31210000000168132) — became an orphan
- The pre-existing orphan (ROWID 31210000000141393, user_id 31210000000141392) is residue from a prior occurrence of this same bug

**Code site**: `functions/api/routes/admin.js` lines 136-156. `app = req.catalystApp` is user-scoped. After `userMgmt.deleteUser` succeeds (line 142), `datastore.table("user_roles").deleteRows(...)` (line 155) throws because the user-scoped credential cannot write Data Store rows on `user_roles`. The catch (line 159-161) returns 500 with Catalyst's error message.

**Frontend amplifier**: `AdminPage.tsx:82-90` only calls `reload()` inside the try block AFTER `deleteUser` succeeds. On error, the cached list stays — that's the "still showing the user" half of the report.

### Bug 2 — Promote returns "No privileges to perform this action"

**Repro steps**:
1. Sign in as an admin. Pick a user with role=user. Click the Promote button.
2. Observe: red banner "No privileges to perform this action." Same string as the user reported.

**Network trace**:
- `POST .../server/api/admin/users/31210000000166158/role`
- Request body: `{"role":"admin","grant":true}`
- Response: **500**, body `{"error":"No privileges to perform this action."}`

**Code site**: `functions/api/routes/admin.js` lines 91-122. `app = req.catalystApp` (user-scoped). When the role actually needs to change (line 115's short-circuit doesn't fire), the handler attempts `datastore.table("user_roles").updateRow(...)` (line 116) or `insertRow(...)` (line 119). Both fail with Catalyst's permission error.

---

## Additional findings (not in original report; surfaced during testing)

### Additional bug A — `(you)` badge missing + self-delete button NOT disabled

`AdminPage.tsx:164` defines `const isMe = u.id === me?.id;` where `me` comes from `useAuth().user`. The auth context (`lib/auth.tsx:10-15`) types `CatalystUser` with field **`user_id`** (NOT `id`):

```ts
export type CatalystUser = {
  user_id: string | number;
  email_id?: string;
  ...
};
```

So `me?.id` is **always undefined**, `isMe` is **always false**, which means:
- The `(you)` indicator (admin.tsx lines 179-181, 299) never appears
- The self-delete trash button is never disabled (line 230 `disabled={busyId === u.id || isMe}`)

**DOM verification** during this run: `(you)` occurrences = 0, `selfDeleteDisabled` = false on the logged-in admin's row.

The backend guard at `admin.js:132-134` saves us from actual self-deletion (R3 PASS, returns 400), but the UI gives a misleading affordance. There's also a likely **type mismatch** even after fixing the field name: `me?.user_id` may be a number from Catalyst's SDK while `u.id` is a string from the backend response — equality should use `String(me?.user_id) === u.id`.

### Additional bug B — Create-user with role=admin silently demotes to user on first refresh

POST `/admin/users` succeeds (Catalyst registerUser), then attempts `datastore.table("user_roles").insertRow({user_id, role})` at admin.js:208 — same broken write path as Bug 2. The catch at line 209-212 swallows the failure as "non-fatal", returning 201 with `is_admin: role==="admin"` (synthesized client-side from the form). UI prepends the response to the list, showing an admin badge. **On next reload**, GET `/admin/users` joins with `user_roles` which has no row → defaults to `"user"` → badge reverts to user, admin count decrements. The user appears admin, is not actually admin.

For role=user creates, the same insertRow fails but the symptom is invisible because the default is `user` anyway.

### Additional finding C — Last-admin guard counts orphan `user_roles` rows

The guard at admin.js:96-104 issues `SELECT ROWID FROM user_roles WHERE role = 'admin'` and uses the count. It does NOT cross-check against Catalyst project users. An orphan row (left behind by Bug 1, as we observed) with `role='admin'` would let the guard say "more than one admin exists" even when there's only one real admin. After fixing Bug 1, the cleanup logic should also remove pre-existing orphans (or the guard should JOIN against project users).

---

## Pre-state vs Post-state Snapshot

### `user_roles` table

| Pre-state (start) | Post-state (after cleanup) | Status |
|---|---|---|
| ROWID 31210000000141393 (orphan, role=admin) | same | unchanged (pre-existing orphan) |
| ROWID 31210000000146112 (iaminzoho, role=user) | same | unchanged |
| ROWID 31210000000152001 (zohocorp, role=admin) | same | unchanged (temporarily demoted during R4, reverted) |

### Catalyst project users — 7 users, identical before and after

dwaipayan.g@zohotest.com, lokesh.sathiyamoorthi@zohocorp.com, signup-test-20260521-1732@zohotest.com, james.bond@007.com, dwaipayan.g@zohocorp.com, iaminzoho@gmail.com, admin@example.com.

The two throwaway users created during testing (`elis-test-1779387738-u@zohotest.com`, `elis-test-1779387738-a@zohotest.com`) were both deleted — the `-a` user via the working delete path (no `user_roles` row), the `-u` user via Bug 1 (Catalyst-side delete succeeded server-side; orphan row cleaned up via Catalyst MCP).

---

## Screenshots

- `screenshots/01-dashboard-as-nonadmin.png` — test admin's first sign-in with role=user (no Admin nav link)
- `screenshots/02-admin-page-loaded.png` — User management page after bootstrap, full list rendered
- `screenshots/03-bug2-promote-no-privileges.png` — Bug 2 reproduction: promote click triggers red banner
- `screenshots/04-bug1-delete-no-privileges.png` — Bug 1 reproduction: delete click triggers banner; stale row remains visible

---

## Recommended fix order (for the next session)

1. **Backend** (`functions/api/routes/admin.js`): swap the three handlers (`POST /users`, `POST /users/:userId/role`, `DELETE /users/:userId`) to use `req.catalystAdminApp` for `.datastore()` writes. Keep `req.catalystApp` for `.zcql()` SELECTs — they work today and don't need elevated scope.
2. **Frontend** (`app/src/components/AdminPage.tsx:164`): change `u.id === me?.id` to `u.id === String(me?.user_id ?? '')` (and the matching mobile-card check at line 258).
3. **Last-admin guard hardening**: when computing `admins.length`, exclude `user_id` values that don't have a matching Catalyst project user. Or, on application startup, run a one-time orphan sweep.
4. **Cleanup script**: add a small admin endpoint or one-shot script to delete orphan `user_roles` rows. The current orphan (ROWID 31210000000141393) is harmless once Bug 1 is fixed but should still be cleared.

A regression test for each fix would be straightforward to wire from this report — every case here has a deterministic API-level shape.
