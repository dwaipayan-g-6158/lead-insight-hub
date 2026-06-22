// Shapes for the org-wide Audit Report. Mirrors functions/api/routes/audit.js
// (reshapeEvent + GET /audit/summary) and lib/audit.js EVENT_TYPES.

export type AuditEventType =
  | "login"
  | "dossier_create"
  | "search"
  | "lead_view"
  | "admin_action";

// Live dossier state spliced onto dossier_create events by the read API.
export type AuditDossierStatus = {
  status: string | null;
  stage: string | null;
  lead_id: string | null;
};

export type AuditEvent = {
  id: string;
  user_id: string | null;
  actor_email: string | null;
  actor_name: string | null;
  event_type: AuditEventType;
  event_action: string | null;
  target_type: string | null;
  target_id: string | null;
  target_label: string | null;
  metadata: Record<string, unknown> | null;
  /** ISO-8601 UTC (…Z). Parse with safeDate(). */
  occurred_at: string | null;
  /** Present only on dossier_create events. */
  dossier?: AuditDossierStatus;
};

export type AuditFeedResponse = {
  events: AuditEvent[];
  limit: number;
  offset: number;
  hasMore: boolean;
};

export type AuditDaySeries = {
  date: string;
  login: number;
  dossier_create: number;
  search: number;
  lead_view: number;
  admin_action: number;
};

export type AuditSummary = {
  window_days: number;
  total_7d: number;
  events_today: number;
  active_users_today: number;
  dossiers_today: number;
  searches_today: number;
  logins_today: number;
  by_type_7d: Record<AuditEventType, number>;
  top_searchers_7d: { name: string; count: number }[];
  series_7d: AuditDaySeries[];
};
