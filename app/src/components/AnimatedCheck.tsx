// A success checkmark that draws itself in (circle then tick) via
// stroke-dashoffset. Used as the icon of the "Dossier ready" toast. Keyframes
// live in styles.css (.lih-check-circle / .lih-check-mark) and collapse to an
// instant draw under prefers-reduced-motion.
export function AnimatedCheck({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      width="20"
      height="20"
      fill="none"
      aria-hidden
    >
      <circle
        className="lih-check-circle"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="2"
      />
      <path
        className="lih-check-mark"
        d="M7 12.5l3.2 3.2L17 9"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
