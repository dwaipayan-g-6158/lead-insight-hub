# Mobile Bottom-Sheet Navigation Menu — Design

**Date:** 2026-06-02
**Status:** Approved (design); pending implementation plan
**Scope:** Mobile (`<md`) navigation menu in `app/src/components/AppShell.tsx` only. Desktop is untouched.

## Context

The current mobile menu is a gesture-less Radix `Sheet` that slides in from the right (`AppShell.tsx`, the `Sheet`/`SheetContent` block). The user's feedback: it "doesn't look like a mobile app," the account actions feel awkwardly placed, and there are no touch gestures. They asked for a native, app-like menu (Gmail iOS and similar as inspiration) with slide gestures.

Decisions reached during brainstorming:
- **Paradigm:** a **bottom sheet** (not a left/right side drawer). Chosen for the most native modern-app feel (Apple/Google Maps, Files, etc.).
- **Height:** **content height** — the sheet rises just enough to fit its ~5 rows, reading as a crisp iOS action sheet with no empty space.
- **Gestures:** real drag/flick via **`vaul`** (already a dependency; a `drawer.tsx` wrapper already exists in the repo).
- **Implementation:** extract a small, self-contained `MobileNavSheet` component; drop it into `AppShell` behind the `md:hidden` breakpoint; adjust `drawer.tsx` content styles for a top-rounded, content-height, safe-area-aware sheet. Reuse the existing reset `Dialog` and the `signOut` / `isAdmin` / nav-item logic as-is.

**Intended outcome:** a polished, gesture-driven bottom-sheet menu on mobile that matches native app conventions, with the account actions cleanly grouped — and zero change to the desktop experience.

## Existing pieces to reuse (do not rebuild)

- **`vaul` `^1.1.2`** — drag-gesture drawer lib (momentum, velocity-snap, background scaling). Already installed.
- **`app/src/components/ui/drawer.tsx`** — shadcn/vaul wrapper. Currently styled as a bottom sheet (`rounded-t-[10px]`, grip handle, `shouldScaleBackground` default true). Present but unused elsewhere.
- **`AppShell.tsx` internals** — `useAuth()` (`user`, `signOut`, `isAdmin`, `heavyAllowed`), the `display` / `initials` / `accountEmail` derivations, the shared reset-password `Dialog` + `confirmReset`, and the nav-item list (`/`, `/leads`, `/upload`, `/admin`). All reused unchanged.

## Components

### `MobileNavSheet` (new) — `app/src/components/MobileNavSheet.tsx`

A self-contained component owning only the mobile menu's structure. Props (kept minimal, passing already-derived values rather than re-deriving):

```
interface MobileNavSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  display: string;          // full name or email fallback
  accountEmail: string;
  initials: string;
  isAdmin: boolean;
  isActive: (path: string) => boolean;
  onResetPassword: () => void;   // sets resetOpen=true in AppShell
  onSignOut: () => void;         // signOut()
}
```

Internally renders a `vaul` `Drawer` (via `drawer.tsx` primitives) containing, top→bottom:

1. **Grab handle** — the existing grip pill from `DrawerContent`.
2. **Identity header** — avatar (initials, `bg-primary/25` circle), `display`, `accountEmail`. Bottom border.
3. **Nav rows** — Dashboard / Leads / (Upload if admin else Create) / Admin (admin-only). Each: full-width `<Link>`, left-aligned icon (`h-5 w-5`) + label, **active state = left accent bar + `bg-primary/15` tint** (no chevron). Tapping navigates and closes the sheet (wrap in `DrawerClose asChild`, mirroring today's `SheetClose` pattern).
4. **Divider + account actions** — `Reset password` row (calls `onResetPassword`, closes sheet) and `Sign out` row in **destructive red** (`text-destructive`, calls `onSignOut`, closes sheet). Same full-bleed list-row styling as the nav rows.
5. **Bottom safe-area padding** (`pb-[env(safe-area-inset-bottom)]`).

The trigger (hamburger `Button`) stays in `AppShell` and controls `open` via `onOpenChange`, matching the current `mobileOpen` state wiring.

### `drawer.tsx` adjustments

The shared wrapper is currently fine as a bottom sheet but tuned for a generic drawer. Adjust `DrawerContent` (or pass `className` overrides from `MobileNavSheet` to avoid changing shared defaults) so this sheet has:
- top corners `rounded-t-2xl`, top border,
- **content height** (no forced `mt-24`/min-height that creates empty space),
- `max-h-[90vh]` guard with internal scroll if content ever exceeds it,
- bottom safe-area inset.

Prefer **per-instance `className` overrides** from `MobileNavSheet` over editing `drawer.tsx` defaults, unless a change is clearly generic — `drawer.tsx` is shared and should stay reusable.

### `AppShell.tsx` changes

- Remove the mobile `Sheet` / `SheetContent` block (the nav rows + footer buttons).
- Keep the hamburger `Button` as the trigger; render `<MobileNavSheet ... />` behind the existing `md:hidden` breakpoint, wired to `mobileOpen` / `setMobileOpen`.
- Pass `onResetPassword={() => { setMobileOpen(false); setResetOpen(true); }}` and `onSignOut={() => { setMobileOpen(false); signOut(); }}`.
- The desktop dropdown, the `ActiveRequestsPill`, the reset `Dialog`, and the logo 5-tap heavy-unlock logic are all left exactly as-is.
- `Sheet` imports become unused once the block is removed — drop them (keep `Dialog`, `Button`, etc.).

## Data flow

`useAuth()` (in `AppShell`) → derived `display`/`initials`/`accountEmail`/`isAdmin` → passed as props to `MobileNavSheet`. Open state lives in `AppShell` (`mobileOpen`). Reset/sign-out callbacks close the sheet then delegate to existing `AppShell` handlers (`setResetOpen(true)`, `signOut()`). The reset `Dialog` remains rendered in `AppShell` as a sibling so closing the sheet never unmounts it (same reasoning as today).

## Gestures & behavior

- **Open:** tap hamburger. (No bottom-edge swipe-to-open — it conflicts with the iOS home-indicator gesture.)
- **Dismiss:** drag/flick down, tap backdrop, tap a nav row, or Esc — all via vaul defaults.
- **Background:** `shouldScaleBackground` dims + scales the app behind the sheet.
- **Reduced motion:** vaul honors `prefers-reduced-motion`; no extra work expected, verify in testing.

## Accessibility

- Drawer uses vaul's dialog semantics (focus trap, Esc, `aria-modal`). Keep a `DrawerTitle` (visually hidden if not shown) so the dialog has an accessible name.
- Nav rows are real `<Link>`s; action rows are real `<button>`s, each with a visible `focus-visible` ring (`ring-2 ring-inset ring-primary`) for keyboard users.
- Touch targets ≥ 44px (rows use `py-3.5` ≈ 52px).
- Active route conveyed by more than color (accent bar + tint + `aria-current` on the active link).

## Testing / verification

1. **Build:** `npm run build` in `app/` compiles clean (no TS/Vite errors); unused `Sheet` imports removed.
2. **Visual (chrome-devtools, ~390px, deployed to Dev):**
   - Hamburger opens a bottom sheet at content height with rounded top + grip; dashboard dims/scales behind it.
   - Order: identity → Dashboard/Leads/Create(or Upload)/Admin → divider → Reset password → Sign out (red).
   - Active route shows the left accent bar + tint.
   - Admin row appears only for an admin user (verify via role simulation or an admin login).
3. **Gestures:** drag/flick down dismisses; tap backdrop dismisses; tap a nav row navigates **and** closes.
4. **Functional:** Reset password closes the sheet and opens the confirm `Dialog`; Sign out closes and signs out.
5. **A11y/keyboard:** Esc closes; Tab moves through rows with a visible focus ring; the dialog has an accessible name.
6. **No regression** to desktop (≥md): account dropdown, Dossier Requests pill, and the logo 5-tap behavior unchanged.

## Out of scope

- Surfacing Dossier Requests / activity on mobile (currently desktop-only).
- Any desktop change.
- The logo 5-tap ELISS-Heavy unlock behavior.

## Deployment

Web-client-only change → `catalyst deploy --only client` to Dev, then a gate-free **Web Client Hosting** migration Dev→Prod (no schema/auth diff). See memory `reference_catalyst_dev_to_prod_promotion` and `feedback_catalyst_client_deploy_split`. Confirm before promoting to Prod.
