import { Check, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import type {
  DossierRequestStage,
  DossierRequestStatus,
} from "@/types/dossier-requests";

// The visible strip groups backend stages into 6 spec-defined cells.
// Two backend stages collapse into single cells:
//   synthesis + synthesis_retry  -> "RESEARCHING"
//   rendering + lint             -> "RENDERING / VERIFYING"
type Cell = {
  key: string;
  label: string;
  backendStages: DossierRequestStage[];
};

const CELLS: Cell[] = [
  { key: "queued", label: "QUEUED", backendStages: ["queued"] },
  { key: "preflight", label: "PREFLIGHT", backendStages: ["preflight"] },
  { key: "enriching", label: "ENRICHING", backendStages: ["rocketreach"] },
  {
    key: "researching",
    label: "RESEARCHING",
    backendStages: ["synthesis", "synthesis_retry"],
  },
  {
    key: "rendering",
    label: "RENDERING / VERIFYING",
    backendStages: ["rendering", "lint"],
  },
  { key: "saving", label: "SAVING", backendStages: ["upload"] },
];

type CellState = "done" | "active" | "failed" | "pending";

function cellIndexForStage(stage: DossierRequestStage | null): number {
  if (!stage) return 0;
  if (stage === "done") return CELLS.length;
  if (stage === "error") return -1;
  return CELLS.findIndex((c) =>
    c.backendStages.includes(stage as DossierRequestStage),
  );
}

function computeCellState(
  cellIdx: number,
  activeIdx: number,
  status: DossierRequestStatus,
  stage: DossierRequestStage | null,
): CellState {
  // Terminal success → every cell is done.
  if (
    status === "succeeded" ||
    status === "partial" ||
    stage === "done"
  ) {
    return "done";
  }

  // Failure → pills passed are done, the cell where it failed turns red.
  // If we lost the stage (error/null), the active index falls back to
  // whatever was in progress most recently.
  if (status === "failed" || stage === "error") {
    const failIdx = activeIdx < 0 ? 0 : activeIdx;
    if (cellIdx < failIdx) return "done";
    if (cellIdx === failIdx) return "failed";
    return "pending";
  }

  if (status === "cancelled") {
    return cellIdx < activeIdx ? "done" : "pending";
  }

  // Live: pending → running.
  if (cellIdx < activeIdx) return "done";
  if (cellIdx === activeIdx) return "active";
  return "pending";
}

type Props = {
  stage: DossierRequestStage | null;
  status: DossierRequestStatus;
  size?: "default" | "compact";
  className?: string;
};

export function StageStrip({
  stage,
  status,
  size = "default",
  className,
}: Props) {
  const activeIdx = cellIndexForStage(stage);
  const isRetry = stage === "synthesis_retry";
  const compact = size === "compact";

  return (
    <ol
      aria-label="Dossier creation stages"
      className={cn(
        "flex flex-wrap items-center",
        compact ? "gap-x-1 gap-y-1" : "gap-x-1.5 gap-y-2",
        className,
      )}
    >
      {CELLS.map((cell, idx) => {
        const state = computeCellState(idx, activeIdx, status, stage);
        const isLast = idx === CELLS.length - 1;
        const showRetryTag = isRetry && cell.key === "researching" && state === "active";

        return (
          <li
            key={cell.key}
            aria-current={state === "active" ? "step" : undefined}
            className="flex items-center"
          >
            <span
              className={cn(
                "inline-flex items-center rounded-full font-medium tracking-wide",
                compact
                  ? "gap-1 px-2 py-0.5 text-[10px]"
                  : "gap-1.5 px-2.5 py-1 text-[11px]",
                pillClassForState(state),
              )}
            >
              {state === "done" && (
                <Check
                  className={compact ? "h-2.5 w-2.5" : "h-3 w-3"}
                  aria-hidden
                />
              )}
              {state === "active" && (
                <span
                  aria-hidden
                  className={cn(
                    "inline-block rounded-full bg-current",
                    compact ? "h-1 w-1" : "h-1.5 w-1.5",
                    "animate-pulse",
                  )}
                />
              )}
              <span className="uppercase">{cell.label}</span>
              {showRetryTag && (
                <span className="ml-0.5 normal-case lowercase opacity-70">
                  (retry)
                </span>
              )}
            </span>
            {!isLast && (
              <ChevronRight
                aria-hidden
                className={cn(
                  "shrink-0 text-muted-foreground/40",
                  compact ? "mx-0.5 h-3 w-3" : "mx-0.5 h-3.5 w-3.5",
                )}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}

function pillClassForState(state: CellState): string {
  switch (state) {
    case "done":
      return "bg-emerald-100 text-emerald-700 ring-1 ring-emerald-200 dark:bg-emerald-500/15 dark:text-emerald-300 dark:ring-emerald-500/30";
    case "active":
      return "bg-primary/15 text-primary ring-2 ring-primary/30 animate-pulse";
    case "failed":
      return "bg-destructive/15 text-destructive ring-2 ring-destructive/30";
    case "pending":
    default:
      return "bg-muted text-muted-foreground ring-1 ring-border/60";
  }
}

// Helper exported for callers that need to render a short live indicator
// elsewhere (e.g. the header trigger button).
export function activeCellLabel(
  stage: DossierRequestStage | null,
  status: DossierRequestStatus,
): { label: string; index: number; total: number } | null {
  if (status === "succeeded" || status === "partial" || stage === "done") {
    return { label: "Complete", index: CELLS.length, total: CELLS.length };
  }
  if (status === "failed" || stage === "error") {
    return { label: "Failed", index: 0, total: CELLS.length };
  }
  const idx = cellIndexForStage(stage);
  const safeIdx = idx < 0 || idx >= CELLS.length ? 0 : idx;
  return {
    label: CELLS[safeIdx].label,
    index: safeIdx + 1,
    total: CELLS.length,
  };
}
