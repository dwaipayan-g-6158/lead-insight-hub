# Mobile Bottom-Sheet Navigation Menu — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the gesture-less right-side Radix `Sheet` mobile menu with a native, drag-dismissible bottom sheet built on `vaul`, extracted into a self-contained `MobileNavSheet` component.

**Architecture:** A new `MobileNavSheet` component renders a `vaul` `Drawer` (via the existing `app/src/components/ui/drawer.tsx` wrapper) at content height: identity header → nav rows (active route gets a left accent bar) → divided account actions (Reset password, Sign out in red). `AppShell.tsx` keeps the hamburger as a plain trigger that toggles `mobileOpen`, renders `MobileNavSheet`, and gains a `data-vaul-drawer-wrapper` attribute on its root so vaul can scale the background. Desktop (≥md) is untouched. The reset `Dialog`, `signOut`/`isAdmin`, and nav-item set are reused as-is.

**Tech Stack:** React 19, TypeScript, Tailwind v4, `@tanstack/react-router`, `vaul ^1.1.2` (already installed), `lucide-react`, Catalyst Web Client Hosting.

> **Environment notes (read first):**
> - **No test runner exists** (`package.json` scripts are only `dev`/`build`/`preview`). Verification per task is **`npx tsc --noEmit`** (type safety — the `vite build` step uses esbuild and does **not** type-check) plus **`npm run build`**, then browser checks via chrome-devtools-mcp on the Dev deployment.
> - **Not a git repository.** There are no per-task `git commit` steps; each task ends at a build/type-check checkpoint instead.
> - Spec: `docs/superpowers/specs/2026-06-02-mobile-bottom-sheet-menu-design.md`.

---

## File Structure

- **Create:** `app/src/components/MobileNavSheet.tsx` — owns the entire mobile menu (identity + nav + account actions) as a `vaul` bottom sheet. Single responsibility: the mobile navigation surface.
- **Modify:** `app/src/components/AppShell.tsx` — remove the `Sheet` block; render `MobileNavSheet`; convert the hamburger to a plain toggle button; add `data-vaul-drawer-wrapper` to the root div; clean up now-unused imports.
- **Reuse unchanged:** `app/src/components/ui/drawer.tsx` (vaul wrapper — styled via per-instance `className`, no edits), the reset `Dialog` + `confirmReset` in `AppShell`, `useAuth()`.

---

## Task 1: Create the `MobileNavSheet` component

**Files:**
- Create: `app/src/components/MobileNavSheet.tsx`

- [ ] **Step 1: Write the component**

Create `app/src/components/MobileNavSheet.tsx` with exactly this content:

```tsx
import { Link } from "@tanstack/react-router";
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerTitle,
} from "@/components/ui/drawer";
import {
  LayoutDashboard,
  FileSearch,
  Upload,
  Sparkles,
  Shield,
  KeyRound,
  LogOut,
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
  /** AppShell's route-active predicate. */
  isActive: (path: string) => boolean;
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
  isActive,
  onResetPassword,
  onSignOut,
}: MobileNavSheetProps) {
  const navItems: { to: string; label: string; Icon: LucideIcon }[] = [
    { to: "/", label: "Dashboard", Icon: LayoutDashboard },
    { to: "/leads", label: "Leads", Icon: FileSearch },
    {
      to: "/upload",
      label: isAdmin ? "Upload" : "Create",
      Icon: isAdmin ? Upload : Sparkles,
    },
    ...(isAdmin ? [{ to: "/admin", label: "Admin", Icon: Shield }] : []),
  ];

  return (
    <Drawer open={open} onOpenChange={onOpenChange} shouldScaleBackground>
      <DrawerContent className="rounded-t-2xl max-h-[90vh] pb-[max(env(safe-area-inset-bottom),0.75rem)] focus-visible:outline-none">
        {/* Accessible name for the dialog; the visual title is the identity row. */}
        <DrawerTitle className="sr-only">Menu</DrawerTitle>

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

        {/* Account actions — divided group; Sign out destructive. */}
        <div className="mt-1 border-t border-border/60 pt-1">
          <button
            type="button"
            onClick={onResetPassword}
            className="flex w-full items-center gap-3.5 px-4 py-3.5 text-left text-sm text-foreground/85 transition-colors active:bg-accent/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary"
            aria-label="Reset password"
          >
            <KeyRound className="h-5 w-5 text-muted-foreground" />
            <span className="flex-1">Reset password</span>
          </button>
          <button
            type="button"
            onClick={onSignOut}
            className="flex w-full items-center gap-3.5 px-4 py-3.5 text-left text-sm text-destructive transition-colors active:bg-accent/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary"
            aria-label={`Sign out ${display}`}
          >
            <LogOut className="h-5 w-5" />
            <span className="flex-1">Sign out</span>
          </button>
        </div>
      </DrawerContent>
    </Drawer>
  );
}
```

Notes baked into the code above:
- `DrawerContent` (in `drawer.tsx`) already renders the grip handle and is bottom-anchored at content height (`h-auto`); `cn()` uses `twMerge`, so the `rounded-t-2xl` override wins over the wrapper's `rounded-t-[10px]`.
- `shouldScaleBackground` is passed explicitly; it only has a visible effect once Task 2 adds `data-vaul-drawer-wrapper` to the app root.
- Touch targets are `py-3.5` (~52px ≥ 44px min). Active route is conveyed by accent bar + tint + `aria-current` (not color alone).

- [ ] **Step 2: Type-check the new file**

Run: `cd app && npx tsc --noEmit`
Expected: PASS (no errors). If it reports `MobileNavSheet` unused, that's expected until Task 2 imports it — proceed to Task 2 and re-check there.

---

## Task 2: Wire `MobileNavSheet` into `AppShell` and remove the old `Sheet`

**Files:**
- Modify: `app/src/components/AppShell.tsx`

- [ ] **Step 1: Add the import**

At the top of `AppShell.tsx`, add alongside the other component imports (e.g. just after the `ActiveRequestsPill` import, ~line 41):

```tsx
import { MobileNavSheet } from "@/components/MobileNavSheet";
```

- [ ] **Step 2: Add `data-vaul-drawer-wrapper` to the app root**

Find the root `<div>` returned inside `DossierActivityProvider` (~line 161, the one whose `className` is the `isLeadDetail ? ... : "min-h-screen bg-background flex flex-col"` ternary). Add the attribute so vaul can scale the background:

```tsx
    <div
      data-vaul-drawer-wrapper=""
      className={
        isLeadDetail
          ? "min-h-screen lg:h-screen lg:overflow-hidden bg-background flex flex-col"
          : "min-h-screen bg-background flex flex-col"
      }
    >
```

(Only the `data-vaul-drawer-wrapper=""` line is added; the existing `className` ternary is unchanged.)

- [ ] **Step 3: Replace the entire mobile `Sheet` block**

Delete the whole mobile menu block — from the opening comment `{/* Mobile menu (below md) ... */}` and its `<Sheet open={mobileOpen} ...> ... </Sheet>` (currently ~lines 270–391) — and replace it with the hamburger trigger + the new component:

```tsx
            {/* Mobile menu (below md) — hamburger toggles a native bottom
               sheet (MobileNavSheet) with nav + account actions. */}
            <Button
              variant="ghost"
              size="sm"
              className="md:hidden h-9 w-9 p-0"
              aria-label="Open menu"
              onClick={() => setMobileOpen(true)}
            >
              <Menu className="h-5 w-5" />
            </Button>
            <MobileNavSheet
              open={mobileOpen}
              onOpenChange={setMobileOpen}
              display={display}
              accountEmail={accountEmail}
              initials={initials}
              isAdmin={isAdmin}
              isActive={isActive}
              onResetPassword={() => {
                setMobileOpen(false);
                setResetOpen(true);
              }}
              onSignOut={() => {
                setMobileOpen(false);
                signOut();
              }}
            />
```

This keeps the hamburger inside the existing `<div className="ml-auto flex items-center gap-2 sm:gap-3">` row. `MobileNavSheet` renders its sheet through a portal, so its placement here is fine. The `md:hidden` on the button hides the whole mobile menu at ≥md (where the desktop dropdown takes over).

- [ ] **Step 4: Remove now-unused imports**

In `AppShell.tsx`:
- Delete the entire `Sheet`/`SheetClose`/`SheetContent`/`SheetTitle`/`SheetTrigger` import block (the `from "@/components/ui/sheet"` import, ~lines 5–11).
- In the `lucide-react` import, remove `X` and `ChevronRight` (they were only used by the deleted sheet). **Keep** `Menu` (hamburger), `ChevronDown` (desktop pill), `KeyRound`, `LogOut`, `Sparkles`, `Upload`, `FileSearch`, `LayoutDashboard`, `Shield` (all still used by the desktop nav/dropdown).

- [ ] **Step 5: Type-check**

Run: `cd app && npx tsc --noEmit`
Expected: PASS with no errors (no unused-import errors, no missing-prop errors on `MobileNavSheet`).

- [ ] **Step 6: Production build**

Run: `cd app && npm run build`
Expected: `✓ built in …s`, no errors. (The 500 kB chunk-size warning is pre-existing and unrelated.)

---

## Task 3: Deploy to Dev and verify (visual + gesture + functional + a11y)

**Files:** none (deploy + browser verification).

- [ ] **Step 1: Deploy the client to Dev**

Run: `catalyst deploy --only client -p 31210000000133001 --org 60066539659 --dc in < /dev/null`
Expected: `DEPLOYMENT SUCCESSFUL: lead_insight_client`.

- [ ] **Step 2: Open the Dev app at mobile width (chrome-devtools-mcp)**

- `resize_page` to 390×844.
- `navigate_page` to `https://lead-insight-hub-60066539659.development.catalystserverless.in/app/?cb=bsheet0602` (cache-bust).
- `take_snapshot`; if on the dashboard, find the "Open menu" button.

- [ ] **Step 3: Verify the open state (visual)**

Click "Open menu", then `take_screenshot`. Confirm:
- A bottom sheet rises to **content height** with a rounded top + grip handle.
- The dashboard behind **dims and scales down slightly** (confirms `data-vaul-drawer-wrapper` works). If it does NOT scale, see the fallback note below.
- Order top→bottom: identity (DG / name / email) → Dashboard / Leads / Create (or Upload) → divider → Reset password → Sign out (in red).
- The active route (Dashboard on `/`) shows the left accent bar + tint.

- [ ] **Step 4: Verify gestures**

- `take_snapshot`, then drag the sheet down: use `drag` from a point inside the grip/header to a point ~300px lower. Expected: the sheet dismisses.
- Reopen, then click the dimmed backdrop area (a coordinate in the top ~20% of the viewport, above the sheet). Expected: dismisses.
- Reopen, click a nav row (e.g. Leads). Expected: navigates to `/leads` AND the sheet closes.

- [ ] **Step 5: Verify account actions (functional)**

- Open the sheet, click **Reset password**. Expected: sheet closes and the "Reset your password?" confirm `Dialog` appears (with the account email). Close it (Cancel).
- Open the sheet, click **Sign out**. Expected: sheet closes and the app signs out (returns to the auth/login screen). Sign back in to continue.

- [ ] **Step 6: Verify admin gating**

Confirm the **Admin** row appears for an admin user. Either log in as the admin, or simulate via `navigate_page` `initScript` that patches `window.fetch` to mark `/me` as admin (see memory `feedback_chrome_devtools_fetch_override_role_simulation`; append `?asuser=1` to force a fresh nav so the initScript runs). Expected: 4 nav rows incl. Admin for admin; 3 (no Admin, label "Create") for non-admin.

- [ ] **Step 7: Verify keyboard a11y + no regressions**

- With the sheet open, press Esc → closes. Tab through rows → each shows a visible inset focus ring.
- `list_console_messages` → no new errors.
- Resize to ≥768px (e.g. 1024×800), reload: confirm the **desktop** account dropdown + Dossier Requests pill render and the bottom sheet is not used (regression check).

**Fallback note (Step 3 scaling):** if the background does not scale, verify `data-vaul-drawer-wrapper=""` is on the root div (Task 2 Step 2) and that the element has a background (`bg-background`). If scaling causes a visual glitch (e.g. a black flash or clipped corners) and is undesirable, set `shouldScaleBackground={false}` on the `Drawer` in `MobileNavSheet.tsx` and rebuild — the sheet + gestures still work without the scale effect.

---

## Task 4 (optional, after user confirmation): Promote to Production

**Files:** none (console migration).

- [ ] **Step 1: Confirm with the user** before touching Prod.

- [ ] **Step 2: Promote** via a gate-free **Web Client Hosting** Dev→Prod migration (Settings → Environments → Deployments → Create Deployment → Web Client Hosting only; Data Store and SignIn Method diffs should be 0). See memory `reference_catalyst_dev_to_prod_promotion`.

- [ ] **Step 3: Verify on the live Prod app** (`https://lead-insight-hub-60066539659.catalystserverless.in/app/`) at mobile width: repeat Task 3 Steps 3–5.

---

## Self-Review

**Spec coverage:**
- Bottom sheet at content height → Task 1 (`DrawerContent`, no forced height) ✓
- vaul gestures (drag/flick/backdrop/esc) → Task 1 (vaul defaults) + Task 3 Step 4 ✓
- Background dim + scale → Task 2 Step 2 (`data-vaul-drawer-wrapper`) + explicit `shouldScaleBackground` ✓
- Identity → nav → divided account actions; Sign out red → Task 1 ✓
- Active route = accent bar + tint + `aria-current` → Task 1 ✓
- Admin-only Admin row; Upload-vs-Create label → Task 1 `navItems`; verified Task 3 Step 6 ✓
- Reuse reset `Dialog` / `signOut` / `isActive` via props → Task 1 interface + Task 2 Step 3 wiring ✓
- Desktop untouched; `md:hidden` trigger → Task 2 Step 3; regression check Task 3 Step 7 ✓
- A11y (dialog name, focus rings, ≥44px, Esc) → Task 1 (`DrawerTitle` sr-only, focus-visible rings, `py-3.5`) + Task 3 Step 7 ✓
- Drawer.tsx via per-instance className, not edited → Task 1 (className overrides), file unchanged ✓
- Build/type-check verification → Tasks 1–2 (`tsc --noEmit`, `npm run build`) ✓
- Deployment (Dev then gate-free Prod) → Tasks 3–4 ✓

**Placeholder scan:** No TBD/TODO; all steps include exact code or exact commands. ✓

**Type/name consistency:** `MobileNavSheetProps` fields (`open`, `onOpenChange`, `display`, `accountEmail`, `initials`, `isAdmin`, `isActive`, `onResetPassword`, `onSignOut`) match the JSX props passed in Task 2 Step 3 exactly. Imports added in Task 2 (`MobileNavSheet`) and removed (`Sheet*`, `X`, `ChevronRight`) are consistent with usage. ✓
