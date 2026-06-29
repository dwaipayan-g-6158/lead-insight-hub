import { useEffect, useRef, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import {
  AlertCircle,
  CheckCircle2,
  Sparkles,
  X,
} from "lucide-react";
import { Spinner } from "@/components/Spinner";
import { AnimatedCheck } from "@/components/AnimatedCheck";
import { ConfettiBurst } from "@/components/ConfettiBurst";
import {
  notifyDossierReady,
  playSuccessChime,
  pulseActivityPill,
} from "@/lib/notify";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { StageStrip } from "@/components/StageStrip";
import { useDossierActivity } from "@/lib/dossier-activity";
import {
  ApiError,
  createDossierRequest,
  getDossierRequest,
} from "@/lib/api";
import {
  isTerminal,
  STAGE_LABELS,
  type DossierRequest,
  type DossierRequestStage,
} from "@/types/dossier-requests";

const POLL_INTERVAL_MS = 5000;

// The single source of truth for the "what's happening with this dossier"
// popup. Driven by the DossierActivityProvider context — opens whenever
// activeRequestId is non-null. Polls getDossierRequest for that id every
// 5s, mirrors the stage strip, and only dismisses on user action while
// the request is in flight.
export function DossierActivityPopup() {
  const { activeRequestId, closeActivity, openActivity } = useDossierActivity();
  const navigate = useNavigate();

  const [request, setRequest] = useState<DossierRequest | null>(null);
  const [retrying, setRetrying] = useState(false);
  // Transient flag that mounts the confetti overlay on success, cleared after
  // the burst finishes. Independent of the dialog open state so the celebration
  // still plays when the user ran the dossier "in background".
  const [celebrate, setCelebrate] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Track the last status we toasted on so completion notifications fire
  // exactly once per request lifecycle even if the popup re-opens after.
  const toastedKey = useRef<string | null>(null);
  // Track the last id we opened with so we can tell a fresh open from a
  // reopen-of-the-same-request from a close. Reopens of the same id keep
  // the prior `request` state visible; close doesn't touch state at all
  // (otherwise the dialog flashes "Connecting…" during Radix's close
  // animation while still mounted).
  const lastOpenedIdRef = useRef<string | null>(null);

  const open = activeRequestId !== null;
  const terminal = request ? isTerminal(request.status) : false;

  useEffect(() => {
    if (activeRequestId === null) return;
    if (lastOpenedIdRef.current === activeRequestId) return;
    lastOpenedIdRef.current = activeRequestId;
    setRequest(null);
    setRetrying(false);
  }, [activeRequestId]);

  // Poll for status while we have an in-flight request.
  useEffect(() => {
    if (!activeRequestId) {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }
    if (request && isTerminal(request.status)) {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }

    let cancelled = false;
    const tick = async () => {
      try {
        const res = await getDossierRequest({ data: { id: activeRequestId } });
        if (!cancelled) setRequest(res.request);
      } catch (e) {
        // Network blips during polling are non-fatal — keep the last-
        // known state and retry on the next tick.
        console.warn("[DossierActivityPopup] poll failed:", e);
      }
    };
    tick();
    pollRef.current = setInterval(tick, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [activeRequestId, request?.status]);

  // Fire a toast exactly once when a request transitions to terminal.
  // The key combines id + status so re-opening an already-terminal
  // request doesn't re-toast.
  useEffect(() => {
    if (!request) return;
    if (!isTerminal(request.status)) return;
    const key = `${request.id}:${request.status}`;
    if (toastedKey.current === key) return;
    toastedKey.current = key;
    // "partial" (dossier saved but degraded/thin) is treated as success — the
    // lead is saved and usable — so it shows the same "Dossier ready" toast and
    // celebration. Only two completion toasts exist: success and failure.
    if (
      (request.status === "succeeded" || request.status === "partial") &&
      request.lead_id
    ) {
      const name = request.intake_name || request.intake_email || "lead";
      toast.success(`Dossier ready: ${name}`, {
        icon: <AnimatedCheck className="text-emerald-500" />,
      });
      // Celebration signals: confetti + pill pulse always; sound (desktop only)
      // and desktop notification only if the user opted in (see lib/notify.ts).
      setCelebrate(false);
      requestAnimationFrame(() => setCelebrate(true));
      pulseActivityPill();
      playSuccessChime();
      notifyDossierReady(name, String(request.lead_id));
    } else if (request.status === "failed") {
      toast.error(request.error_message || "Generation failed");
    }
  }, [request?.status, request?.id, request?.lead_id]);

  // Unmount the confetti overlay after the burst has finished playing.
  useEffect(() => {
    if (!celebrate) return;
    const t = setTimeout(() => setCelebrate(false), 3200);
    return () => clearTimeout(t);
  }, [celebrate]);

  const handleViewDossier = () => {
    if (request?.lead_id) {
      navigate({
        to: "/leads/$leadId",
        params: { leadId: String(request.lead_id) },
      });
      closeActivity();
    }
  };

  const handleTryAgain = async () => {
    if (!request) return;
    const payload: Record<string, string> = {};
    if (request.intake_name) payload.name = request.intake_name;
    if (request.intake_email) payload.email = request.intake_email;
    if (request.intake_linkedin_url)
      payload.linkedin_url = request.intake_linkedin_url;
    if (request.intake_company_url)
      payload.company_url = request.intake_company_url;
    if (request.intake_notes) payload.notes = request.intake_notes;

    setRetrying(true);
    try {
      const res = await createDossierRequest({ data: payload });
      toast.success("Retry submitted");
      openActivity(res.request_id);
    } catch (e) {
      if (
        e instanceof ApiError &&
        e.status === 409 &&
        e.payload?.error === "duplicate_in_flight" &&
        e.payload?.request_id
      ) {
        toast.info("Already in progress for this person");
        openActivity(String(e.payload.request_id));
      } else {
        const msg = e instanceof Error ? e.message : "Retry failed";
        toast.error(msg);
      }
    } finally {
      setRetrying(false);
    }
  };

  return (
    <>
      {celebrate && <ConfettiBurst />}
      <Dialog
        open={open}
        onOpenChange={(next) => {
          if (!next) closeActivity();
        }}
      >
      <DialogContent
        className="sm:max-w-xl"
        hideClose={!terminal}
        flyTarget="#dossier-activity-pill"
        onPointerDownOutside={(e) => {
          if (!terminal) e.preventDefault();
        }}
        onEscapeKeyDown={(e) => {
          if (!terminal) e.preventDefault();
        }}
        onInteractOutside={(e) => {
          if (!terminal) e.preventDefault();
        }}
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            {terminal ? "Dossier activity" : "Dossier in progress"}
          </DialogTitle>
          <DialogDescription>
            {terminal
              ? "This dossier has finished. Close the popup or jump to the lead."
              : "Generation is in flight. Click “Run in background” to keep working — the dossier keeps building."}
          </DialogDescription>
        </DialogHeader>

        <ProgressBody
          request={request}
          retrying={retrying}
          onViewDossier={handleViewDossier}
          onTryAgain={handleTryAgain}
          onClose={closeActivity}
        />
        </DialogContent>
      </Dialog>
    </>
  );
}

function ProgressBody({
  request,
  retrying,
  onViewDossier,
  onTryAgain,
  onClose,
}: {
  request: DossierRequest | null;
  retrying: boolean;
  onViewDossier: () => void;
  onTryAgain: () => void;
  onClose: () => void;
}) {
  if (!request) {
    return (
      <div className="py-8 flex flex-col items-center gap-2 text-muted-foreground">
        <Spinner className="h-6 w-6" />
        <span className="text-sm">Connecting…</span>
      </div>
    );
  }

  const terminal = isTerminal(request.status);
  const isRetryPass = request.stage === "synthesis_retry";
  const title =
    request.intake_name ||
    request.intake_email ||
    request.intake_linkedin_url ||
    request.intake_company_url ||
    "Untitled lead";

  return (
    <div className="space-y-4 mt-1">
      {/* Lead title + stage strip */}
      <div className="space-y-3 rounded-md border bg-muted/30 px-3 py-3">
        <div className="flex items-baseline justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="text-sm font-medium truncate">{title}</div>
            {request.intake_email && request.intake_name && (
              <div className="text-xs text-muted-foreground truncate">
                {request.intake_email}
              </div>
            )}
          </div>
          <span className="shrink-0 text-[10px] uppercase tracking-wider text-muted-foreground">
            {request.status}
          </span>
        </div>
        <StageStrip stage={request.stage} status={request.status} />
      </div>

      {/* Status card */}
      {terminal ? (
        request.status === "succeeded" || request.status === "partial" ? (
          <div className="flex items-start gap-3 rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-3">
            <CheckCircle2 className="h-5 w-5 mt-0.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
            <div className="flex-1 space-y-1">
              <div className="text-sm font-medium flex items-center gap-2">
                {request.status === "partial"
                  ? request.rr_degraded
                    ? "Dossier saved (OSINT-only)"
                    : "Dossier saved with thin sections"
                  : "Dossier ready"}
                {request.rr_degraded && (
                  <span
                    className="inline-flex items-center rounded-full border border-amber-500/40 bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-amber-700 dark:text-amber-400"
                    title={
                      request.rr_degradation_reason === "rr_full_miss"
                        ? "RocketReach has no record of this organization — common for .gov/.edu/non-profit prospects"
                        : "RocketReach returned partial data — firmographics missing"
                    }
                  >
                    OSINT-only
                  </span>
                )}
              </div>
              <div className="text-xs text-muted-foreground">
                {request.intake_name || request.intake_email || "Lead"}
                {typeof request.tokens_input === "number" &&
                  typeof request.tokens_output === "number" && (
                    <>
                      {" · "}
                      {(
                        request.tokens_input + request.tokens_output
                      ).toLocaleString()}
                      {" tokens"}
                    </>
                  )}
                {typeof request.rr_calls === "number" && request.rr_calls > 0 && (
                  <> · {request.rr_calls} RR calls</>
                )}
              </div>
              {request.status === "partial" && request.rr_degraded && (
                <div className="text-xs text-amber-700 dark:text-amber-400 mt-1">
                  {request.rr_degradation_reason === "rr_full_miss"
                    ? "RocketReach has no record of this organization. All firmographics, contact data, and DMU intelligence were sourced from web search and preflight only — review carefully before sending outreach."
                    : "RocketReach returned contact data but no company firmographics. Firmographics in this dossier are OSINT-sourced and lower-confidence."}
                </div>
              )}
              {request.status === "partial" && !request.rr_degraded && request.error_message && (
                <div className="text-xs text-amber-700 dark:text-amber-400 mt-1">
                  {request.error_message}
                </div>
              )}
            </div>
          </div>
        ) : request.status === "failed" ? (
          <div className="flex items-start gap-3 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-3">
            <AlertCircle className="h-5 w-5 mt-0.5 text-destructive shrink-0" />
            <div className="flex-1 space-y-1">
              <div className="text-sm font-medium">Generation failed</div>
              <div className="text-xs text-muted-foreground break-words">
                {request.error_message || "Unknown error"}
              </div>
            </div>
          </div>
        ) : (
          <div className="flex items-start gap-3 rounded-md border bg-muted/30 px-3 py-3">
            <X className="h-5 w-5 mt-0.5 text-muted-foreground shrink-0" />
            <div className="text-sm">Cancelled</div>
          </div>
        )
      ) : (
        <div className="flex items-center gap-3 rounded-md border bg-muted/20 px-3 py-3">
          <Spinner className="h-4 w-4 text-primary shrink-0" />
          <div className="flex-1 text-sm">
            <div className="font-medium">
              {request.stage
                ? STAGE_LABELS[request.stage as DossierRequestStage]
                : "Starting"}
              …
            </div>
            <div className="text-xs text-muted-foreground">
              {isRetryPass
                ? "First pass had thin sections — regenerating once for a richer dossier (~3 extra min)."
                : "Usually completes in 2-3 minutes. Safe to close — generation continues."}
            </div>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex flex-row-reverse gap-2 pt-1">
        {terminal &&
          (request.status === "succeeded" || request.status === "partial") &&
          request.lead_id && (
            <Button onClick={onViewDossier} className="cursor-pointer">
              View dossier
            </Button>
          )}
        {terminal && request.status === "failed" && (
          <Button
            onClick={onTryAgain}
            disabled={retrying}
            className="cursor-pointer"
          >
            {retrying ? (
              <>
                <Spinner className="h-4 w-4 mr-2" />
                Retrying…
              </>
            ) : (
              "Try again"
            )}
          </Button>
        )}
        <Button
          type="button"
          variant={terminal ? "ghost" : "outline"}
          onClick={onClose}
          className="cursor-pointer"
        >
          {terminal ? "Close" : "Run in background"}
        </Button>
      </div>
    </div>
  );
}
