import { useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";
import { toast } from "sonner";
import { Activity, ChevronDown, Loader2, RefreshCw, X } from "lucide-react";

import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { activeCellLabel } from "@/components/StageStrip";
import {
  ApiError,
  clearAllTerminalRequests,
  clearDossierRequest,
  createDossierRequest,
  listDossierRequests,
} from "@/lib/api";
import { useDossierActivity } from "@/lib/dossier-activity";
import {
  isTerminal,
  STAGE_LABELS,
  type DossierRequest,
  type DossierRequestStage,
} from "@/types/dossier-requests";

const POLL_INTERVAL_MS = 10000;

// Maps the raw server error_message to a one-line user-facing label.
// The full original message stays in the row's `title` attribute (tooltip)
// so power users / support can still see it on hover.
//
// RR branches are split by cause because the generic "Enrichment failed —
// RocketReach" was misleading: coverage gaps (no data for this org), auth
// failures, and rate-limits all hit the same label even though they require
// different operator action. Coverage gaps no longer reach this function —
// the pipeline auto-degrades to OSINT-only and marks the row "partial"
// (handled in the row renderer below, not here).
function friendlyErrorLabel(raw: string | null | undefined): string {
  if (!raw) return "Generation failed";
  const s = String(raw).toLowerCase();
  if (s.includes("extra data") || s.includes("json")) return "Generation failed — response format issue";
  if (s.includes("rocketreach auth") || s.includes("unauthorized") || s.includes("rr_api_key")) return "RocketReach auth error";
  if (s.includes("rocketreach rate") || s.includes("rate-limited") || s.includes("rate limit")) return "RocketReach rate-limited — try again";
  if (s.includes("rocketreach") || s.includes("rr ") || s.includes("rr_")) return "RocketReach error";
  if (s.includes("anthropic") || s.includes("api key") || s.includes("credit")) return "LLM service error";
  if (s.includes("timeout") || s.includes("timed out") || s.includes("exceeded") || s.includes("stalled")) return "Timed out — try again";
  if (s.includes("synthesis")) return "Synthesis failed";
  if (s.includes("rendering") || s.includes("render")) return "Rendering failed";
  return "Generation failed";
}

export function ActiveRequestsPill() {
  const { openActivity } = useDossierActivity();
  const [requests, setRequests] = useState<DossierRequest[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [paused, setPaused] = useState(false);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [clearingId, setClearingId] = useState<string | null>(null);
  const [clearingAll, setClearingAll] = useState(false);
  const [refreshNonce, setRefreshNonce] = useState(0);

  useEffect(() => {
    let cancelled = false;

    const tick = async () => {
      try {
        setLoading(true);
        const res = await listDossierRequests({});
        if (cancelled) return;
        const recent = res.requests.slice(0, 20);
        setRequests(recent);
        const anyLive = recent.some((r) => !isTerminal(r.status));
        if (!anyLive) setPaused(true);
        else setPaused(false);
      } catch (e) {
        // Auth errors are noisy here — swallow.
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    tick();

    let intervalId: ReturnType<typeof setInterval> | null = null;
    if (!paused) {
      intervalId = setInterval(tick, POLL_INTERVAL_MS);
    }
    return () => {
      cancelled = true;
      if (intervalId) clearInterval(intervalId);
    };
  }, [paused, refreshNonce]);

  useEffect(() => {
    if (open) setPaused(false);
  }, [open]);

  const handleRetry = async (request: DossierRequest) => {
    setRetryingId(request.id);
    try {
      const payload: Record<string, string> = {};
      if (request.intake_name) payload.name = request.intake_name;
      if (request.intake_email) payload.email = request.intake_email;
      if (request.intake_linkedin_url) payload.linkedin_url = request.intake_linkedin_url;
      if (request.intake_company_url) payload.company_url = request.intake_company_url;
      if (request.intake_notes) payload.notes = request.intake_notes;
      await createDossierRequest({ data: payload });
      toast.success("Retry submitted");
      setRefreshNonce((n) => n + 1);
    } catch (e) {
      // 409 dedup — typed via ApiError now; surface as info, refresh pill.
      if (
        e instanceof ApiError &&
        e.status === 409 &&
        e.payload?.error === "duplicate_in_flight"
      ) {
        toast.info("Already in progress for this person");
        setRefreshNonce((n) => n + 1);
      } else {
        const msg = e instanceof Error ? e.message : "Retry failed";
        toast.error(msg);
      }
    } finally {
      setRetryingId(null);
    }
  };

  const handleClearOne = async (request: DossierRequest) => {
    setClearingId(request.id);
    // Optimistic: drop from the list immediately so the row disappears on
    // click. The next poll/refresh will reconcile if the server rejects.
    setRequests((prev) => prev.filter((r) => r.id !== request.id));
    try {
      await clearDossierRequest({ data: { id: request.id } });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Clear failed";
      toast.error(msg);
      // Roll back by forcing a refetch — cheap and avoids reordering bugs.
      setRefreshNonce((n) => n + 1);
    } finally {
      setClearingId(null);
    }
  };

  const handleClearAll = async () => {
    setClearingAll(true);
    // Optimistic: hide every terminal row immediately. Live rows stay.
    setRequests((prev) => prev.filter((r) => !isTerminal(r.status)));
    try {
      await clearAllTerminalRequests();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Clear failed";
      toast.error(msg);
      setRefreshNonce((n) => n + 1);
    } finally {
      setClearingAll(false);
    }
  };

  // Live-stage info for the pill label. Server returns newest first, so
  // position [0] of the in-flight slice is the most recent live request.
  const liveLeader = requests.find((r) => !isTerminal(r.status)) ?? null;
  const liveCount = requests.filter((r) => !isTerminal(r.status)).length;
  const terminalCount = requests.length - liveCount;
  const liveCellInfo = liveLeader
    ? activeCellLabel(liveLeader.stage, liveLeader.status)
    : null;

  const handleOpenLive = (request: DossierRequest) => {
    setOpen(false);
    openActivity(request.id);
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={
            liveCount > 0
              ? `${liveCount} dossier${liveCount === 1 ? "" : "s"} in progress`
              : "Dossier requests"
          }
          className={`relative inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors ${
            liveCount > 0
              ? "border-primary/40 bg-primary/10 text-primary hover:bg-primary/15"
              : "border-border bg-card/60 text-muted-foreground hover:text-foreground"
          }`}
        >
          {liveCount > 0 ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Activity className="h-3.5 w-3.5" />
          )}
          {liveCount > 0 && liveCellInfo ? (
            <span className="inline-flex items-center gap-1 font-medium">
              <span className="text-muted-foreground/80">Dossier Requests:</span>
              <span className="max-w-[8rem] truncate uppercase tracking-wide">
                {liveCellInfo.label}
              </span>
              <span className="text-muted-foreground/80">
                {liveCellInfo.index}/{liveCellInfo.total}
              </span>
            </span>
          ) : (
            <span className="font-medium">Dossier Requests</span>
          )}
          <ChevronDown className="h-3 w-3 opacity-70" />
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 p-0">
        <div className="flex items-center justify-between px-3 py-2 border-b">
          <div className="text-xs uppercase tracking-wider text-muted-foreground">
            Recent activity
          </div>
          {terminalCount > 0 && (
            <button
              type="button"
              onClick={handleClearAll}
              disabled={clearingAll}
              className="text-[11px] text-muted-foreground hover:text-foreground disabled:opacity-50 cursor-pointer"
              title="Remove every completed entry from this list (leads are not deleted)"
            >
              {clearingAll ? "Clearing…" : "Clear all"}
            </button>
          )}
        </div>
        <ul className="max-h-80 overflow-y-auto divide-y">
          {requests.length === 0 && !loading && (
            <li className="px-3 py-4 text-xs text-muted-foreground text-center">
              No recent requests.
            </li>
          )}
          {requests.length === 0 && loading && (
            <li className="px-3 py-4 text-xs text-muted-foreground text-center">
              Loading…
            </li>
          )}
          {requests.map((r) => (
            <RequestRow
              key={r.id}
              request={r}
              onNavigate={() => setOpen(false)}
              onRetry={handleRetry}
              onOpenLive={handleOpenLive}
              onClear={handleClearOne}
              retrying={retryingId === r.id}
              clearing={clearingId === r.id}
            />
          ))}
        </ul>
      </PopoverContent>
    </Popover>
  );
}

function RequestRow({
  request,
  onNavigate,
  onRetry,
  onOpenLive,
  onClear,
  retrying,
  clearing,
}: {
  request: DossierRequest;
  onNavigate: () => void;
  onRetry: (r: DossierRequest) => void;
  onOpenLive: (r: DossierRequest) => void;
  onClear: (r: DossierRequest) => void;
  retrying: boolean;
  clearing: boolean;
}) {
  const live = !isTerminal(request.status);
  const title =
    request.intake_name ||
    request.intake_email ||
    request.intake_linkedin_url ||
    request.intake_company_url ||
    "Untitled lead";

  const partialLabel = request.rr_degraded
    ? request.rr_degradation_reason === "rr_full_miss"
      ? "OSINT-only — no RocketReach data for this org"
      : "OSINT-only — RocketReach firmographics missing"
    : "Saved with warnings";
  const sub = live
    ? request.stage
      ? STAGE_LABELS[request.stage as DossierRequestStage]
      : "Queued"
    : request.status === "succeeded"
      ? "Ready"
      : request.status === "partial"
        ? partialLabel
        : request.status === "failed"
          ? friendlyErrorLabel(request.error_message)
          : "Cancelled";

  const subTitle = request.status === "failed"
    ? (request.error_message || undefined)
    : request.status === "partial" && request.rr_degraded
      ? "RocketReach has no record of this organization — common for .gov/.edu/non-profit prospects. The dossier was generated from web search and preflight only; review carefully before sending outreach."
      : undefined;

  const dotClass = live
    ? "bg-primary animate-pulse"
    : request.status === "succeeded"
      ? "bg-emerald-500"
      : request.status === "partial"
        ? "bg-amber-500"
        : request.status === "failed"
          ? "bg-destructive"
          : "bg-muted-foreground/40";

  const isRetryable = request.status === "failed" && Boolean(
    request.intake_name ||
      request.intake_email ||
      request.intake_linkedin_url ||
      request.intake_company_url,
  );

  const inner = (
    <div className="flex items-start gap-2 px-3 py-2">
      <span
        aria-hidden
        className={`mt-1 h-1.5 w-1.5 rounded-full shrink-0 ${dotClass}`}
      />
      <div className="flex-1 min-w-0">
        <div className="text-sm truncate">{title}</div>
        <div
          className="text-[11px] text-muted-foreground truncate"
          title={subTitle}
        >
          {sub}
        </div>
      </div>
      {isRetryable && (
        <button
          type="button"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onRetry(request);
          }}
          disabled={retrying}
          className="shrink-0 inline-flex items-center gap-1 rounded-md border border-border/60 px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-muted-foreground hover:text-foreground hover:border-border disabled:opacity-50 cursor-pointer"
          title="Re-submit this request"
        >
          {retrying ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <RefreshCw className="h-3 w-3" />
          )}
          Retry
        </button>
      )}
      {/* Per-row clear (× button) — only on terminal rows. Live rows still
          need to finish, so deleting them would orphan the running Job. */}
      {!live && (
        <button
          type="button"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onClear(request);
          }}
          disabled={clearing}
          aria-label="Remove from recent activity"
          title="Remove from recent activity (lead is not deleted)"
          className="shrink-0 inline-flex items-center justify-center rounded-md border border-transparent p-0.5 text-muted-foreground hover:text-foreground hover:border-border/60 disabled:opacity-50 cursor-pointer"
        >
          {clearing ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <X className="h-3.5 w-3.5" />
          )}
        </button>
      )}
    </div>
  );

  // Live rows: clicking anywhere on the row re-opens the activity popup
  // for THIS specific request. (No retry button is shown on live rows,
  // so the whole row is a safe click target.)
  if (live) {
    return (
      <li>
        <button
          type="button"
          onClick={() => onOpenLive(request)}
          className="block w-full text-left hover:bg-accent/40 focus-visible:bg-accent/40 focus-visible:outline-none cursor-pointer"
        >
          {inner}
        </button>
      </li>
    );
  }
  if (request.lead_id) {
    return (
      <li>
        <Link
          to="/leads/$leadId"
          params={{ leadId: String(request.lead_id) }}
          onClick={onNavigate}
          className="block hover:bg-accent/40 focus-visible:bg-accent/40 focus-visible:outline-none"
        >
          {inner}
        </Link>
      </li>
    );
  }
  return <li>{inner}</li>;
}
