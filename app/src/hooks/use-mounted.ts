import { useEffect, useState } from "react";

/**
 * Returns `true` after the component has committed its first paint.
 * Useful for triggering CSS width/transform transitions on mount
 * (render at the "from" state, then flip to the "to" state).
 *
 * Optional `delay` (ms) lets callers cascade multiple bars/widgets.
 */
export function useMounted(delay = 0): boolean {
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    if (delay <= 0) {
      // Wait one frame so the initial 0% width is painted first.
      const id = requestAnimationFrame(() => setMounted(true));
      return () => cancelAnimationFrame(id);
    }
    const t = setTimeout(() => setMounted(true), delay);
    return () => clearTimeout(t);
  }, [delay]);
  return mounted;
}
