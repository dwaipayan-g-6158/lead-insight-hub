import { useRef, useState, type ReactNode } from "react";
import { Link, useLocation } from "@tanstack/react-router";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  LayoutDashboard,
  FileSearch,
  Upload,
  LogOut,
  Shield,
  Menu,
  Sparkles,
  X,
  ChevronRight,
} from "lucide-react";
import { ActiveRequestsPill } from "@/components/ActiveRequestsPill";
import { DossierActivityPopup } from "@/components/DossierActivityPopup";
import { DossierActivityProvider } from "@/lib/dossier-activity";

export function AppShell({ children }: { children: ReactNode }) {
  const { user, signOut, isAdmin } = useAuth();
  const loc = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const isActive = (p: string) => loc.pathname === p || (p !== "/" && loc.pathname.startsWith(p));

  // Rapid-tap counter on the logo: 5 clicks within 500 ms of each other
  // arm the gated toggle for a single 60s window. CreateDossierModal reads
  // the stored timestamp on every open and shows the toggle only if it
  // falls inside the window. The flag is single-use — cleared on successful
  // submit — so a fresh 5-tap is required for the next heavy run. Tap below
  // threshold or any pause > 500 ms resets the counter, so a normal
  // "click logo to go home" interaction never triggers it. The Link's own
  // onClick still fires (navigation is unaffected).
  const tapRef = useRef<{ count: number; last: number }>({ count: 0, last: 0 });
  const onLogoTap = () => {
    const now = Date.now();
    const ref = tapRef.current;
    ref.count = now - ref.last < 500 ? ref.count + 1 : 1;
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
    }
  };
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
            onClick={onLogoTap}
            className="flex items-center gap-2 cursor-pointer rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            <img
              src={`${import.meta.env.BASE_URL}logo.svg`}
              alt=""
              aria-hidden
              className="h-8 w-8"
            />
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
            {navItem("/upload", isAdmin ? "Upload" : "Create", isAdmin ? Upload : Sparkles)}
            {isAdmin && navItem("/admin", "Admin", Shield)}
          </nav>
          <div className="ml-auto flex items-center gap-2 sm:gap-3">
            <div className="hidden md:block">
              <ActiveRequestsPill />
            </div>
            <div
              className="hidden md:flex items-center gap-2 rounded-full border border-border/60 bg-card/60 pl-1.5 pr-3 py-1"
              title={display}
            >
              <span
                aria-hidden
                className="inline-grid h-6 w-6 place-items-center rounded-full bg-primary/25 text-[10px] font-semibold text-foreground"
              >
                {initials.slice(0, 2)}
              </span>
              <span className="text-xs text-foreground/80 max-w-[160px] truncate">{display}</span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={signOut}
              className="hidden md:inline-flex cursor-pointer focus-visible:ring-2 focus-visible:ring-primary"
              aria-label={`Sign out ${display}`}
            >
              <LogOut className="h-4 w-4 mr-2" />
              <span>Sign out</span>
            </Button>

            {/* Mobile menu (below md) — hamburger opens a Sheet exposing all
               nav items, the user identity, and sign-out. Previously Admin
               and Sign-out were dropped off-screen at narrow widths. */}
            <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
              <SheetTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className="md:hidden h-9 w-9 p-0"
                  aria-label="Open menu"
                >
                  <Menu className="h-5 w-5" />
                </Button>
              </SheetTrigger>
              {/*
                Custom mobile menu: iOS-style top bar with a real bordered
                close button (replaces the default `SheetPrimitive.Close`
                opacity-70 X — that one is small, faint, and easy to miss
                on a real iPhone). We hide it via [&>button.absolute]:hidden
                and put our own SheetClose-wrapped Button in the header row
                where users expect it.

                Each nav row is wrapped in SheetClose asChild so a single tap
                navigates AND closes the drawer in one gesture (the previous
                `<div onClick={...}>` wrapper closed but didn't pass through
                the Radix Close primitive). Rows are full-width with chevrons
                — list-style affordance familiar from iOS Settings.
              */}
              <SheetContent
                side="right"
                className="w-[88vw] max-w-[340px] flex flex-col gap-0 p-0 pt-[env(safe-area-inset-top)] pb-[env(safe-area-inset-bottom)] pr-[env(safe-area-inset-right)] [&>button.absolute]:hidden"
              >
                {/* Top bar — sticky title + close on the right */}
                <div className="flex items-center justify-between h-14 px-3 border-b border-border/60 bg-card/40 backdrop-blur">
                  <SheetTitle className="text-base font-semibold pl-1">Menu</SheetTitle>
                  <SheetClose asChild>
                    <Button
                      variant="ghost"
                      className="h-10 w-10 p-0 rounded-full border border-border/60 hover:bg-accent text-foreground"
                      aria-label="Close menu"
                    >
                      <X className="h-5 w-5" />
                    </Button>
                  </SheetClose>
                </div>

                {/* User identity row */}
                <div className="flex items-center gap-3 px-4 py-4 border-b border-border/60">
                  <span
                    aria-hidden
                    className="inline-grid h-10 w-10 shrink-0 place-items-center rounded-full bg-primary/25 text-sm font-semibold text-foreground"
                  >
                    {initials.slice(0, 2)}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium text-foreground truncate">{display}</div>
                    <div className="text-xs text-muted-foreground">Signed in</div>
                  </div>
                </div>

                {/* Nav rows — full-width tappable, chevron affordance */}
                <nav aria-label="Mobile main" className="flex-1 flex flex-col py-2 overflow-y-auto">
                  {([
                    { to: "/", label: "Dashboard", Icon: LayoutDashboard },
                    { to: "/leads", label: "Leads", Icon: FileSearch },
                    {
                      to: "/upload",
                      label: isAdmin ? "Upload" : "Create",
                      Icon: isAdmin ? Upload : Sparkles,
                    },
                    ...(isAdmin ? [{ to: "/admin" as const, label: "Admin", Icon: Shield }] : []),
                  ]).map(({ to, label, Icon }) => {
                    const active = isActive(to);
                    return (
                      <SheetClose asChild key={to}>
                        <Link
                          to={to}
                          className={`flex items-center gap-3 px-4 py-3.5 active:bg-accent/60 transition-colors ${
                            active ? "bg-primary/15 text-foreground" : "text-foreground/85"
                          }`}
                        >
                          <Icon className={`h-5 w-5 ${active ? "text-primary" : "text-muted-foreground"}`} />
                          {/* text-sm (14 px) matches the main app's body
                              text. text-base (16 px) felt inflated next to
                              content rows behind the drawer overlay. */}
                          <span className="text-sm flex-1">{label}</span>
                          <ChevronRight className="h-4 w-4 text-muted-foreground/50" />
                        </Link>
                      </SheetClose>
                    );
                  })}
                </nav>

                {/* Footer — full-width sign-out */}
                <div className="border-t border-border/60 p-4">
                  <Button
                    variant="outline"
                    onClick={() => {
                      setMobileOpen(false);
                      signOut();
                    }}
                    className="w-full"
                    aria-label={`Sign out ${display}`}
                  >
                    <LogOut className="h-4 w-4 mr-2" />
                    Sign out
                  </Button>
                </div>
              </SheetContent>
            </Sheet>
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
    </DossierActivityProvider>
  );
}
