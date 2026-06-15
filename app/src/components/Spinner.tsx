// Crisp symmetric ring spinner — a complete circle with one accent arc (see
// .spinner-ring in styles.css). Replaces the small lucide Loader2 arc, whose
// thin rounded stroke-caps shimmered/"shook" when spun at small sizes on
// fractional display scaling (Windows 125%/150%). Size it with h-/w- utility
// classes; the colour follows `currentColor`, so it inherits text colour just
// like the lucide icon did.
export function Spinner({ className = "" }: { className?: string }) {
  return <span className={`spinner-ring ${className}`} aria-hidden />;
}
