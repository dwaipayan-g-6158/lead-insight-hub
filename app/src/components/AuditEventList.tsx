import { type ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import { safeDate } from "@/lib/utils";
import { Search, LogIn, Sparkles, Shield, Eye } from "lucide-react";
import type { AuditEvent, AuditEventType } from "@/types/audit";

// Per-type presentation: chip label, icon, and badge colors. Keep the keys in
// sync with lib/audit.js EVENT_TYPES and routes/audit.js.
export const TYPE_META: Record<
  AuditEventType,
  { label: string; Icon: typeof LogIn; badge: string }
> = {
  login: {
    label: "Login",
    Icon: LogIn,
    badge: "bg-sky-500/12 border-sky-500/30 text-sky-700 dark:text-sky-300",
  },
  dossier_create: {
    label: "Dossier",
    Icon: Sparkles,
    badge: "bg-violet-500/12 border-violet-500/30 text-violet-700 dark:text-violet-300",
  },
  lead_view: {
    label: "View",
    Icon: Eye,
    badge: "bg-teal-500/12 border-teal-500/30 text-teal-700 dark:text-teal-300",
  },
  search: {
    label: "Search",
    Icon: Search,
    badge: "bg-amber-500/12 border-amber-500/30 text-amber-700 dark:text-amber-300",
  },
  admin_action: {
    label: "Admin",
    Icon: Shield,
    badge: "bg-rose-500/12 border-rose-500/30 text-rose-700 dark:text-rose-300",
  },
};

export const FILTERS: { key: AuditEventType | ""; label: string }[] = [
  { key: "", label: "All" },
  { key: "login", label: "Logins" },
  { key: "dossier_create", label: "Dossiers" },
  { key: "search", label: "Searches" },
  { key: "lead_view", label: "Views" },
  { key: "admin_action", label: "Admin" },
];

// Live-status badge for dossier_create rows (current dossier_requests state).
export function dossierStatusClass(status: string | null | undefined): string {
  switch ((status || "").toLowerCase()) {
    case "succeeded":
      return "bg-emerald-500/12 border-emerald-500/30 text-emerald-700 dark:text-emerald-300";
    case "failed":
    case "cancelled":
      return "bg-rose-500/12 border-rose-500/30 text-rose-700 dark:text-rose-300";
    case "partial":
      return "bg-amber-500/12 border-amber-500/30 text-amber-700 dark:text-amber-300";
    case "pending":
    case "running":
      return "bg-sky-500/12 border-sky-500/30 text-sky-700 dark:text-sky-300";
    default:
      return "bg-accent/40 border-border text-muted-foreground";
  }
}

export function relTime(iso: string | null): string {
  const d = safeDate(iso);
  if (!d) return "—";
  const diff = Date.now() - d.getTime();
  const s = Math.max(0, Math.round(diff / 1000));
  if (s < 45) return "just now";
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  const dd = Math.round(h / 24);
  if (dd < 7) return `${dd}d ago`;
  return d.toLocaleDateString();
}

export function absTime(iso: string | null): string {
  const d = safeDate(iso);
  return d ? d.toLocaleString() : "—";
}

export function initialsOf(name: string | null, email: string | null): string {
  const src = (name || email || "?").trim();
  const parts = src.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return src.slice(0, 2).toUpperCase();
}

// Human-readable description of an event. Returns inline JSX so dossier rows
// can deep-link to the produced lead.
export function describe(ev: AuditEvent): ReactNode {
  switch (ev.event_type) {
    case "login":
      return <span className="text-muted-foreground">signed in</span>;
    case "search":
      return (
        <span>
          searched{" "}
          <span className="font-medium text-foreground">“{ev.target_label || ""}”</span>
          {typeof ev.metadata?.results === "number" && (
            <span className="text-muted-foreground"> · {ev.metadata.results as number} results</span>
          )}
        </span>
      );
    case "dossier_create": {
      const engine = ev.event_action === "heavy" ? "Heavy" : "Light";
      const lead = ev.dossier?.lead_id;
      const label = ev.target_label || "a prospect";
      return (
        <span>
          created a <span className="text-muted-foreground">{engine}</span> dossier for{" "}
          {lead ? (
            <Link
              to="/leads/$leadId"
              params={{ leadId: lead }}
              className="font-medium hover:text-primary focus-visible:underline"
            >
              {label}
            </Link>
          ) : (
            <span className="font-medium text-foreground">{label}</span>
          )}
        </span>
      );
    }
    case "lead_view": {
      const label = ev.target_label || "a dossier";
      return (
        <span>
          viewed{" "}
          {ev.target_id ? (
            <Link
              to="/leads/$leadId"
              params={{ leadId: ev.target_id }}
              className="font-medium hover:text-primary focus-visible:underline"
            >
              {label}
            </Link>
          ) : (
            <span className="font-medium text-foreground">{label}</span>
          )}
        </span>
      );
    }
    case "admin_action": {
      const action = (ev.event_action || "").replace(/_/g, " ");
      return (
        <span>
          {action || "admin action"}
          {ev.target_label && (
            <span className="text-muted-foreground"> · {ev.target_label}</span>
          )}
        </span>
      );
    }
    default:
      return <span className="text-muted-foreground">{ev.event_action || ev.event_type}</span>;
  }
}

// Org-wide audit event list — a responsive table (desktop) / card list (mobile).
// Shared by the main feed (AuditPage) and the KPI drill-down popups so rows
// render identically everywhere.
export function AuditEventList({ events }: { events: AuditEvent[] }) {
  return (
    <>
      {/* Desktop / tablet — table */}
      <table className="w-full text-sm hidden sm:table">
        <thead className="bg-muted/40 text-xs uppercase tracking-wider text-muted-foreground">
          <tr>
            <th className="text-left px-4 py-2.5">When</th>
            <th className="text-left px-4 py-2.5">User</th>
            <th className="text-left px-4 py-2.5">Event</th>
            <th className="text-left px-4 py-2.5">Activity</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {events.map((ev) => {
            const meta = TYPE_META[ev.event_type];
            return (
              <tr key={ev.id} className="hover:bg-accent/30 align-top">
                <td className="px-4 py-3 whitespace-nowrap text-muted-foreground" title={absTime(ev.occurred_at)}>
                  {relTime(ev.occurred_at)}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2 min-w-0">
                    <span
                      aria-hidden
                      className="inline-grid h-6 w-6 shrink-0 place-items-center rounded-full bg-primary/20 text-[10px] font-semibold"
                    >
                      {initialsOf(ev.actor_name, ev.actor_email)}
                    </span>
                    <span className="truncate max-w-[180px]" title={ev.actor_email || undefined}>
                      {ev.actor_name || ev.actor_email || "Unknown"}
                    </span>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full border font-medium ${meta.badge}`}
                  >
                    <meta.Icon className="h-3 w-3" />
                    {meta.label}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2 flex-wrap">
                    {describe(ev)}
                    {ev.event_type === "dossier_create" && ev.dossier?.status && (
                      <span
                        className={`text-[10px] px-1.5 py-0.5 rounded-full border uppercase tracking-wider ${dossierStatusClass(ev.dossier.status)}`}
                      >
                        {ev.dossier.status}
                      </span>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {/* Mobile — card list */}
      <ul className="sm:hidden divide-y divide-border">
        {events.map((ev) => {
          const meta = TYPE_META[ev.event_type];
          return (
            <li key={ev.id} className="p-3">
              <div className="flex items-start gap-3">
                <span
                  aria-hidden
                  className="inline-grid h-9 w-9 shrink-0 place-items-center rounded-full bg-primary/20 text-xs font-semibold"
                >
                  {initialsOf(ev.actor_name, ev.actor_email)}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-medium truncate max-w-[150px]">
                      {ev.actor_name || ev.actor_email || "Unknown"}
                    </span>
                    <span
                      className={`inline-flex items-center gap-1 text-[9px] px-1.5 py-0.5 rounded-full border font-medium ${meta.badge}`}
                    >
                      <meta.Icon className="h-2.5 w-2.5" />
                      {meta.label}
                    </span>
                    <span className="ml-auto text-[10px] text-muted-foreground" title={absTime(ev.occurred_at)}>
                      {relTime(ev.occurred_at)}
                    </span>
                  </div>
                  <div className="text-sm mt-0.5 flex items-center gap-2 flex-wrap">
                    {describe(ev)}
                    {ev.event_type === "dossier_create" && ev.dossier?.status && (
                      <span
                        className={`text-[9px] px-1.5 py-0.5 rounded-full border uppercase tracking-wider ${dossierStatusClass(ev.dossier.status)}`}
                      >
                        {ev.dossier.status}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </>
  );
}
