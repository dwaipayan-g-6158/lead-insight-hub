import { useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { Link, useLocation } from "@tanstack/react-router";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  LayoutDashboard,
  FileSearch,
  Upload,
  LogOut,
  Shield,
  Sparkles,
  ChevronDown,
  KeyRound,
  SlidersHorizontal,
  ScrollText,
  Volume2,
  Bell,
} from "lucide-react";
import { toast } from "sonner";
import {
  getNotifyEnabled,
  getSoundEnabled,
  setSoundEnabled,
  toggleDesktopNotifications,
} from "@/lib/notify";
import { ActiveRequestsPill } from "@/components/ActiveRequestsPill";
import { MobileNavSheet } from "@/components/MobileNavSheet";
import { DossierActivityPopup } from "@/components/DossierActivityPopup";
import { DossierActivityProvider } from "@/lib/dossier-activity";
import { Spinner } from "@/components/Spinner";
import { resetMyPassword } from "@/lib/api";

// Pixie-dust sparkle burst shown for the brief ELISS-Heavy "armed" window.
// Defined at MODULE scope (never inside AppShell's render) so it keeps a stable
// component identity — a component declared inline would get a fresh identity
// every parent render and React would remount/restart it. The randomised grain
// styles are computed ONCE per mount via useMemo; because this only mounts while
// `heavyArmed` is true, each unlock yields a fresh, organic spread. Distances/
// sizes are tuned for the 32px (h-8) header logo. Purely decorative: the wrapper
// is aria-hidden and pointer-events:none (see .heavy-sparkles in styles.css).
const SPARKLE_COLORS = ["#a78bfa", "#7c5cff", "#fde68a", "#ffffff"];
function HeavySparkles() {
  const grains = useMemo(
    () =>
      Array.from({ length: 16 }, () => {
        const ang = Math.random() * Math.PI * 2;
        const dist = 24 + Math.random() * 40;
        const tx = Math.cos(ang) * dist;
        const ty = Math.sin(ang) * dist - (8 + Math.random() * 22); // upward bias = "floaty"
        return {
          "--tx": `${tx.toFixed(1)}px`,
          "--ty": `${ty.toFixed(1)}px`,
          "--sz": `${(5 + Math.random() * 5).toFixed(1)}px`,
          "--sc": (0.3 + Math.random() * 0.7).toFixed(2),
          "--rot": `${Math.round(90 + Math.random() * 240)}deg`,
          "--dur": `${(0.8 + Math.random() * 0.35).toFixed(2)}s`,
          "--delay": `${(Math.random() * 0.15).toFixed(2)}s`,
          "--c": SPARKLE_COLORS[Math.floor(Math.random() * SPARKLE_COLORS.length)],
        } as CSSProperties;
      }),
    [],
  );
  return (
    <span className="heavy-sparkles" aria-hidden>
      {grains.map((style, i) => (
        <span key={i} className="sparkle" style={style} />
      ))}
    </span>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { user, signOut, isAdmin, isSuperAdmin, heavyAllowed } = useAuth();
  const loc = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const isActive = (p: string) => loc.pathname === p || (p !== "/" && loc.pathname.startsWith(p));

  // Rapid-tap counter on the logo: 5 taps within 800 ms of each other arm the
  // gated toggle for a single 60s window. CreateDossierModal reads the stored
  // timestamp on every open and shows the toggle only if it falls inside the
  // window. The flag is single-use — cleared on successful submit — so a fresh
  // 5-tap is required for the next heavy run. Any pause > 800 ms resets the
  // counter, so a normal "tap logo to go home" interaction never triggers it.
  //
  // Counted on pointerdown (not click): on mobile, touch->click synthesis is
  // delayed/occasionally coalesced and human tapping cadence on the small logo
  // is uneven, so click-based counting missed taps. pointerdown fires
  // immediately and reliably for mouse, touch, and pen, while the Link's own
  // click still handles navigation (pointerdown does not preventDefault).
  const tapRef = useRef<{ count: number; last: number }>({ count: 0, last: 0 });
  // Transient flag that fires a one-shot glow pulse on the logo when the
  // gated ELISS-Heavy window is armed, so the 5-tap unlock has visible
  // feedback. Cleared after the pulse so a later unlock can re-trigger it.
  const [heavyArmed, setHeavyArmed] = useState(false);
  const armedTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onLogoTap = () => {
    // The 5-tap unlock is entitlement-gated: only allowlisted users (server
    // flag from GET /me) can arm the ELISS-Heavy toggle. Non-allowlisted users
    // tapping the logo just navigate home — no flag, no glow. The backend
    // dossiers route is still the authoritative boundary regardless.
    if (!heavyAllowed) return;
    const now = Date.now();
    const ref = tapRef.current;
    ref.count = now - ref.last < 800 ? ref.count + 1 : 1;
    ref.last = now;
    if (ref.count >= 5) {
      ref.count = 0;
      try {
        // Store the activation epoch-ms. Legacy "1" values from earlier
        // builds parse to integer 1 and are well outside any TTL window,
        // so this auto-migrates without explicit cleanup.
        window.localStorage.setItem("_lih_x", String(now));
      } catch {
        /* localStorage unavailable — silently no-op */
      }
      // Retrigger the pulse: drop the class, then re-add on the next frame.
      setHeavyArmed(false);
      if (armedTimer.current) clearTimeout(armedTimer.current);
      requestAnimationFrame(() => {
        setHeavyArmed(true);
        // 1400ms keeps the sparkle burst mounted until its longest grain
        // (dur ≤ 1.15s + delay ≤ 0.15s) has finished; the 0.9s glow pulse on
        // the logo plays once within this window and then holds its rest state.
        armedTimer.current = setTimeout(() => setHeavyArmed(false), 1400);
      });
    }
  };
  useEffect(() => () => {
    if (armedTimer.current) clearTimeout(armedTimer.current);
  }, []);
  // Lead detail pages (e.g. /leads/31210000000141422) escape the 1280px content
  // cap so the dossier iframe can fill the viewport. The bare /leads list stays
  // capped — its table is designed for that width.
  const isLeadDetail =
    loc.pathname.startsWith("/leads/") && loc.pathname !== "/leads";

  const u = user as
    | {
        first_name?: string;
        last_name?: string;
        email_id?: string;
        email?: string;
      }
    | null;
  const fullName = [u?.first_name, u?.last_name].filter(Boolean).join(" ");
  const display = fullName || u?.email_id || u?.email || "Signed in";
  const initialsRaw =
    ((u?.first_name?.[0] ?? "") + (u?.last_name?.[0] ?? "")) ||
    (u?.email_id?.[0] ?? u?.email?.[0] ?? "?");
  const initials = initialsRaw.toUpperCase();
  const accountEmail = u?.email_id || u?.email || "your email";

  // Self-service password reset. Catalyst Native Auth is email-based — the
  // server triggers Catalyst's reset email and the user sets the new password
  // on Catalyst's hosted page. We just confirm intent, fire the request, and
  // toast the outcome. resetOpen drives a shared dialog rendered once below;
  // it is opened from BOTH the desktop pill dropdown and the mobile Sheet.
  const [resetOpen, setResetOpen] = useState(false);
  const [resetBusy, setResetBusy] = useState(false);

  // Per-user completion-feedback prefs (localStorage; default off). Mirrored in
  // the account menu so the user can turn the chime / desktop notifications on
  // or off. Turning notifications on triggers the browser permission prompt.
  const [soundOn, setSoundOn] = useState(false);
  const [notifyOn, setNotifyOn] = useState(false);
  useEffect(() => {
    setSoundOn(getSoundEnabled());
    setNotifyOn(getNotifyEnabled());
  }, []);
  const onToggleSound = (v: boolean) => {
    setSoundOn(v);
    setSoundEnabled(v);
  };
  const onToggleNotify = async (v: boolean) => {
    const ok = await toggleDesktopNotifications(v);
    setNotifyOn(ok);
    if (v && !ok) {
      toast.error("Desktop notifications are blocked in your browser settings");
    }
  };
  const confirmReset = async () => {
    setResetBusy(true);
    try {
      const r = await resetMyPassword();
      toast.success(`Reset link sent to ${r.email}`);
      setResetOpen(false);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Reset failed");
    } finally {
      setResetBusy(false);
    }
  };

  const navItem = (to: string, label: string, Icon: typeof LayoutDashboard) => (
    <Link
      to={to}
      className={`inline-flex items-center gap-2 px-3 py-2 sm:py-1.5 rounded-md text-sm transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background ${
        isActive(to)
          ? "bg-primary/15 text-primary"
          : "text-muted-foreground hover:text-foreground hover:bg-accent/50"
      }`}
    >
      <Icon className="h-4 w-4" />
      {label}
    </Link>
  );

  return (
    <DossierActivityProvider>
    <div
      data-vaul-drawer-wrapper=""
      className={
        isLeadDetail
          ? // On lg+ lock to viewport so the iframe fills the screen. On mobile
            // keep min-h-screen so the page can grow and iOS Safari URL bar
            // collapse works naturally.
            "min-h-screen lg:h-screen lg:overflow-hidden bg-background flex flex-col"
          : "min-h-screen bg-background flex flex-col"
      }
    >
      <header className="border-b border-border bg-card/40 backdrop-blur sticky top-0 z-10 pt-[env(safe-area-inset-top)] pl-[max(env(safe-area-inset-left),0px)] pr-[max(env(safe-area-inset-right),0px)]">
        <div className="mx-auto max-w-7xl px-4 h-14 flex items-center gap-4 sm:gap-6">
          {/* Logo link: aria-label removed so the visible product name
             IS the accessible name (WCAG 2.5.3 Label in Name). Voice-
             control users saying "Click Enterprise…" now matches. The
             logo image stays alt="" because its meaning is conveyed by
             the adjacent text. */}
          <Link
            to="/"
            onPointerDown={onLogoTap}
            className="flex items-center gap-2 cursor-pointer touch-manipulation select-none [-webkit-touch-callout:none] rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            <span
              className={`relative inline-flex ${heavyArmed ? "logo-armed" : ""}`}
              aria-hidden
            >
              <img
                src={`${import.meta.env.BASE_URL}logo.svg`}
                alt=""
                aria-hidden
                className="h-8 w-8 logo-spin"
              />
              {heavyArmed && <HeavySparkles />}
            </span>
            <div className="text-[11px] sm:text-sm font-semibold leading-tight tracking-tight">
              Enterprise Lead Intelligence
              <br />
              and Scoring System
            </div>
          </Link>
          {/* Desktop / tablet nav (md+) — full inline */}
          <nav aria-label="Main" className="hidden md:flex items-center gap-1">
            {navItem("/", "Dashboard", LayoutDashboard)}
            {navItem("/leads", "Leads", FileSearch)}
            {(isAdmin || isSuperAdmin) && navItem("/audit", "Audit", ScrollText)}
            {navItem("/upload", isAdmin ? "Upload" : "Create", isAdmin ? Upload : Sparkles)}
            {isAdmin && navItem("/admin", "Admin", Shield)}
            {isSuperAdmin && navItem("/settings", "Settings", SlidersHorizontal)}
          </nav>
          <div className="ml-auto flex items-center gap-2 sm:gap-3">
            {/* Visible on every breakpoint. On mobile the pill renders in a
               compact form (icon + live count only) so the dossier status is
               glanceable on a phone AND so the "Run in background" minimize
               animation has a real on-screen target (#dossier-activity-pill).
               Single instance → one polling loop shared by both layouts. */}
            <div className="block">
              <ActiveRequestsPill />
            </div>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  id="account-menu-trigger"
                  className="hidden md:flex items-center gap-2 rounded-full border border-border/60 bg-card/60 pl-1.5 pr-2.5 py-1 cursor-pointer transition-colors hover:bg-card/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                  title={display}
                  aria-label={`Account menu for ${display}`}
                >
                  <span
                    aria-hidden
                    className="inline-grid h-6 w-6 place-items-center rounded-full bg-primary/25 text-[10px] font-semibold text-foreground"
                  >
                    {initials.slice(0, 2)}
                  </span>
                  <span className="text-xs text-foreground/80 max-w-[160px] truncate">{display}</span>
                  <ChevronDown className="h-3 w-3 opacity-70" aria-hidden />
                </button>
              </DropdownMenuTrigger>
              {/* Single canonical account menu, styled to mirror the Dossier
                 Requests popover (ActiveRequestsPill.tsx): w-80 p-0 panel with
                 a full-width uppercase header + border-b dividers and full-
                 bleed action rows. Stays a DropdownMenu so it keeps keyboard
                 menu semantics and auto-close-on-select. */}
              <DropdownMenuContent
                align="end"
                className="w-80 p-0"
                // Radix returns focus to the trigger when the menu closes. After a
                // mouse-driven close (click-outside or item select) Chrome still
                // flags that restored focus as :focus-visible, so the primary ring
                // stays stuck on the pill until the next click — visually out of
                // step with the Dossier Requests Popover pill, which shows no ring.
                // Suppressing the focus-return means the ring only appears on a
                // genuine keyboard Tab onto the pill, not after a pointer close.
                onCloseAutoFocus={(e) => e.preventDefault()}
              >
                <DropdownMenuLabel className="px-3 py-2 border-b font-normal text-xs uppercase tracking-wider text-muted-foreground">
                  Account
                </DropdownMenuLabel>
                <DropdownMenuLabel className="px-3 py-2 border-b font-normal">
                  <div className="text-sm font-medium text-foreground truncate">{display}</div>
                  <div className="text-xs text-muted-foreground truncate">{accountEmail}</div>
                </DropdownMenuLabel>
                <DropdownMenuLabel className="px-3 py-2 border-b font-normal text-xs uppercase tracking-wider text-muted-foreground">
                  Completion alerts
                </DropdownMenuLabel>
                <DropdownMenuCheckboxItem
                  checked={soundOn}
                  onSelect={(e) => e.preventDefault()}
                  onCheckedChange={onToggleSound}
                  className="cursor-pointer py-2"
                >
                  <Volume2 className="h-4 w-4 mr-2" />
                  Success sound
                </DropdownMenuCheckboxItem>
                <DropdownMenuCheckboxItem
                  checked={notifyOn}
                  onSelect={(e) => e.preventDefault()}
                  onCheckedChange={(v) => void onToggleNotify(v)}
                  className="cursor-pointer py-2 border-b"
                >
                  <Bell className="h-4 w-4 mr-2" />
                  Desktop notification
                </DropdownMenuCheckboxItem>
                <DropdownMenuItem
                  className="cursor-pointer px-3 py-2 rounded-none"
                  onSelect={() => setResetOpen(true)}
                >
                  <KeyRound className="h-4 w-4 mr-2" />
                  Reset password
                </DropdownMenuItem>
                <DropdownMenuItem
                  className="cursor-pointer px-3 py-2 rounded-none text-destructive focus:text-destructive"
                  onSelect={() => signOut()}
                >
                  <LogOut className="h-4 w-4 mr-2" />
                  Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            {/* Mobile menu (below md) — MobileNavSheet renders its own
               md:hidden hamburger (a vaul DrawerTrigger) and the bottom sheet
               with nav + account actions. */}
            <MobileNavSheet
              open={mobileOpen}
              onOpenChange={setMobileOpen}
              display={display}
              accountEmail={accountEmail}
              initials={initials}
              isAdmin={isAdmin}
              isSuperAdmin={isSuperAdmin}
              isActive={isActive}
              soundOn={soundOn}
              notifyOn={notifyOn}
              onToggleSound={onToggleSound}
              onToggleNotify={onToggleNotify}
              onResetPassword={() => {
                setMobileOpen(false);
                setResetOpen(true);
              }}
              onSignOut={() => {
                setMobileOpen(false);
                signOut();
              }}
            />
          </div>
        </div>
      </header>
      <main
        className={
          isLeadDetail
            ? "w-full px-4 pt-3 pb-2 flex-1 flex flex-col min-h-0"
            : "mx-auto max-w-7xl px-4 py-6 flex-1 w-full"
        }
      >
        {children}
      </main>
      {!isLeadDetail && (
        <footer className="border-t border-border bg-card/40 mt-auto py-4">
          <div className="mx-auto max-w-7xl px-4 flex flex-col items-center gap-1.5 text-center sm:flex-row sm:justify-between sm:text-left text-xs text-muted-foreground">
            <span>© {new Date().getFullYear()} ManageEngine. All rights reserved.</span>
            <span className="text-[10px] uppercase tracking-wider">Confidential & Proprietary</span>
          </div>
        </footer>
      )}
    </div>
    <DossierActivityPopup />
    {/* Shared password-reset confirm dialog — opened from the desktop pill
       dropdown and the mobile Sheet. Rendered as a sibling (not nested in the
       dropdown item) so closing the menu doesn't unmount it. */}
    <Dialog open={resetOpen} onOpenChange={(o) => !resetBusy && setResetOpen(o)}>
      <DialogContent className="sm:max-w-md" flyTarget="#account-menu-trigger">
        <DialogHeader>
          <DialogTitle>Reset your password?</DialogTitle>
          <DialogDescription>
            We'll email a secure reset link to <strong>{accountEmail}</strong>. Open it to
            set a new password on Zoho's secure page, then you'll return to the app.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button
            variant="ghost"
            onClick={() => setResetOpen(false)}
            disabled={resetBusy}
          >
            Cancel
          </Button>
          <Button onClick={confirmReset} disabled={resetBusy}>
            {resetBusy && <Spinner className="h-4 w-4 mr-2" />}
            Send reset link
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
    </DossierActivityProvider>
  );
}
