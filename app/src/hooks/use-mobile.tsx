import * as React from "react";

import { isDesktopEnv } from "@/lib/platform";

const MOBILE_BREAKPOINT = 768;

export function useIsMobile() {
  const [isMobile, setIsMobile] = React.useState<boolean | undefined>(undefined);

  React.useEffect(() => {
    const mql = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`);
    const onChange = () => {
      setIsMobile(window.innerWidth < MOBILE_BREAKPOINT);
    };
    mql.addEventListener("change", onChange);
    setIsMobile(window.innerWidth < MOBILE_BREAKPOINT);
    return () => mql.removeEventListener("change", onChange);
  }, []);

  return !!isMobile;
}

/**
 * Reactive companion to lib/platform.ts isDesktopEnv(): true only in a desktop
 * browser tab (>= 768px AND not a standalone PWA). Re-evaluates on viewport
 * resize and display-mode change. Used to show/hide the desktop-only
 * completion-feedback toggles.
 */
export function useIsDesktopEnv() {
  const [isDesktop, setIsDesktop] = React.useState<boolean>(() => isDesktopEnv());

  React.useEffect(() => {
    const widthMql = window.matchMedia(`(min-width: ${MOBILE_BREAKPOINT}px)`);
    const standaloneMql = window.matchMedia("(display-mode: standalone)");
    const onChange = () => setIsDesktop(isDesktopEnv());
    widthMql.addEventListener("change", onChange);
    standaloneMql.addEventListener("change", onChange);
    onChange();
    return () => {
      widthMql.removeEventListener("change", onChange);
      standaloneMql.removeEventListener("change", onChange);
    };
  }, []);

  return isDesktop;
}
