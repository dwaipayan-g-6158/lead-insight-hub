import { useMemo, type CSSProperties } from "react";

// CSS-only celebratory confetti. Mounted briefly when a dossier completes, then
// unmounted by the parent. Purely decorative: a fixed full-viewport overlay,
// aria-hidden + pointer-events:none so it never affects layout, hit-testing or
// the a11y tree. Each piece gets randomised CSS custom props (start column,
// horizontal drift, rotation, size, colour, duration, delay) — mirrors the
// HeavySparkles approach in AppShell. styles.css (.lih-confetti*) animates them
// and suppresses the whole overlay under prefers-reduced-motion.
const COLORS = [
  "#a78bfa",
  "#7c5cff",
  "#fde68a",
  "#34d399",
  "#60a5fa",
  "#f472b6",
  "#ffffff",
];

export function ConfettiBurst({ pieces = 90 }: { pieces?: number }) {
  const bits = useMemo(
    () =>
      Array.from({ length: pieces }, (_, i) => {
        const left = Math.random() * 100; // vw start column
        const dx = (Math.random() * 2 - 1) * 140; // horizontal drift px
        const rot = Math.round(180 + Math.random() * 600);
        const dur = 1.7 + Math.random() * 1.3;
        const delay = Math.random() * 0.3;
        const sz = 6 + Math.random() * 8;
        return {
          "--cx": `${left.toFixed(2)}vw`,
          "--dx": `${dx.toFixed(0)}px`,
          "--rot": `${rot}deg`,
          "--dur": `${dur.toFixed(2)}s`,
          "--delay": `${delay.toFixed(2)}s`,
          "--sz": `${sz.toFixed(1)}px`,
          "--c": COLORS[i % COLORS.length],
          "--o": (0.55 + Math.random() * 0.45).toFixed(2),
        } as CSSProperties;
      }),
    [pieces],
  );
  return (
    <div className="lih-confetti" aria-hidden>
      {bits.map((style, i) => (
        <span key={i} className="lih-confetti-piece" style={style} />
      ))}
    </div>
  );
}
