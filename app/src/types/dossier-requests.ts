// Shape of a row from the dossier_requests table, as reshaped by the
// /dossiers/generate routes in functions/api/routes/dossiers.js.

export type DossierRequestStatus =
  | "pending"
  | "running"
  | "succeeded"
  | "failed"
  | "partial"
  | "cancelled";

export type DossierRequestStage =
  | "queued"
  | "preflight"
  | "rocketreach"
  | "synthesis"
  | "synthesis_retry"
  | "rendering"
  | "lint"
  | "upload"
  | "done"
  | "error";

export type DossierRequest = {
  // Server reshapes ROWID → id (string) so JS Number precision doesn't lose digits.
  id: string;
  user_id: string;
  status: DossierRequestStatus;
  stage: DossierRequestStage | null;
  intake_name: string | null;
  intake_email: string | null;
  intake_linkedin_url: string | null;
  intake_company_url: string | null;
  intake_notes: string | null;
  catalyst_job_id: string | null;
  // Kept as string (not number) — Catalyst ROWID is a 17-digit bigint
  // that JS Number() rounds to the nearest IEEE-754 double, losing the
  // last digit. The server emits it as a string for that reason.
  lead_id: string | null;
  error_message: string | null;
  tokens_input: number | null;
  tokens_output: number | null;
  rr_calls: number | null;
  // True when the pipeline auto-degraded to OSINT-only synthesis because
  // RocketReach had no firmographics for the lead's org (common for
  // .gov/.edu/non-profit prospects RR doesn't index). Surfaces as the
  // OSINT-only badge in the activity UI; status will be "partial".
  rr_degraded: boolean | null;
  // "rr_full_miss" when no RR data at all; "rr_company_miss" when contact
  // /DMU data was returned but firmographics were missing. Null when RR
  // ran cleanly (or when the row predates this column).
  rr_degradation_reason: string | null;
  started_at: string | null;
  completed_at: string | null;
  CREATEDTIME: string | null;
};

// Order of stages for UI progress rendering. `done` and `error` are terminal
// and don't appear in the running progress bar.
export const STAGE_SEQUENCE: DossierRequestStage[] = [
  "queued",
  "preflight",
  "rocketreach",
  "synthesis",
  "rendering",
  "lint",
  "upload",
];

export const STAGE_LABELS: Record<DossierRequestStage, string> = {
  queued: "Queued",
  preflight: "Preflight",
  rocketreach: "Enriching",
  synthesis: "Researching",
  // synthesis_retry overlays the same slot in the progress bar as synthesis;
  // we just relabel it so the user knows why the second pass is taking longer.
  synthesis_retry: "Researching (2nd pass)",
  rendering: "Rendering",
  lint: "Verifying",
  upload: "Saving",
  done: "Complete",
  error: "Error",
};

// Map a stage value to the canonical sequence-slot for progress-bar highlight.
// synthesis_retry isn't a separate step in the workflow — it shares the
// "synthesis" pill but with the retry label above.
export function stageForSequence(
  stage: DossierRequestStage | null | undefined,
): DossierRequestStage | null {
  if (!stage) return null;
  if (stage === "synthesis_retry") return "synthesis";
  return stage;
}

export const TERMINAL_STATUSES: DossierRequestStatus[] = [
  "succeeded",
  "failed",
  "partial",
  "cancelled",
];

export function isTerminal(status: DossierRequestStatus): boolean {
  return TERMINAL_STATUSES.includes(status);
}
