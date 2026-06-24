/**
 * HTTP client for the Catalyst Advanced I/O Function at /server/api/*.
 * Exposes functions with shapes compatible with the old TanStack Server Functions
 * — components can keep their `fn({ data: {...} })` call style.
 */

const BASE = "/server/api";

// Custom error class that carries the server's full JSON payload + status
// code so callers can branch on specific error shapes (e.g. 409
// duplicate_in_flight → switch to the existing request's progress view
// instead of just toasting the message).
export class ApiError extends Error {
  status: number;
  payload: any;
  constructor(message: string, status: number, payload: any) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

async function call<T = any>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    credentials: "include",
    headers: {
      Accept: "application/json",
      ...(init.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
      ...(init.headers || {}),
    },
    ...init,
  });
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    let payload: any = null;
    try {
      payload = await res.json();
      // Surface server-side diagnostic fields (step, catalyst) when present.
      const parts: string[] = [];
      if (payload?.error || payload?.message) parts.push(String(payload.error || payload.message));
      if (payload?.step) parts.push(`step=${payload.step}`);
      if (payload?.catalyst) parts.push(`catalyst=${payload.catalyst}`);
      if (parts.length) msg = parts.join(" · ");
      console.error(`[api ${init.method || "GET"} ${path}]`, payload);
    } catch {}
    throw new ApiError(msg, res.status, payload);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

function toQueryString(params: Record<string, unknown>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v == null || v === "") continue;
    sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

// ---------- leads ----------

export type UploadInput = {
  filename: string;
  html: string;
};

export async function uploadDossier({ data }: { data: UploadInput }) {
  return call<{ id: string; lead_name: string; company: string | null; updated: boolean }>(
    "/leads/upload",
    { method: "POST", body: JSON.stringify(data) },
  );
}

export type ListInput = {
  search?: string;
  tier?: "HOT" | "WARM" | "COOL" | "COLD";
  company?: string;
  min_score?: number;
  max_score?: number;
  signal_label?: string;
  signal_type?: string;
  confidence?: "high" | "medium" | "low" | "unknown";
  icp_min?: number;
  mine?: "1";
};

export async function listLeads({ data }: { data?: ListInput } = {}) {
  return call<{ leads: any[] }>(`/leads${toQueryString((data || {}) as Record<string, unknown>)}`);
}

export async function getLead({ data }: { data: { id: string } }) {
  return call<{
    lead: any;
    signals: any[];
    html: string | null;
    htmlUrl: string | null;
    storage_status: "available" | "missing" | null;
  }>(`/leads/${encodeURIComponent(data.id)}`);
}

export async function deleteLead({ data }: { data: { id: string } }) {
  return call<{ ok: boolean }>(`/leads/${encodeURIComponent(data.id)}`, { method: "DELETE" });
}

export async function getDashboardStats() {
  return call<{ leads: any[]; signals: any[] }>(`/stats`);
}

// ---------- dossier requests (server-side generation) ----------

import type {
  DossierRequest,
  DossierRequestStatus,
} from "@/types/dossier-requests";

export type CreateDossierInput = {
  name?: string;
  email?: string;
  linkedin_url?: string;
  company_url?: string;
  notes?: string;
  // Opaque caller-side hint; the backend gates its meaning behind a server
  // allowlist, so callers without access get the same response shape and
  // an identical dossier as if the field were absent.
  _x?: string;
};

export async function createDossierRequest({ data }: { data: CreateDossierInput }) {
  return call<{
    request_id: string;
    status: DossierRequestStatus;
    catalyst_job_id: string | null;
  }>("/dossiers/generate", { method: "POST", body: JSON.stringify(data) });
}

export async function getDossierRequest({ data }: { data: { id: string } }) {
  return call<{ request: DossierRequest }>(
    `/dossiers/generate/${encodeURIComponent(data.id)}`,
  );
}

export async function listDossierRequests(
  { data }: { data?: { status?: DossierRequestStatus | string } } = {},
) {
  const qs = toQueryString((data || {}) as Record<string, unknown>);
  return call<{ requests: DossierRequest[] }>(`/dossiers/generate${qs}`);
}

// Hard-delete a single terminal dossier_requests row (the inbox entry,
// NOT the lead itself). `force=1` opts into the broader-status branch of
// the DELETE handler — without it the server only cancels `pending` rows.
export async function clearDossierRequest({ data }: { data: { id: string } }) {
  return call<{ ok: true; deleted: number }>(
    `/dossiers/generate/${encodeURIComponent(data.id)}?force=1`,
    { method: "DELETE" },
  );
}

// Hard-delete every terminal dossier_requests row for the current user.
// Live (pending/running) rows are skipped server-side.
export async function clearAllTerminalRequests() {
  return call<{ ok: true; deleted: number }>(
    `/dossiers/generate?clear_terminal=1`,
    { method: "DELETE" },
  );
}

export async function cancelDossierRequest({ data }: { data: { id: string } }) {
  return call<{ ok: boolean; status: DossierRequestStatus }>(
    `/dossiers/generate/${encodeURIComponent(data.id)}`,
    { method: "DELETE" },
  );
}

// ---------- me / auth bootstrap ----------

export async function getMyRole() {
  return call<{ userId: string; roles: string[]; isAdmin: boolean; role: string }>(`/me/role`);
}

// Triggers Catalyst's email-based password reset for the logged-in user.
// The server resolves the email from the session — nothing is sent in the
// body. Returns the email the reset link was sent to (for the success toast).
export async function resetMyPassword() {
  return call<{ ok: boolean; email: string }>(`/me/reset-password`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function getMyProfile() {
  return call<{
    userId: string;
    email: string | null;
    firstName: string | null;
    lastName: string | null;
    role: string;
    isAdmin: boolean;
    isSuperAdmin?: boolean;
    roles: string[];
    heavyAllowed?: boolean;
  }>(`/me`);
}

// Login beacon for the Audit Report. Fired once per browser session from
// auth.tsx (sessionStorage-guarded) right after auth resolves. Best-effort —
// the server always 200s and the audit write is fire-and-forget.
export async function postSessionStart() {
  return call<{ ok: boolean }>(`/me/session-start`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function postSignupBootstrap() {
  return call<{ role: "admin" | "user"; alreadySet: boolean }>(`/auth/post-signup`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

// Public self-signup — no auth cookie required. Server validates the email
// domain against ALLOWED_SIGNUP_DOMAINS before calling registerUser; the
// 403 payload's `error` field surfaces the human-readable allowed list.
export async function selfSignup({
  data,
}: {
  data: { first_name: string; last_name: string; email_id: string };
}) {
  return call<{ ok: true; message: string; email: string }>(`/auth/signup`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getSignupConfig() {
  return call<{ allowed_domains: string[] }>(`/auth/signup/config`);
}

// ---------- admin ----------

export type AdminUser = {
  id: string;
  email: string | null;
  first_name?: string | null;
  last_name?: string | null;
  created_at: string;
  last_sign_in_at: string | null;
  confirmed?: boolean;
  email_confirmed_at: string | null;
  banned_until?: string | null;
  provider: string | null;
  roles: string[];
  is_admin: boolean;
};

export async function adminListUsers(
  { data }: { data?: { page?: number; perPage?: number } } = {},
) {
  const qs = toQueryString((data || {}) as Record<string, unknown>);
  return call<{ users: AdminUser[]; total: number; page: number; perPage: number }>(
    `/admin/users${qs}`,
  );
}

export async function adminSetRole({
  data,
}: {
  data: { userId: string; role: "admin" | "user"; grant: boolean };
}) {
  return call<{ ok: boolean }>(
    `/admin/users/${encodeURIComponent(data.userId)}/role`,
    { method: "POST", body: JSON.stringify({ role: data.role, grant: data.grant }) },
  );
}

export async function adminDeleteUser({ data }: { data: { userId: string } }) {
  return call<{ ok: boolean }>(`/admin/users/${encodeURIComponent(data.userId)}`, {
    method: "DELETE",
  });
}

export async function adminCreateUser({
  data,
}: {
  data: {
    first_name: string;
    last_name: string;
    email_id: string;
    role: "user" | "admin";
  };
}) {
  return call<AdminUser>(`/admin/users`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ---------- audit report ----------

import type {
  AuditFeedResponse,
  AuditSummary,
  AuditDrilldownCard,
  AuditDrilldownResponse,
} from "@/types/audit";

export type AuditFeedInput = {
  event_type?: string; // comma-separated list of AuditEventType
  q?: string; // free-text over actor + label + action
  user?: string; // user_id filter
  from?: string; // YYYY-MM-DD
  to?: string; // YYYY-MM-DD
  limit?: number;
  offset?: number;
};

export async function getAuditLog({ data }: { data?: AuditFeedInput } = {}) {
  const qs = toQueryString((data || {}) as Record<string, unknown>);
  return call<AuditFeedResponse>(`/audit${qs}`);
}

export async function getAuditSummary() {
  return call<AuditSummary>(`/audit/summary`);
}

export async function getAuditDrilldown({ data }: { data: { card: AuditDrilldownCard } }) {
  const qs = toQueryString({ card: data.card } as Record<string, unknown>);
  return call<AuditDrilldownResponse>(`/audit/drilldown${qs}`);
}

// ---------- super-admin generation settings ----------

// One field's contract — mirrors functions/api/lib/generation-settings.schema.json.
export type SettingSpec = {
  type: "int" | "bool" | "enum";
  default: number | boolean | string;
  min?: number;
  max?: number;
  enum?: string[];
  recommended: number | boolean | string;
  unit?: string;
  engine: "light" | "heavy" | "shared";
  group: "richness" | "operational";
  label: string;
  help: string;
  tradeoff: string;
  recommendedNote?: string;
  dependsOn?: string;
};

export type SettingsSchema = {
  version: number;
  models: { id: string; label: string }[];
  settings: Record<string, SettingSpec>;
};

export type SettingsWarning = { field: string; level: "info" | "warn"; msg: string };

export type SettingsValue = number | boolean | string;

export type GetSettingsResponse = {
  schema: SettingsSchema;
  defaults: Record<string, SettingsValue>;
  settings: Record<string, SettingsValue>;
  warnings: SettingsWarning[];
  meta: { updatedBy: string | null; updatedAt: string | null; hasRow: boolean };
};

export async function getSettings() {
  return call<GetSettingsResponse>(`/admin/settings`);
}

export type UpdateSettingsResponse = {
  ok: boolean;
  settings: Record<string, SettingsValue>;
  warnings: SettingsWarning[];
  meta: { updatedBy: string; updatedAt: string };
};

export async function updateSettings({
  data,
}: {
  data: Record<string, SettingsValue>;
}) {
  return call<UpdateSettingsResponse>(`/admin/settings`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}
