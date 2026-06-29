import { useEffect } from "react";
import { Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerDescription,
  DrawerTitle,
  DrawerTrigger,
} from "@/components/ui/drawer";
import {
  LayoutDashboard,
  FileSearch,
  Upload,
  Sparkles,
  Shield,
  SlidersHorizontal,
  KeyRound,
  LogOut,
  Menu,
  ScrollText,
  Bell,
  type LucideIcon,
} from "lucide-react";

interface MobileNavSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Full name, or email fallback — already derived by AppShell. */
  display: string;
  accountEmail: string;
  /** Uppercased initials — already derived by AppShell. */
  initials: string;
  isAdmin: boolean;
  /** Single super-admin gate for the generation-settings link. */
  isSuperAdmin: boolean;
  /** AppShell's route-active predicate. */
  isActive: (path: string) => boolean;
  /** Desktop-notification opt-in state (mirrors the desktop account dropdown).
     The success sound is desktop-browser only, so it has NO mobile toggle. */
  notifyOn: boolean;
  onToggleNotify: (on: boolean) => void | Promise<void>;
  /** Closes the sheet, then opens the shared reset Dialog. */
  onResetPassword: () => void;
  /** Closes the sheet, then signs out. */
  onSignOut: () => void;
}

/**
 * Mobile (<md) navigation menu rendered as a native bottom sheet (vaul).
 * Drag/flick down, tap the backdrop, tap a row, or Esc to dismiss; the app
 * behind dims and scales (requires `data-vaul-drawer-wrapper` on the app root).
 * Desktop uses a separate account dropdown in AppShell — this is md:hidden via
 * the trigger that controls `open`.
 */
export function MobileNavSheet({
  open,
  onOpenChange,
  display,
  accountEmail,
  initials,
  isAdmin,
  isSuperAdmin,
  isActive,
  notifyOn,
  onToggleNotify,
  onResetPassword,
  onSignOut,
}: MobileNavSheetProps) {
  const navItems: { to: string; label: string; Icon: LucideIcon }[] = [
    { to: "/", label: "Dashboard", Icon: LayoutDashboard },
    { to: "/leads", label: "Leads", Icon: FileSearch },
    ...(isAdmin || isSuperAdmin
      ? [{ to: "/audit", label: "Audit", Icon: ScrollText }]
      : []),
    {
      to: "/upload",
      label: isAdmin ? "Upload" : "Create",
      Icon: isAdmin ? Upload : Sparkles,
    },
    ...(isAdmin ? [{ to: "/admin", label: "Admin", Icon: Shield }] : []),
    ...(isSuperAdmin
      ? [{ to: "/settings", label: "Settings", Icon: SlidersHorizontal }]
      : []),
  ];

  // Self-managed background zoom (replaces vaul's shouldScaleBackground, which
  // jumps in standalone PWAs: its open transform includes env(safe-area-inset-top)
  // but its drag transform doesn't). We flag the document while open and drive the
  // zoom from CSS with NO safe-area term, so browser and installed-PWA match and
  // the background doesn't shift mid-drag. See styles.css [data-nav-sheet-open].
  useEffect(() => {
    const el = document.documentElement;
    if (open) el.setAttribute("data-nav-sheet-open", "");
    else el.removeAttribute("data-nav-sheet-open");
    return () => el.removeAttribute("data-nav-sheet-open");
  }, [open]);

  // autoFocus: vaul defaults to false and then preventDefault()s the dialog's
  // open-auto-focus, which leaves focus on the trigger while the background is
  // aria-hidden (Chrome a11y warning + keyboard user stuck outside the sheet).
  // Enabling it moves focus into the sheet on open.
  //
  // shouldScaleBackground={false} is explicit: the shared drawer.tsx wrapper
  // defaults it to TRUE, so omitting it would leave vaul's (glitchy) scaling on.
  // We drive the zoom ourselves via CSS instead (see the effect above).
  return (
    <Drawer open={open} onOpenChange={onOpenChange} shouldScaleBackground={false} autoFocus>
      {/* The trigger lives inside the Drawer so vaul manages focus correctly:
         on open it moves focus into the sheet (not left on a now-aria-hidden
         trigger), and returns it to the trigger on close. */}
      <DrawerTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="md:hidden h-9 w-9 p-0"
          aria-label="Open menu"
        >
          <Menu className="h-5 w-5" />
        </Button>
      </DrawerTrigger>
      {/* border-x-0 border-b-0: the shared DrawerContent sets a full border, but
         a bottom-anchored full-width sheet only wants a top edge. */}
      <DrawerContent className="rounded-t-2xl border-x-0 border-b-0 max-h-[90vh] pb-[max(env(safe-area-inset-bottom),0.75rem)] focus-visible:outline-none">
        {/* Accessible name + description for the dialog; the visual title is the
           identity row, so both are sr-only. */}
        <DrawerTitle className="sr-only">Menu</DrawerTitle>
        <DrawerDescription className="sr-only">
          Account details and primary navigation
        </DrawerDescription>

        {/* Identity header */}
        <div className="flex items-center gap-3 px-4 pb-4 pt-1 border-b border-border/60">
          <span
            aria-hidden
            className="inline-grid h-10 w-10 shrink-0 place-items-center rounded-full bg-primary/25 text-sm font-semibold text-foreground"
          >
            {initials.slice(0, 2)}
          </span>
          <div className="min-w-0 flex-1">
            <div className="text-sm font-medium text-foreground truncate">{display}</div>
            <div className="text-xs text-muted-foreground truncate">{accountEmail}</div>
          </div>
        </div>

        {/* Nav rows — tap navigates AND closes (DrawerClose asChild). */}
        <nav aria-label="Mobile main" className="flex flex-col py-1">
          {navItems.map(({ to, label, Icon }) => {
            const active = isActive(to);
            return (
              <DrawerClose asChild key={to}>
                <Link
                  to={to}
                  aria-current={active ? "page" : undefined}
                  className={`relative flex items-center gap-3.5 px-4 py-3.5 text-sm transition-colors active:bg-accent/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary ${
                    active
                      ? "bg-primary/15 text-foreground before:absolute before:inset-y-0 before:left-0 before:w-1 before:bg-primary"
                      : "text-foreground/85"
                  }`}
                >
                  <Icon
                    className={`h-5 w-5 ${active ? "text-primary" : "text-muted-foreground"}`}
                  />
                  <span className="flex-1">{label}</span>
                </Link>
              </DrawerClose>
            );
          })}
        </nav>

        {/* Completion alerts — only the Desktop notification toggle here. The
           success sound is desktop-browser only (no mobile toggle). Full-row
           button carrying role="switch"; the switch graphic is a pure-visual
           aria-hidden span so we never nest an interactive control inside the
           button. Toggling does NOT close the sheet. */}
        <div className="mt-1 border-t border-border/60 pt-1">
          <div className="px-4 pt-2 pb-1 text-xs uppercase tracking-wider text-muted-foreground">
            Completion alerts
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={notifyOn}
            onClick={() => void onToggleNotify(!notifyOn)}
            className="flex w-full items-center gap-3.5 px-4 py-3.5 text-left text-sm text-foreground/85 transition-colors active:bg-accent/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary"
          >
            <Bell className="h-5 w-5 text-muted-foreground" />
            <span className="flex-1">Desktop notification</span>
            <span
              aria-hidden
              className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors ${notifyOn ? "bg-primary" : "bg-input"}`}
            >
              <span
                className={`inline-block h-4 w-4 rounded-full bg-background shadow transition-transform ${notifyOn ? "translate-x-4" : "translate-x-0.5"}`}
              />
            </span>
          </button>
        </div>

        {/* Account actions — divided group; Sign out destructive. */}
        <div className="mt-1 border-t border-border/60 pt-1">
          <button
            type="button"
            onClick={onResetPassword}
            className="flex w-full items-center gap-3.5 px-4 py-3.5 text-left text-sm text-foreground/85 transition-colors active:bg-accent/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary"
          >
            <KeyRound className="h-5 w-5 text-muted-foreground" />
            <span className="flex-1">Reset password</span>
          </button>
          <button
            type="button"
            onClick={onSignOut}
            className="flex w-full items-center gap-3.5 px-4 py-3.5 text-left text-sm text-destructive transition-colors active:bg-destructive/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary"
          >
            <LogOut className="h-5 w-5" />
            <span className="flex-1">Sign out</span>
          </button>
        </div>
      </DrawerContent>
    </Drawer>
  );
}
