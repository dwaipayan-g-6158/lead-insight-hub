// Runtime environment detection for completion-feedback gating. The success
// chime and OS desktop notification are reserved for a desktop *browser tab*:
// they are removed on phones (small viewport) and inside an installed PWA —
// including a PWA installed on a desktop. Plain (non-React) functions so both
// notify.ts effects and React components share one definition of "desktop".

// Mirrors MOBILE_BREAKPOINT in hooks/use-mobile.tsx — keep the two in sync.
export const DESKTOP_MIN_WIDTH = 768;

/**
 * True when running as an installed standalone PWA — the display-mode media
 * query (Chromium/Android/desktop installs) OR the iOS-Safari legacy
 * navigator.standalone flag.
 */
export function isStandalonePWA(): boolean {
  if (typeof window === "undefined") return false;
  try {
    const mql = window.matchMedia?.("(display-mode: standalone)")?.matches ?? false;
    const ios = (window.navigator as { standalone?: boolean }).standalone === true;
    return mql || ios;
  } catch {
    return false;
  }
}

/**
 * True only in a desktop browser tab: NOT a standalone PWA AND viewport width
 * >= DESKTOP_MIN_WIDTH. This is the single gate for the success chime and the
 * OS desktop notification.
 */
export function isDesktopEnv(): boolean {
  if (typeof window === "undefined") return false;
  if (isStandalonePWA()) return false;
  try {
    return (
      window.matchMedia?.(`(min-width: ${DESKTOP_MIN_WIDTH}px)`)?.matches ??
      window.innerWidth >= DESKTOP_MIN_WIDTH
    );
  } catch {
    return window.innerWidth >= DESKTOP_MIN_WIDTH;
  }
}
