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
  const pct = score != null && max ? Math.round((score / max) * 100) : 0;

  return (
    <div>
      <div className="flex justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium">
          {score ?? "â€”"}
          {max ? ` / ${max}` : ""}
        </span>
      </div>
      <div className="h-1.5 rounded bg-muted mt-1 overflow-hidden">
        <div className="h-full bg-primary" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
