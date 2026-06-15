import { useEffect, useRef, type ReactNode } from "react";
import { useRouter, useRouterState } from "@tanstack/react-router";
import { useAuth } from "@/lib/auth";
import { Heart, LogIn, Lock, Network, Radar, Sparkles, Zap } from "lucide-react";
import { SignUpPage } from "@/components/SignUpPage";

const CATALYST_LOGIN_ID = "catalyst-login-container";
// Minimum iframe height: reserves space for Catalyst's typical email-
// step form so the shell doesn't visually jump from a short box to the
// real content. Real content is normally ≥520 px (email step ~340,
// password+alert ~480, OTP-with-banner ~520). 520 keeps a stable
// visual footprint and the ResizeObserver shrinks it down to a tighter
// height after the first measure when appropriate. Previously this was
// 200 — caused a visible expand-jump after sign-out / cold-load.
const IFRAME_MIN_HEIGHT = 520;

// Subtle SVG grid as data URI — used as a low-opacity texture overlay.
const GRID_BG =
  "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='40' height='40' viewBox='0 0 40 40'><path d='M40 0H0V40' stroke='%239aa0b8' stroke-width='0.5' fill='none'/></svg>\")";

export function AuthGate({ children }: { children: ReactNode }) {
  const { user, loading, roleLoading } = useAuth();
  // Hash-based router means `/signup` ↔ URL `#/signup`. useRouterState
  // is reactive — clicking the Sign up link or signing back in updates
  // pathname and triggers a re-render.
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const isSignupRoute = pathname === "/signup";

  // /signup is a public page — render it regardless of auth state,
  // bypassing both the loading shell and LoginScreen. The route file at
  // app/src/routes/signup.tsx exists for the router but we never need
  // its <Outlet> path (AppShell + children) because the page is full-bleed.
  if (isSignupRoute) {
    return <SignUpPage />;
  }

  // Loading state: render an empty branded canvas instead of a centered
  // spinner. Reason — after signOut() the page does a full reload; the
  // first paint is loading=true, which used to show a spinner, then
  // ~50-500ms later the SDK confirms "no user" and we swap to the
  // LoginScreen. The user perceives that swap as a "flicker". A blank
  // background-colored shell during loading transitions cleanly into
  // either the LoginScreen or the authenticated children without any
  // visible icon shifting. The Catalyst iframe's own internal loader
  // (after LoginScreen mounts) takes over within ~100 ms so users
  // still see *something* moving.
  if (loading) {
    return <div aria-hidden className="min-h-screen bg-background" />;
  }
  if (!user) return <LoginScreen />;
  // Hold the same blank canvas while the role resolves — otherwise
  // children mount with isAdmin=false (the initial state) and admins
  // see a ~200-500ms flash of the non-admin "Create lead" UI before
  // getMyProfile() returns and re-renders into the admin "Upload" UI.
  if (roleLoading) {
    return <div aria-hidden className="min-h-screen bg-background" />;
  }
  return <>{children}</>;
}

function LoginScreen() {
  const { renderLoginInto } = useAuth();
  const router = useRouter();
  const logoSrc = `${import.meta.env.BASE_URL}logo.svg`;
  const slotRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const t = setTimeout(() => {
      void renderLoginInto(CATALYST_LOGIN_ID);
    }, 50);
    return () => clearTimeout(t);
  }, [renderLoginInto]);

  // Dynamic iframe height — the Catalyst sign-in iframe ships intrinsically
  // sized for ~520 px, but its content varies per step (email ≈ 280, password
  // ≈ 330, OTP-with-banner ≈ 380, MFA/captcha can spike higher). Without
  // this, a fixed-height parent either clips the bottom buttons or leaves a
  // gap. We measure the inner #signin_flow column and resize the iframe
  // shell to match, observed via ResizeObserver so step changes track live.
  useEffect(() => {
    const slot = slotRef.current;
    if (!slot) return;

    let resizeObs: ResizeObserver | null = null;
    let innerMut: MutationObserver | null = null;
    let alertMsgObs: MutationObserver | null = null;
    let srcObs: MutationObserver | null = null;
    let alertDismissTimer = 0;
    let pollHandle = 0;
    let attachedIframe: HTMLIFrameElement | null = null;

    // Track whether the iframe has ever been measured with real content.
    // We skip the height transition on the very first sizing (the IFRAME_MIN_HEIGHT
    // floor → first real measure) to avoid a jarring grow-from-200px on mount.
    // After that, every subsequent height change animates smoothly.
    let firstMeasureApplied = false;
    const apply = (iframe: HTMLIFrameElement, h: number) => {
      // Before the first real measurement, clamp to IFRAME_MIN_HEIGHT so the
      // shell doesn't paint a tiny box that then grows. AFTER the first
      // measurement, trust the measured height — Catalyst's email step is
      // only ~280 px and forcing it to 520 leaves a visible dead zone inside
      // the card on iPhone (390×844). The transition setup below animates
      // the shrink smoothly.
      const measured = Math.ceil(h);
      const next = `${firstMeasureApplied ? measured : Math.max(measured, IFRAME_MIN_HEIGHT)}px`;
      if (iframe.style.height === next) return;
      if (!firstMeasureApplied) {
        firstMeasureApplied = true;
        // Release the slot's anti-flicker `min-height` now that the iframe
        // is measured — without this the slot stays pinned at 536 px even
        // when the iframe shrinks to ~200 px (email step), leaving a big
        // dead zone inside the card on mobile. Slot transitions smoothly
        // via the `transition-[min-height]` utility on the slot div.
        slot.style.minHeight = "0px";
      } else if (!iframe.style.transition) {
        iframe.style.setProperty(
          "transition",
          "height 0.28s cubic-bezier(0.4, 0, 0.2, 1)",
          "important",
        );
      }
      iframe.style.setProperty("height", next, "important");
    };

    const attach = (iframe: HTMLIFrameElement) => {
      // Same iframe re-presented (e.g., MutationObserver re-fired without
      // a replacement) → skip. A new iframe element means re-attach.
      if (attachedIframe === iframe) return;
      attachedIframe = iframe;

      // Re-inject our login theme CSS into whatever doc lives in the iframe.
      // The /signin endpoint accepts our css_url SDK param, but Catalyst
      // navigates the same iframe to /accounts/p/<zaid>/password for
      // "Forgot Password?" — and that page hard-codes Catalyst's own
      // light-theme reset CSS. Same-origin lets us reliably append a
      // <link> to its <head>. Idempotent via [data-liw-theme="1"].
      const injectThemeCss = () => {
        const liveDoc = iframe.contentDocument;
        if (!liveDoc?.head) return;
        if (liveDoc.querySelector('link[data-liw-theme="1"]')) return;
        const link = liveDoc.createElement("link");
        link.rel = "stylesheet";
        link.href = `${window.location.origin}/app/login-iframe.css?v=35`;
        link.setAttribute("data-liw-theme", "1");
        liveDoc.head.appendChild(link);
      };

      // Re-wire on every load. The Catalyst SDK first injects the iframe
      // pointing at about:blank (readyState=complete instantly, but no
      // #signin_flow), then navigates it to the real /accounts/p/.../signin
      // URL — that second load fires a fresh `load` event we must catch.
      const wireUp = () => {
        const doc = iframe.contentDocument;
        if (!doc) return;
        injectThemeCss();
        // Soft fade-in for the doc body so cross-iframe navigation
        // (signin → forgot-password → back) reads as a transition
        // rather than a flash of unstyled content.
        //
        // Opacity-ONLY — deliberately no transform. A sub-pixel transform
        // animation (the old translateY(2px)→0 slide) re-rasterizes every
        // 1px hairline each frame, which shimmered the input/divider borders
        // and the primary button edges during the Forgot-Password navigation
        // (the reported "flickering straight line / button edges"). Opacity
        // fades cleanly without touching the raster grid. As a bonus, body
        // now keeps `transform: none` permanently, so it never becomes the
        // containing block for the position:fixed .Alert banner — which is
        // why the old 360ms transform-cleanup timer is gone.
        if (doc.body) {
          doc.body.style.opacity = "0";
          doc.body.style.transition =
            "opacity 0.28s cubic-bezier(0.16, 0.84, 0.32, 1)";
          requestAnimationFrame(() => {
            if (doc.body) doc.body.style.opacity = "1";
          });
        }
        if (pollHandle) {
          clearTimeout(pollHandle);
          pollHandle = 0;
        }
        resizeObs?.disconnect();

        // Measure the bottom edge of the visible primary action button
        // (NEXT / SIGN IN / VERIFY) plus a small breathing pad. We can't
        // use body.scrollHeight here because Catalyst's signin page keeps
        // a tail of hidden / off-state form rows (password textbox_div,
        // forgot-password row, federated chrome) that live inside the
        // form pane and inflate body height even when their parents are
        // zeroheight or display:none. Anchoring on the rendered button
        // gives an iframe that is exactly the height of the form the
        // user is on — anything below is clipped by the iframe boundary,
        // hiding the orphan rows automatically.
        const PAD = 16;
        // Coalesce repeated measure() calls into a single rAF tick so a
        // burst of Catalyst DOM mutations (each one would otherwise
        // synchronously read geometry, forcing layout) collapses into
        // one read + one write per frame. Cuts the ~100 ms forced
        // reflow window flagged in the Lighthouse perf trace.
        let measurePending = false;
        const measure = () => {
          if (measurePending) return;
          measurePending = true;
          const rafWin = iframe.contentWindow ?? (window as Window);
          rafWin.requestAnimationFrame(() => {
            measurePending = false;
            const liveDoc = iframe.contentDocument;
            if (!liveDoc) return;
            let bottom = 0;
            // Body-relative scroll offset — `getBoundingClientRect()` returns
            // viewport-relative coords, which subtract `body.scrollTop`. When
            // Catalyst auto-scrolls body during step transitions (e.g. the
            // Change→edit→NEXT replay on the signin step), the button's BCR
            // bottom shrinks → iframe shrinks → Catalyst scrolls further to
            // keep the button visible → iframe shrinks more. That feedback
            // loop was leaving the iframe at ~196 px instead of ~480, and
            // overflow:hidden was clipping the .hellouser email row above
            // the password input (user-reported glitch 2026-05-22).
            const scrollOffset = liveDoc.body.scrollTop;
            const buttons = liveDoc.querySelectorAll<HTMLElement>(
              "button.btn, input.btn, #nextbtn, .btn.blue",
            );
            buttons.forEach((b) => {
              const r = b.getBoundingClientRect();
              // Skip off-state buttons: zero-sized, hidden ancestors, or
              // sitting at y<=0 (Catalyst's templates park inactive panes
              // at negative offsets or with width=0 borders).
              if (r.width < 40 || r.height < 20) return;
              if (b.offsetParent === null) return;
              const bodyRelBottom = r.bottom + scrollOffset;
              if (bodyRelBottom > bottom) bottom = bodyRelBottom;
            });
            if (bottom > 0) {
              apply(iframe, bottom + PAD);
            } else {
              // Fallback before any button is in the DOM (still booting).
              apply(iframe, IFRAME_MIN_HEIGHT);
            }
          });
        };

        const waitForFlow = () => {
          const liveDoc = iframe.contentDocument;
          if (!liveDoc) return;
          // signin page → #signin_flow ; password-reset page → #recovery_flow.
          // measure() finds any visible primary button below, so either
          // structural shell works as the ResizeObserver target.
          const flow =
            liveDoc.getElementById("signin_flow") ??
            liveDoc.getElementById("recovery_flow");
          if (!flow) {
            pollHandle = window.setTimeout(waitForFlow, 60);
            return;
          }
          measure();
          resizeObs?.disconnect();
          resizeObs = new ResizeObserver(measure);
          resizeObs.observe(flow);
          resizeObs.observe(liveDoc.body);

          // Catalyst's #signin_flow has min-height:520, so its own
          // bounding rect never changes between steps — the swap is
          // expressed only as display:block↔none on sub-containers
          // (#login / #otp_container / #emailverify_container / etc.).
          // ResizeObserver doesn't fire on display toggles, so observe
          // those mutations directly. We schedule the re-measure via
          // rAF to batch successive Catalyst DOM writes into a single
          // iframe resize.
          innerMut?.disconnect();
          let scheduled = false;
          innerMut = new MutationObserver(() => {
            if (scheduled) return;
            scheduled = true;
            const rafWin =
              iframe.contentWindow ?? (window as Window);
            rafWin.requestAnimationFrame(() => {
              scheduled = false;
              measure();
            });
          });
          innerMut.observe(flow, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ["style", "class", "hidden"],
          });
          // The .Alert banner is a body-level sibling of #signin_flow,
          // so the subtree observer above misses it appearing /
          // disappearing. Watch body too — the rAF batching above
          // coalesces both into a single re-measure tick.
          innerMut.observe(liveDoc.body, {
            childList: true,
            subtree: false,
            attributes: true,
            attributeFilter: ["style", "class"],
          });

          // Auto-dismiss the banner 4 s after Catalyst writes a message
          // into .alert_message. We drive the fade-out by toggling a
          // `.liw-alert-dismissed` class — the CSS transition on .Alert
          // animates opacity + max-height back to 0, and the iframe
          // ResizeObserver shrinks the iframe to match. Class-based
          // dismissal restarts cleanly on every fresh message (Resend
          // OTP, rate-limit error, captcha), unlike CSS animation chains
          // which need a complex reflow toggle to re-fire.
          alertMsgObs?.disconnect();
          if (alertDismissTimer) {
            clearTimeout(alertDismissTimer);
            alertDismissTimer = 0;
          }
          const alertEl = liveDoc.querySelector<HTMLElement>(".Alert");
          const alertMsg = liveDoc.querySelector<HTMLElement>(
            ".Alert .alert_message",
          );
          if (alertEl && alertMsg) {
            const scheduleDismiss = () => {
              if (!alertMsg.textContent?.trim()) return;
              alertEl.classList.remove("liw-alert-dismissed");
              // Re-measure on banner appear too — body's :has() rule adds
              // 76 px padding-top which shifts the visible button down.
              // ResizeObserver doesn't catch the padding change because
              // body has height:100% locked to the iframe, so we trigger
              // measure explicitly on a microtask.
              requestAnimationFrame(measure);
              if (alertDismissTimer) clearTimeout(alertDismissTimer);
              alertDismissTimer = window.setTimeout(() => {
                alertEl.classList.add("liw-alert-dismissed");
                alertDismissTimer = 0;
                // After the CSS transition completes (~300 ms) the body
                // padding-top has fully collapsed back to 0 and the form
                // has shifted up. Re-measure so the iframe + parent card
                // shrink back to their compact size.
                setTimeout(measure, 350);
              }, 4000);
            };
            // Initial check — Catalyst may have already written content
            // by the time the iframe page finished loading.
            scheduleDismiss();
            alertMsgObs = new MutationObserver(scheduleDismiss);
            alertMsgObs.observe(alertMsg, {
              childList: true,
              characterData: true,
              subtree: true,
            });
          }
        };
        waitForFlow();
      };

      iframe.addEventListener("load", wireUp);
      // Belt-and-braces: also watch the iframe element itself for `src`
      // attribute changes. Catalyst's "Forgot Password?" handler navigates
      // the iframe via window.location.assign on the inner document — the
      // `load` event fires reliably in our tests but the in-doc CSS-link
      // injection from the previous `load` round can race with Catalyst's
      // own head rewrites. Triggering wireUp again on src mutation
      // guarantees our theme link survives those rewrites.
      srcObs?.disconnect();
      srcObs = new MutationObserver(() => {
        // Defer to the next macrotask so the new doc has parsed at least
        // its head; injectThemeCss handles head readiness itself.
        setTimeout(wireUp, 0);
      });
      srcObs.observe(iframe, {
        attributes: true,
        attributeFilter: ["src"],
      });
      // Apply a sane initial height immediately so the slot reserves space
      // before any Catalyst content paints.
      apply(iframe, IFRAME_MIN_HEIGHT);
      if (iframe.contentDocument?.readyState === "complete") wireUp();
    };

    // Catalyst SDK injects the iframe asynchronously; watch the slot until
    // it appears, then attach observers.
    const existing = slot.querySelector("iframe");
    if (existing) attach(existing as HTMLIFrameElement);

    const mut = new MutationObserver(() => {
      const ifr = slot.querySelector("iframe");
      if (ifr) attach(ifr as HTMLIFrameElement);
    });
    mut.observe(slot, { childList: true, subtree: true });

    return () => {
      mut.disconnect();
      innerMut?.disconnect();
      alertMsgObs?.disconnect();
      srcObs?.disconnect();
      resizeObs?.disconnect();
      if (pollHandle) clearTimeout(pollHandle);
      if (alertDismissTimer) clearTimeout(alertDismissTimer);
    };
  }, []);

  return (
    // min-h-[100svh] + min-h-[100dvh] is the iOS-Safari-aware dynamic
    // viewport pattern: svh is the static fallback (Safari < 15.4) so
    // there's never a 0-height moment, dvh tracks URL-bar collapse so
    // the layout doesn't snap when Safari's chrome animates in/out.
    // `relative` (instead of `fixed inset-0`) lets the document grow
    // naturally and keeps scroll position predictable on iPhone.
    <div className="relative min-h-[100svh] min-h-[100dvh] w-full overflow-x-hidden bg-background text-foreground">
      {/* Ambient backdrop: radial glow + low-opacity grid */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(124,111,240,0.18),transparent_55%)]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 bottom-0 h-1/2 bg-[radial-gradient(ellipse_at_bottom,rgba(99,102,241,0.08),transparent_60%)]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.04]"
        style={{ backgroundImage: GRID_BG }}
      />

      <div className="relative z-10 grid min-h-[100svh] min-h-[100dvh] w-full lg:grid-cols-[1.05fr_1fr]">
        {/* LEFT — brand panel (lg+ only) */}
        <aside className="hidden lg:flex flex-col justify-between border-r border-border/60 p-10 xl:p-14">
          <div className="flex items-center gap-3">
            <img src={logoSrc} alt="ELISS Logo" width={40} height={40} className="h-10 w-auto brand-breathe" />
            <div className="flex flex-col leading-none">
              <span className="text-[10px] font-semibold uppercase tracking-[0.34em] text-primary">
                ELISS
              </span>
              <span className="mt-1 text-[10px] uppercase tracking-[0.22em] text-muted-foreground/70">
                Enterprise Edition
              </span>
            </div>
          </div>

          <div className="max-w-md">
            <h1 className="text-3xl font-semibold leading-[1.12] tracking-tight xl:text-[2.5rem]">
              Lead Intelligence,
              <br />
              engineered for revenue teams.
            </h1>
            <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
              Search, score, and act on every B2B lead — collective sales
              intelligence in a single dossier-first workspace.
            </p>

            <ul className="mt-8 space-y-3 text-sm feature-stagger">
              <li className="feature-item flex items-start gap-3 text-foreground/85">
                <span className="mt-0.5 inline-grid h-7 w-7 place-items-center rounded-md border border-border/60 bg-card/50 text-primary">
                  <Sparkles className="h-3.5 w-3.5" />
                </span>
                <div>
                  <div className="font-medium text-foreground">
                    Auto-parsed dossiers
                  </div>
                  <div className="text-xs text-muted-foreground">
                    ELISS HTML reports turned into structured scores in seconds.
                  </div>
                </div>
              </li>
              <li className="feature-item flex items-start gap-3 text-foreground/85">
                <span className="mt-0.5 inline-grid h-7 w-7 place-items-center rounded-md border border-border/60 bg-card/50 text-primary">
                  <Zap className="h-3.5 w-3.5" />
                </span>
                <div>
                  <div className="font-medium text-foreground">
                    Fit · Intent · Timing · Budget
                  </div>
                  <div className="text-xs text-muted-foreground">
                    Multi-dimensional scoring with tier and confidence rollups.
                  </div>
                </div>
              </li>
              <li className="feature-item flex items-start gap-3 text-foreground/85">
                <span className="mt-0.5 inline-grid h-7 w-7 place-items-center rounded-md border border-border/60 bg-card/50 text-primary">
                  <Network className="h-3.5 w-3.5" />
                </span>
                <div>
                  <div className="font-medium text-foreground">
                    ManageEngine Ecosystem lean
                  </div>
                  <div className="text-xs text-muted-foreground">
                    AD360 &amp; Log360 aware-GTM — backed by{" "}
                    <span className="inline-flex items-center gap-1 align-baseline">
                      <span className="font-medium text-foreground">Love</span>
                      <Heart
                        aria-label="love"
                        className="h-3.5 w-3.5 text-[oklch(0.65_0.22_25)] fill-[oklch(0.65_0.22_25)] heart-beat"
                      />
                    </span>
                    .
                  </div>
                </div>
              </li>
            </ul>
          </div>

          <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.2em] text-muted-foreground/80">
            <Radar className="h-3.5 w-3.5 text-primary/70" />
            <span>Enterprise Lead Intelligence and Scoring System</span>
          </div>
        </aside>

        {/* RIGHT — form panel. On mobile (<lg) we top-anchor the card with
            `justify-start` so the iframe shrinking from 520 → ~200 px (when
            measure() lands) doesn't yank the Welcome header downward as the
            centered column recenters. On desktop we keep `justify-center`
            because the brand sidebar fills the left half and a centered form
            on the right reads as deliberate composition rather than a tall
            empty space. */}
        <main className="flex min-h-[100svh] min-h-[100dvh] flex-col items-center justify-start lg:justify-center px-4 py-6 pt-[max(env(safe-area-inset-top),1.5rem)] pb-[max(env(safe-area-inset-bottom),1.5rem)] sm:px-8">
          <div className="w-full max-w-[420px]">
            {/* Inline brand row (visible on < lg viewports) — full product
                name, centered, two-line wrap. Replaces the prior "ELISS /
                Lead Intelligence Hub" abbreviation for brand consistency
                with the desktop sidebar footer and the app header. */}
            <div className="mb-6 flex flex-col items-center gap-2 text-center lg:hidden">
              <img src={logoSrc} alt="" aria-hidden width={36} height={36} className="h-9 w-auto" />
              <div className="text-[11px] font-semibold uppercase tracking-[0.18em] leading-tight text-foreground/85">
                Enterprise Lead Intelligence
                <br />
                and Scoring System
              </div>
            </div>

            {/* Card */}
            <div className="login-card-rise overflow-hidden rounded-2xl border border-border/80 bg-card/80 shadow-[0_24px_70px_-24px_rgba(0,0,0,0.75)] backdrop-blur-sm">
              {/* Card header — small banner inside the card so the form has context */}
              <div className="border-b border-border/60 px-6 pb-4 pt-5">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-base font-semibold tracking-tight">
                      Welcome back
                    </div>
                    <div className="mt-0.5 text-xs text-muted-foreground">
                      Sign in to your workspace to continue.
                    </div>
                  </div>
                  <span className="login-badge-glow hidden sm:inline-grid h-9 w-9 place-items-center rounded-full border border-border/60 bg-background/60 text-primary">
                    <LogIn className="h-4 w-4" />
                  </span>
                </div>
              </div>

              {/* Catalyst iframe slot — iframe height is driven dynamically
                  by the LoginScreen effect above (ResizeObserver on the
                  inner #signin_flow), so the shell tracks every Catalyst
                  step (email / password / OTP+banner / MFA / captcha)
                  without clipping or trailing whitespace. */}
              <div
                ref={slotRef}
                id={CATALYST_LOGIN_ID}
                // min-h compensates for vertical padding (pt-1 + pb-3 = 16 px)
                // so the slot's outer box is the same size whether the iframe
                // has mounted or not (prevents the "Welcome back" header from
                // jumping 8 px up when Catalyst injects the iframe).
                // The min() cap means: tall viewports reserve 536 px to
                // absorb the post-mount → post-measure transition; phones
                // (where 536 px would be most of the screen) cap at 70 svh
                // so the card stays proportional. After the first measure,
                // the `apply()` function above drives iframe height to the
                // real content size — the slot then naturally hugs it.
                className="relative w-full min-h-[min(536px,70svh)] transition-[min-height] duration-300 ease-out px-3 pb-3 pt-1 [&_iframe]:!w-full [&_iframe]:!border-0 [&_iframe]:!bg-transparent before:pointer-events-none before:absolute before:inset-3 before:rounded-md before:bg-gradient-to-br before:from-white/[0.02] before:to-white/[0.06] before:transition-opacity before:duration-200 [&:not(:has(iframe))]:before:opacity-100 has-[iframe]:before:opacity-0"
              />

              {/* Card footer — tiny trust strip */}
              <div className="flex items-center justify-between border-t border-border/60 bg-background/30 px-6 py-3 text-[10px] uppercase tracking-[0.18em] text-muted-foreground/80">
                <span className="flex items-center gap-1.5">
                  <Lock className="h-3 w-3 text-primary/70" />
                  ManageEngine · Confidential
                </span>
                <span>Internal use only</span>
              </div>
            </div>

            <p className="mt-5 text-center text-xs text-muted-foreground">
              New to ELISS?{" "}
              <button
                type="button"
                onClick={() => router.navigate({ to: "/signup" })}
                className="font-medium text-primary hover:underline"
              >
                Sign up
              </button>
            </p>
            <p className="mt-2 text-center text-[11px] text-muted-foreground/70">
              By signing in you agree to the workspace acceptable-use policy.
            </p>
          </div>
        </main>
      </div>
    </div>
  );
}
