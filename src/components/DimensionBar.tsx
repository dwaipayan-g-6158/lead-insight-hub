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
  const pct = score != null && max ? Math.round((score / max) * 100) : 0;
  const mounted = useMounted();

  return (
    <div>
      <div className="flex justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium">
          {score ?? "—"}
          {max ? ` / ${max}` : ""}
        </span>
      </div>
      <div className="h-1.5 rounded bg-muted mt-1 overflow-hidden">
        <div
          className="h-full bg-primary bar-fill"
          style={{ width: `${mounted ? pct : 0}%` }}
        />
      </div>
    </div>
  );
}
