import { useEffect, useState } from "react";

/**
 * Animates a number from 0 → `target` over `duration` ms using an
 * ease-out-cubic curve. Respects `prefers-reduced-motion`. Re-runs
 * whenever `target` changes.
 */
export function useCountUp(target: number, duration = 900): number {
  const [value, setValue] = useState(target === 0 ? 0 : 0);

  useEffect(() => {
    if (typeof window === "undefined") {
      setValue(target);
      return;
    }
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced || duration <= 0 || target === 0) {
      setValue(target);
      return;
    }
    let raf = 0;
    const start = performance.now();
    const from = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(Math.round(from + (target - from) * eased));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);

  return value;
}
