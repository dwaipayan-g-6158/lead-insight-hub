import { useMounted } from "@/hooks/use-mounted";

/** Reusable dimension progress bar (Fit, Intent, Timing, Budget). */
export function DimensionBar({
  label,
  score,
  max,
}: {
  label: string;
  score: number | null;
  max: number | null;
}) {
  const hasScore = score != null && max != null;
  const pct = hasScore ? Math.round((score / max) * 100) : 0;
  const mounted = useMounted();

  return (
    <div>
      <div className="flex items-baseline justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        {hasScore ? (
          <span className="font-medium tabular-nums">
            {score}
            <span className="text-muted-foreground"> / {max}</span>
          </span>
        ) : (
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground/60">
            Not scored
          </span>
        )}
      </div>
      <div className="h-1.5 rounded bg-muted mt-1 overflow-hidden">
        <div
          className={`h-full bar-fill ${hasScore ? "bg-primary" : "bg-muted-foreground/20"}`}
          style={{ width: `${mounted && hasScore ? pct : 0}%` }}
        />
      </div>
    </div>
  );
}
