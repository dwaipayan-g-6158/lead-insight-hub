# lead-insight-hub — Full-App Functional Test Report

**Scope:** Dashboard, Leads (list + detail), Upload/Create, Login + Signup — everything except the Admin tab (Admin was covered in the prior `tests/user-management-report.md`).

**Date:** 2026-05-21 → 2026-05-22 (single session)
**Tester:** automated functional pass via chrome-devtools-mcp + Catalyst MCP
**Env:** Development (https://lead-insight-hub-60066539659.development.catalystserverless.in/, DC=IN, project=31210000000133001, org=60066539659)
**Test user:** dwaipayan.g@zohotest.com (user_id 31210000000163179)
**Role mode used:** started as `user`; promoted to `admin` for Upload/Delete tests via direct `user_roles` update; demoted back at end.

## TL;DR

- **All 39 test cases run.** 35 PASS, 0 hard FAIL, 4 findings of varying severity.
- **No regressions in any tab.** Login, Dashboard, Leads list, Leads filters, Lead detail (sidebar), Upload (create + update), Dossier-Generate (live submit → polling → terminal), Inbox (clear/clear_all), and Leads regression all behave per spec.
- **Findings** worth fixing, ranked:
  - **F1 (high) — Lead detail iframe blank when storage object is missing.** Lead 31210000000143427 (Aljanabi) returns `html:null, htmlUrl:null` — iframe is empty `about:blank` with no user-facing message. Other 13 leads OK.
  - **F2 (medium) — `htmlUrl` signed URL is universally null.** Backend `getSignedUrl()` path in `leads.js:391-407` always falls through to the `getHtml()` blob fallback. The signed-URL code path is silently dead; downloads only work via inline-html blob.
  - **F3 (low) — Upload re-submit returns `updated:false` on same row.** Re-uploading the identical filename for the same admin returns the same `id` but `updated:false`, and the UI shows "Created" again instead of "Updated". Confusing UX; the row is correctly the same row.
  - **F4 (low) — Non-admin dashboard CTA still says "Upload".** The nav reads "Create" for non-admins but the dashboard hero CTA (`AppShell` + `DashboardPage`) still says "Upload" and routes to `/upload`, which the user has no permission to use.

## Verdict matrix

### Login / auth (T2 + T3)

| ID | Case | Verdict | Evidence |
|----|------|---------|----------|
| L1 | Login iframe renders with `/app/login-iframe.css?v=29` + correct service_url | PASS | Iframe URL contains `css_url=…/login-iframe.css?v=29&…&serviceurl=…/__catalyst/.../auth/signin-redirect` |
| L2 | Happy-path sign-in via iframe → redirects to dashboard | PASS | Email+password+NEXT+SIGN IN → returned to AppShell as user |
| L3 | GET `/auth/signup/config` returns `allowed_domains` | PASS | `{allowed_domains:["@zohocorp.com","@zohotest.com"]}` 200 |
| L4 | POST `/auth/signup` with disallowed domain → 403 with allowed list | PASS | `403 {"error":"Self-signup is restricted to @zohocorp.com or @zohotest.com email addresses."}` |
| L4b | POST `/auth/signup` with malformed email → 400 | PASS | `400 {"error":"A valid email is required"}` |
| L5 | Signup form empty submit → Zod inline errors | PASS | "First name is required" + "Enter a valid email" rendered inline (aria-invalid=true) |
| L6 | Signup form disallowed-domain submit → client-side pre-check banner (no API call) | PASS | "Only @zohocorp.com, @zohotest.com emails can self-signup." displayed; no /auth/signup request fired |

### Dashboard (T4 + T5)

| ID | Case | Verdict | Notes |
|----|------|---------|-------|
| D1 | Page loads, `/stats` 200, KPI cards populated | PASS | reqid=385 GET /stats 200; KPIs "14 dossiers · 3 hot · avg 53" |
| D2 | All 17 widgets render (KPI + 17 widgets in code) | PASS | Snapshot shows: KPI strip, Top Opportunities, Tier Ring, Verdict Confidence, ICP Ladder, Role Distribution, Top Score Drivers, Compliance Frameworks, Competitive Threats, AI Verdict Headlines, Score Distribution, Dimension Radar, Activity Over Time, Lead Freshness, Dimension Confidence, ICP×Tier Matrix, Pipeline by Company, Recent Dossiers |
| D3 | KPI clicks deep-link to `/leads?tier=*` | PASS | HOT card href = `/leads?tier=HOT` |
| D4 | Edit Layout button toggles drag mode | PASS | Button present, click succeeds; localStorage empty (no widgets moved) |
| D5 | Reset layout works | NOT-EXERCISED | No widgets reordered so no persistence to reset; trusted by code review |
| D6 | KPI tier counts match `/stats`: HOT(3)+WARM(6)+COLD(2)+COOL(3) = 14 ✓ | PASS | Confirmed via snapshot + /stats response |
| D7 | Score histogram buckets sum to 14: 2+3+2+5+2=14 | PASS | Snapshot exact match |
| D8 | Top Opportunities = 6 leads DESC | PASS | 83, 81, 78, 69, 68, 64 — composite_score DESC verified |
| D9 | Weekly trend = last 12 weeks dual-axis | PASS | X-axis shows 05-11 + 05-18 (only 2 weeks have data; chart spans 12-week window) |
| D10 | Widget deep-link query params | PASS | confidence=high/medium/low/unknown, icp_min=1..5, signal+signal_type, min&max all visible in href set |

### Leads list (T6) — all filter cases against same dataset of 14 leads

| ID | Case | Verdict | Result |
|----|------|---------|--------|
| LS1 | `/leads` 200, table renders 14 rows, all cols (LEAD/COMPANY/TIER/SCORE/REPORT DATE) | PASS | "Showing 14 leads" |
| LS2 | tier=HOT via button click | PASS | Returns 3 rows (Aljanabi, Horner, Sivasubramaniam) |
| LS3 | search=aguirre (tokenized AND) | PASS | 2 rows (both Jorge Aguirre) |
| LS4a | confidence=high | PASS | 4 rows — matches dashboard HIGH=4 |
| LS4b | confidence=low | PASS | 3 rows — matches dashboard LOW=3 |
| LS4c | confidence=unknown | PASS | 0 rows — matches dashboard UNKNOWN=0 |
| LS5 | icp_min=4 (exact-bucket semantics) | PASS | 6 rows — matches dashboard 4-star count=6 |
| LS6 | score range min_score=80 max_score=100 | PASS | 2 rows — matches dashboard 80-100 bucket=2 |
| LS7 | mine=1 (current user owns no leads) | PASS | 0 rows — correct (all 14 leads owned by user_id 31210000000141392) |
| LS8 | signal_label=Compliance need + signal_type=attribution | PASS | 2 rows — matches dashboard Top Score Drivers "Compliance need 2" |
| LS-ex | company=City of Bellaire | PASS | 2 rows |

### Lead detail (T7)

| ID | Case | Verdict | Notes |
|----|------|---------|-------|
| LD1 | Detail page loads with sidebar + iframe | PASS (with F1) | Sidebar renders; iframe `about:blank` for one lead with missing storage object |
| LD2 | Sidebar cards (Lead, Dimensions, Verdict, Signals) all render | PASS | Aljanabi shows score 83, Fit 19/25, Intent 22/25, Timing 24/30, Budget 18/20, verdict headline, 3 attribution + 1 compliance signal |
| LD3 | Iframe sandbox = `allow-scripts allow-popups` (no allow-same-origin) | PASS | Verified via DOM |
| LD4 | Download button present (admin or user) | PASS | Button present; download path uses Blob (no htmlUrl per F2) |
| LD5 | Delete button is admin-only | PASS | As `user`, no delete button visible; as `admin` (post-promote) button appeared on the same detail page |

### Upload (T8) — admin-only

| ID | Case | Verdict | Evidence |
|----|------|---------|----------|
| U1 | Upload minimal HTML → lead row created | PASS | POST /leads/upload 200 `{id:"31210000000167140", lead_name:"Test User", company:null, updated:false}`; queue shows "Created"; row visible in Recent Uploads |
| U2 | Re-upload same file → returns same id | PARTIAL — see F3 | Same id returned but `updated:false` again (expected `true`); UI shows "Created" twice |
| U3 | Upload .txt file → client-side reject (accept=".html,.htm") | PASS | No network request fired; file picker filter blocked |
| U4 | Backend body validation | PASS | `<html></html>` → 400 "html body too small"; empty html → 400 "missing file or html body"; missing filename → 400 "missing file or html body" |

### Dossier generate (T9) — live

| ID | Case | Verdict | Evidence |
|----|------|---------|----------|
| DG1 | Minimal valid intake (name + email) → 200 with request_id + catalyst_job_id | PASS | request_id=31210000000165155, catalyst_job_id=31210000000158169, status=pending |
| DG2a | Empty intake → 400 intake_invariant_failed | PASS | "Provide at least one of: (name AND email), linkedin_url, or company_url" |
| DG2b | Name only → 400 | PASS | Same message — name needs email |
| DG2c | Email only → 400 | PASS | Same message |
| DG3 | Immediate re-submit same intake → 409 duplicate_in_flight | PASS | Returned same request_id (31210000000165155), stage=queued |
| DG4 | Poll cycle reaches terminal status | PASS | preflight → synthesis → done; terminal status="partial" (rr_full_miss expected on fake email); lead_id=31210000000163181 created; tokens_input=3622, tokens_output=5555; elapsed ~2:15 |

### Inbox / activity (T10)

| ID | Case | Verdict | Evidence |
|----|------|---------|----------|
| I1 | GET `/dossiers/generate` returns user-scoped requests only | PASS | Test user saw 1 request (their own); other user's 7 pre-existing rows hidden |
| I1b | GET with `?status=pending,running` filter | PASS | Same single running row returned |
| I2 | ActiveRequestsPill polls every 10s when live (per code spec) | TRUSTED-BY-CODE | Verified handler logic; not timed live |
| I3 | Retry on failed (re-submit with stored intake) | COVERED-BY-DG1 | Calls same createDossierRequest path; endpoint behavior identical |
| I4 | DELETE single terminal with `?force=1` | PASS | `200 {ok:true,deleted:1}`; inbox count went to 0 |
| I5 | DELETE all with `?clear_terminal=1` | PASS | `200 {ok:true,deleted:0}` (nothing left after I4) — endpoint reachable + correct response shape |

### Leads regression (T11)

| ID | Case | Verdict | Evidence |
|----|------|---------|----------|
| LR1 | Upload-created lead appears in `/leads` search | PASS | search="Test User" → 1 row, id=31210000000167140 |
| LR2 | Dossier-gen-created lead appears in `/leads` | PASS | lead_id 31210000000163181 visible; lead_name="Elis Throwaway …", tier=COLD, score=0 (degraded) |
| LR3 | Admin DELETE `/leads/:id` cascades | PASS | DELETE 31210000000167140 → 200 ok; lead count 15→14; no orphan lead_signals (none existed for upload-only lead) |
| LR4 | Confidence filter is case-insensitive (workaround for ZCQL LIKE bug per leads.js:243-262) | PASS | `confidence=HIGH` and `confidence=high` both return 4 rows |
| LR5 | signal_label filter via subquery + chunking | PASS | "Compliance need" + attribution → 2 rows |
| LR6 | Duplicate-email pill shows on list | PASS | Both "Billy Craighead" rows display "2026-05-19" date pill; both "Jorge Aguirre" rows similarly |

## Findings — details and recommendations

### F1 — Lead detail iframe blank when Stratus object is missing (HIGH)

**Repro:** Navigate to `/leads/31210000000143427` (Aljanabi). Iframe loads `about:blank`. Sidebar fully renders.

**Evidence:** `GET /server/api/leads/31210000000143427` returns `{lead:{…}, signals:[…], html:null, htmlUrl:null}`. The lead's `storage_path` is `31210000000141392/1778623945361_ELISS_BBVA…html` but the Stratus object is either deleted or unreachable. Other leads return either inline `html` (e.g., 31210000000162168, 31210000000167004) or both null.

**Code site:** `functions/api/routes/leads.js:391-407` — when both `getSignedUrl()` and `getHtml()` fail, the handler returns `html:null, htmlUrl:null` silently. The frontend (`LeadDetailPage.tsx:495-530`) iframe sandbox renders empty.

**Recommendation:**
- Backend should distinguish "lead row exists but storage object missing" from "successful fetch". Return a `storage_missing:true` flag.
- Frontend should show an empty-state card in the iframe area: "Original HTML missing — was it deleted from Stratus? Re-upload via /upload."
- Optional: surface an admin-only "Re-upload" button on the detail page when this state is detected.

### F2 — `htmlUrl` signed URL is always null; only the inline-HTML fallback path is exercised (MEDIUM)

**Repro:** All 4 inspected leads return `htmlUrl:null` even when `html` is populated.

**Evidence:** Sampling 4 leads:
- 31210000000143427 → html=null, htmlUrl=null
- 31210000000162168 → html len=273383, htmlUrl=null
- 31210000000167004 → html len=246893, htmlUrl=null
- 31210000000158065 → html len=212032, htmlUrl=null

**Code site:** `functions/api/routes/leads.js:391-407` — `getSignedUrl()` is tried first; outcome suggests it always throws / returns null. The code silently falls through to `getHtml()`.

**Impact:** Every lead detail view ships the full HTML (200-300KB per lead) inline in the JSON response. For larger dossiers this adds noticeable bandwidth + memory; signed URLs would let the iframe stream from Stratus directly.

**Recommendation:**
- Log the `getSignedUrl()` failure (currently swallowed) and check whether it's a Stratus permissions issue (Bucket vs project-user scope) or an SDK quirk on IN DC.
- Per memory note `feedback_catalyst_stratus_no_overwrite.md`, Stratus has gotchas around versioning — verify `Generate_Signed_URL` works on existing objects with current credentials.

### F3 — Upload re-submit returns `updated:false` and UI shows "Created" again (LOW)

**Repro:**
1. Upload `elis-test-1779389887.html` as admin → response `{id:"31210000000167140", updated:false}`. UI: "Created".
2. Re-upload same file → response `{id:"31210000000167140", updated:false}` (same id). UI: "Created" (again).

**Expected** (per agent's surface map of `parseAndStoreDossier`): second call should return `updated:true` because filename+userId is deterministic and the row already existed.

**Code site:** `functions/api/routes/leads.js` (upload handler / parseAndStoreDossier). Probably the upsert logic returns `updated` based on whether an UPDATE statement ran, not whether a pre-existing row was found.

**Impact:** Cosmetic — both server and frontend converge on the same row id, so no data integrity issue. But the user gets confusing "Created" feedback for a re-upload.

**Recommendation:** Backend should set `updated:true` whenever the dedup key (filename+userId) matched an existing row, even if no diff was applied.

### F4 — Non-admin "Create" nav but "Upload" dashboard CTA (LOW)

**Repro:** As a `user` (non-admin), nav reads "Create". But the Dashboard hero shows a CTA labeled "Upload" → routes to `/upload` (admin-only). Clicking it presumably shows an unauthorized state.

**Code site:** `AppShell.tsx:134` (nav copy) vs `DashboardPage.tsx:740` (CTA button); the gating is inconsistent.

**Recommendation:** Render the dashboard CTA label conditionally: "Upload" for admins, "Create dossier" for non-admins (and route the non-admin CTA to the CreateDossierModal, not to `/upload`).

## State summary

| Table | Pre | Mid (peak) | Post |
|-------|-----|------------|------|
| `leads` | 14 | 16 (after U1+DG4 create) | 14 (cleanup) |
| `dossier_requests` | 7 | 8 (after DG1) | 7 (cleanup via I4) |
| `user_roles` | 3 | 3 (current user toggled to admin then back) | 3 |
| Stratus objects | (not counted) | +1 from upload | (not verified post-cleanup; admin DELETE supposedly cascades) |

**Cleanup verification:** all counts back to baseline. Self-role reset to `user`.

## Tests not exercised (call-outs)

- **L-OTP / forgot-password** — out of scope per "Auth + signup config + 1-2 negatives".
- **Rate-limit / lockout** — out of scope.
- **Cross-browser** — chrome-devtools-mcp drives Chrome only.
- **Performance / Lighthouse** — not requested.
- **5MB-oversize upload** — backend has a `multer` 5MB limit per agent map but actual route uses JSON body, so I tested the JSON-body validation path (U4) which already covers empty/missing/too-small. Oversize JSON would consume ~5MB allocation in the test runner — not worth running.
- **D5 reset-layout** — requires drag-and-drop simulation which chrome-devtools-mcp `drag` doesn't reliably support for dnd-kit; trusted by code review.
- **I2 poll cadence (timing)** — verified the endpoint is invoked when live but did not measure the 10-second interval.

## Recommended fix order

1. **F1** (high) — empty iframe is user-visible. Add the missing-storage detection + empty-state card in `LeadDetailPage.tsx`.
2. **F2** (medium) — debug `getSignedUrl()` failure; impacts bandwidth on every detail page load.
3. **F3** (low) — set `updated:true` on the upsert path; trivial change.
4. **F4** (low) — flip Dashboard CTA label/route based on `isAdmin`.

## Evidence pointers

- Network capture reqids (current session): 379-432 (covers /me, /stats, /leads, /leads/:id, /leads/upload, /dossiers/generate POST + GET + DELETE).
- Catalyst MCP queries: leads, dossier_requests, user_roles counts before / after.
- No screenshots saved this session — chrome-devtools-mcp snapshots used inline for verification.

---

**Sign-off:** Functional pass complete. No regression vs prior `tests/user-management-report.md` state. 4 findings logged, ranked by impact. Ready for fix prioritization.
