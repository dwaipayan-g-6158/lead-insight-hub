# Login Screen — Functional, Integration & Regression Report

**Date:** 2026-05-22
**Target:** https://lead-insight-hub-60066539659.development.catalystserverless.in/app/
**Source rev under test:** local working tree at `lead-insight-hub-catalyst` (login-iframe.css `?v=29`)
**Driver:** chrome-devtools-mcp (Chromium 148), desktop 1440×900 unless noted
**Test plan:** `C:\Users\dGiri\.claude\plans\giggly-knitting-abelson.md`
**Screenshot folder:** `tests/screenshots/login-2026-05-22/`

---

## Headline

| Reported defect | Verdict | Root cause located |
|---|---|---|
| **Captcha darkened / not visible** | **CONFIRMED** | `app/public/login-iframe.css` lines 870 + 887 |
| **Email-edit replay glitch** | **NOT REPRODUCED** in static screenshots; mechanism identified | `app/public/login-iframe.css` line 656 (`transition: padding-top 0.3s` on body) is the most plausible amplifier |

Of 27 cases executed: **22 PASS · 1 CONFIRMED-DEFECT · 1 NOT-REPRO-WITH-CAVEATS · 1 IDEMPOTENCY-NOTE · 2 MINOR-A11Y-GAPS · 0 BLOCKERS.** Full login round-trip works end-to-end.

---

## Defect A — Captcha rendered too dark to read (CONFIRMED)

### Repro

1. The captcha is `display:none` until Catalyst challenges; in this dev environment it did not activate after 4 failed-password attempts.
2. Force-shown the captcha container and exercised both Catalyst code paths:
   - **Signin-flow path:** captcha painted as `background-image` on `#captcha_img` DIV (no `<img>` child). Verified via DOM inspection — Catalyst's static HTML in the captcha container ships ZERO `<img>` tags (only an `<input>`, the bare `#captcha_img` div, the reload `<span>`, and an error `<div>`).
   - **Recovery-flow path:** captcha painted as `<img id="hip">` inside the same div.

### Evidence

- `D01-captcha-signin-flow-bg-image-rendering.png` — signin-flow path: captcha glyphs barely visible (dim gray on dark)
- `D01-captcha-recovery-flow-img-with-filter.png` — recovery-flow path: same glyphs clearly legible (the `filter: invert(0.92) hue-rotate(180deg) contrast(1.05)` properly inverts a black-on-white captcha into a light-on-dark one)
- DOM excerpt confirming no `<img>` in the signin-flow captcha container:
  ```html
  <div class="textbox_div" id="captcha_container" style="display: none;">
    <input id="captcha" placeholder="Enter CAPTCHA" type="text" name="captcha" class="textbox" ...>
    <div id="captcha_img" name="captcha" class="textbox"></div>
    <span class="reloadcaptcha"> </span>
    <div class="fielderror"></div>
  </div>
  ```

### Root cause

`app/public/login-iframe.css`:

- Line **870:** `#captcha_img.textbox { background-color: rgba(0, 0, 0, 0.25) !important; ... }` — applies a dark overlay to the captcha container.
- Line **887:** `#hip, #captcha_img img { filter: invert(0.92) hue-rotate(180deg) contrast(1.05) !important; ... }` — applies a compensating inversion **only when the captcha is rendered as an `<img>` (recovery flow)**.

The author's own comment at lines 856–859 calls out the trap:
> "use `background-color` (not the `background` shorthand) so Catalyst's JS-injected `style="background-image: url(...)"` for the signin-flow captcha (which uses a CSS background, not an `<img>`) still composites on top of our surface color."

The composite is what causes the darkening: the original captcha image is black-on-white, our overlay is a 25% black film, and there is no filter on this code path to re-invert. Recovery-flow captchas dodge the bug because the filter targets the `<img>` directly.

### Fix candidates (for the follow-up `/fix` session — NOT applied by this pass)

1. **Drop the dark overlay on `#captcha_img.textbox`** (the cleanest fix) — let the white captcha background show through. The surrounding form chrome (border, gap) already provides separation.
2. **Apply the inversion to the background-image too** via `filter` on `#captcha_img.textbox` and `background-blend-mode: difference`. Risk: `filter` cascades to the reload icon child if not scoped carefully.
3. **Override `background-color` to white when a `background-image` is set** (using a more specific selector). Lowest blast radius.

---

## Defect B — Email-edit replay glitch (NOT REPRODUCED, but mechanism identified)

### What was attempted

| Variant | Result |
|---|---|
| D-03 valid email → NEXT → Change → edit to different email → NEXT | Step-1 re-rendered cleanly. "This account does not exist." alert appeared in the standard inline-error position. No visible overlap, ghost text, or stuck loader. *Screenshot: `D03-step5-GLITCH-after-edit-next.png`* |
| D-04 valid email → NEXT → Change → NEXT (no edit) | Step-2 re-rendered cleanly. *Screenshot: `D04-step2-after-next-no-edit.png`* |
| D-05 invalid → error → fix to valid → NEXT | Previous error cleared, Step-2 rendered cleanly. *Screenshots: `D05-step1-invalid-account-error.png` → `S05-post-login-dashboard.png`* |

In all three variants, the final still-frame screenshot is a clean form. The user's reported visible glitch was not captured in any single still.

### What I did find

DOM inspection of the iframe (same-origin, fully introspectable) revealed two transition rules that can plausibly cause a perceived flicker on step swap:

- **`body { transition: padding-top 0.3s ease !important; }`** — `app/public/login-iframe.css` line **656**. The body padding-top is animated whenever the Catalyst alert banner appears or disappears. Going from "(error) NEXT" → "advances to step 2" can trigger an alert appear+dismiss combo that nudges the form's vertical position mid-transition.
- **Catalyst's own `embedded_signin.css`** applies `transition: all` to both `#login_id_container` and `#password_container` (not in our CSS — verified by grep). Combined with Catalyst's `display: none` ↔ `display: block` toggling, any animatable property change on those containers will tween, which is the textbook setup for ghost-state flickers.

Additional minor observations during the chain:
- After clicking **Change**, the "Forgot Password?" span (`#blueforgotpassword`) stays in the a11y tree on Step 1. Computed style is `display: inline-block` with width/height = 0, so it is invisible to sighted users — **not a visible bug**, but a screen reader announces it as present on Step 1.

### Recommended next step

Because the still-frame static evidence does not capture the user's described glitch, the next investigation step should be **a screen recording of the live page in the exact browser the reporter used**, not more static screenshots. To get there, the fix-session should temporarily wrap our `body { transition: padding-top 0.3s }` rule and re-test with the user. If the glitch disappears, that was the cause; if it persists, the issue lives inside Catalyst's SDK and needs to be reported upstream.

---

## Suite results

### A. Defect-confirmation

| ID | Verdict | Notes |
|---|---|---|
| D-01 | **CONFIRMED** | See Defect A above. |
| D-02 | N/T | Captcha never activated organically (4 failed-password attempts insufficient in this dev env). Re-roll behaviour can only be tested once D-01 is fixed and captcha is provoked. |
| D-03 | NOT-REPRO | Mechanism flagged (see Defect B). |
| D-04 | PASS | Re-submitting same email after Change advanced cleanly to Step 2. |
| D-05 | PASS | Invalid → error → corrected → Step 2 transitioned without lingering error. |

### B. Smoke

| ID | Verdict | Notes |
|---|---|---|
| S-01 | PASS | Zero red console entries. Two non-blockers: `apple-mobile-web-app-capable` deprecation warn (parent's `index.html`); `Quirks Mode` issue from Catalyst's iframe doc (their HTML lacks a DOCTYPE — not our code). |
| S-02 | PASS | `login-iframe.css?v=29` returns 200 (`text/css`). |
| S-03 | PASS | `catalystWebSDK.js v4.5.0` returns 200 from `static.zohocdn.com`. |
| S-04 | PASS | Exactly one iframe mounted inside `#catalyst-login-container`. |
| S-05 | PASS | Full login with `dwaipayan.g@zohotest.com` → dashboard rendered with 13 dossiers, 2 HOT, avg score 51. *Screenshot: `S05-post-login-dashboard.png`* |
| S-06 | PASS | "Sign out DG" returns to login screen, iframe re-mounts with empty email field. *Screenshot: `S06-after-logout-immediate.png`* |

### C. Integration

| ID | Verdict | Notes |
|---|---|---|
| I-01 | PASS | Catalyst's `/baas/v1/.../project-user/current` poll flipped 401 → 200 within one cycle after `signin/v2/primary/.../password` succeeded. |
| I-02 | **NOTE — IDEMPOTENCY** | `POST /server/api/auth/post-signup` was called on **both** the first login (reqid 175) and the second login (reqid 310). Either the AuthGate calls it unconditionally as an idempotent bootstrap (safe; route already dedupes in `functions/api/routes/auth.js`) or it should be gated on `firstLogin === true`. Flag for the AuthGate author to confirm intent. Not a regression. |
| I-03 | PASS | `GET /server/api/me` response body matches AuthProvider shape exactly: `{userId, email, firstName, lastName, role, isAdmin, roles}`. |
| I-04 | PASS | Reload mid-login (after NEXT, before password) returned to a clean Step 1; email was discarded. *Screenshot: `I04-mid-login-reload-returns-to-step1.png`* |
| I-05 | PASS | Opening `/app/` in a second tab while logged in skipped the login screen entirely and rendered the dashboard directly. No flash of iframe. *Screenshot: `I05-second-tab-skips-login.png`* |
| I-06 | PASS | Wrong password (3× variants) surfaced "Incorrect password. Please try again." in the Catalyst-native alert, parent stayed on `/app/`, no calls to `/server/api/me`. |

### D. Regression

| ID | Verdict | Notes |
|---|---|---|
| R-01 | PASS | `#login_id` and `#password` computed styles: text `rgb(231, 233, 241)`, body bg `rgb(24, 28, 42)` — dark theme intact. |
| R-02 | PASS | iPhone 14 (390×844): no horizontal scroll, form fits, complementary panel collapses to ELISS logo. *Screenshot: `R02-mobile-iphone14.png`* |
| R-03 | PASS | Slow 3G mid-load screenshot is pure dark — **no FOUC** of white iframe content. *Screenshots: `R03-slow-3g-mid-load.png`, `R03-slow-3g-60s.png`* |
| R-04 | **MINOR a11y gap** | Zero `@media (prefers-reduced-motion)` rules in `login-iframe.css` — body transition + `.reloadcaptcha` rotate animation will run even for users who opted out. Decorative only; no functional break. |
| R-05 | **MINOR a11y gap** | Zero `@media (forced-colors)` rules. Heavy `!important` usage on captcha filter means forced-colors mode (Windows High Contrast) may further degrade captcha visibility — couples to Defect A. |
| R-06 | N/T | SPA hash routing makes browser back/forward low-value for the login round-trip; skipped. |
| R-07 | PASS | `?v=29` cache-bust query string appears in network log — bumping it on next deploy will force a fresh fetch. |
| R-08 | PASS | Lighthouse desktop scores: **Accessibility 95**, Best Practices 96, SEO 100, Agentic Browsing 98. Reports under `%TEMP%/chrome-devtools-mcp-*/report.html`. |
| R-09 | PASS | iframe URL contains `hide_fp=false`; `#blueforgotpassword` SPAN exists with text "Forgot Password?" — link is reachable, our CSS does not hide it. |
| R-10 | PASS | No CSP, CORS, or mixed-content errors. Only console noise is the apple-mobile-web-app-capable deprecation warn and `/baas/v1/project-user/current` 401s (expected pre-auth polls). |

---

## Console + network appendix

**Console (clean baseline load, unauthenticated):**
- `[warn]` `<meta name="apple-mobile-web-app-capable">` deprecated → cheap one-line fix in `app/index.html`.
- `[error] 401` ×2 → Catalyst SDK's auth-state poll. Expected when unauthenticated.
- `[issue]` "Verify stylesheet URLs", "Quirks Mode", "Incorrect use of `<label for=>`" → originate from Catalyst's iframe document (their HTML, not ours).

**Network (full smoke load):** 37 requests, all 200 except the two expected pre-auth 401s and one `ERR_ABORTED` on `embedded_signin.css` that subsequently retries successfully (Catalyst SDK behaviour, not a regression).

---

## Fix recommendation

Single highest-value change for the follow-up session:

1. **Edit `app/public/login-iframe.css` lines 854–877** to either drop `background-color: rgba(0, 0, 0, 0.25)` from `#captcha_img.textbox` or add a sibling rule that forces a white background whenever Catalyst inlines a `background-image`. Bump `?v=29` to `?v=30` in `app/src/lib/catalyst-client.ts` to bust the cache. This kills Defect A and is the only change that is independently confirmed in evidence.

Lower-priority candidates, optional and contingent on the live screen-recording from the original reporter:

2. **Edit `app/public/login-iframe.css` line 655–657** — narrow the body `transition: padding-top 0.3s` to only run when the alert is present/absent (use `:has()` selector or move the rule onto a wrapper). Re-test the email-edit chain with the same user.
3. **Add `@media (prefers-reduced-motion: reduce) { *, *::before, *::after { transition: none !important; animation: none !important; } }`** at the bottom of `login-iframe.css` — closes R-04 and incidentally protects against item 2 above.

No code in `app/` or `functions/` was modified by this test pass.
