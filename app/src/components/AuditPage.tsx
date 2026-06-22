import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import { useServerFn } from "@/lib/use-server-fn";
import { getAuditLog, getAuditSummary } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/Spinner";
import { safeDate } from "@/lib/utils";
import {
  Search,
  X,
  ScrollText,
  LogIn,
  Sparkles,
  Shield,
  Users,
  FileText,
  Activity,
  Eye,
} from "lucide-react";
import type {
  AuditEvent,
  AuditEventType,
  AuditSummary,
} from "@/types/audit";

const POLL_MS = 7000;

// Per-type presentation: chip label, icon, and badge colors. Keep the keys in
// sync with lib/audit.js EVENT_TYPES and routes/audit.js.
const TYPE_META: Record<
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

const FILTERS: { key: AuditEventType | ""; label: string }[] = [
  { key: "", label: "All" },
  { key: "login", label: "Logins" },
  { key: "dossier_create", label: "Dossiers" },
  { key: "search", label: "Searches" },
  { key: "lead_view", label: "Views" },
  { key: "admin_action", label: "Admin" },
];

// Live-status badge for dossier_create rows (current dossier_requests state).
function dossierStatusClass(status: string | null | undefined): string {
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

function relTime(iso: string | null): string {
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

function absTime(iso: string | null): string {
  const d = safeDate(iso);
  return d ? d.toLocaleString() : "—";
}

function initialsOf(name: string | null, email: string | null): string {
  const src = (name || email || "?").trim();
  const parts = src.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return src.slice(0, 2).toUpperCase();
}

// Human-readable description of an event. Returns inline JSX so dossier rows
// can deep-link to the produced lead.
function describe(ev: AuditEvent): ReactNode {
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

function KpiTile({
  label,
  value,
  Icon,
}: {
  label: string;
  value: number | string;
  Icon: typeof Activity;
}) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-widest text-muted-foreground">{label}</span>
        <Icon className="h-3.5 w-3.5 text-muted-foreground/70" />
      </div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>
    </Card>
  );
}

export function AuditPage() {
  const feedFn = useServerFn(getAuditLog);
  const sumFn = useServerFn(getAuditSummary);

  const [searchInput, setSearchInput] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [typeFilter, setTypeFilter] = useState<AuditEventType | "">("");
  const [limit, setLimit] = useState(100);

  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [summary, setSummary] = useState<AuditSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [hasMore, setHasMore] = useState(false);
  const [newCount, setNewCount] = useState(0);

  // Track ids already shown so a poll can announce only genuinely new events.
  const seenIds = useRef<Set<string>>(new Set());
  const firstLoad = useRef(true);

  // Debounce the free-text query.
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(searchInput.trim()), 300);
    return () => clearTimeout(t);
  }, [searchInput]);

  // Fetch + poll. The interval recreates when filters change so it always
  // queries the current view. Polling pauses while the tab is hidden.
  useEffect(() => {
    let active = true;
    let intervalId: number | null = null;

    const load = (silent: boolean) => {
      if (!silent) setLoading(true);
      Promise.all([
        feedFn({
          data: {
            q: debouncedQ || undefined,
            event_type: typeFilter || undefined,
            limit,
          },
        }),
        sumFn(),
      ])
        .then(([feed, sum]) => {
          if (!active) return;
          if (!firstLoad.current) {
            const fresh = feed.events.filter((e) => !seenIds.current.has(e.id)).length;
            if (fresh > 0) setNewCount((n) => n + fresh);
          }
          seenIds.current = new Set(feed.events.map((e) => e.id));
          firstLoad.current = false;
          setEvents(feed.events);
          setHasMore(feed.hasMore);
          setSummary(sum);
        })
        .catch(() => {
          /* transient — keep the last good view, next poll retries */
        })
        .finally(() => {
          if (active && !silent) setLoading(false);
        });
    };

    const start = () => {
      if (intervalId == null) intervalId = window.setInterval(() => load(true), POLL_MS);
    };
    const stop = () => {
      if (intervalId != null) {
        window.clearInterval(intervalId);
        intervalId = null;
      }
    };
    const onVis = () => {
      if (document.hidden) stop();
      else {
        load(true);
        start();
      }
    };

    load(false);
    if (!document.hidden) start();
    document.addEventListener("visibilitychange", onVis);
    return () => {
      active = false;
      stop();
      document.removeEventListener("visibilitychange", onVis);
    };
  }, [feedFn, sumFn, debouncedQ, typeFilter, limit]);

  // Reset the "new" counter when the user changes the view.
  useEffect(() => {
    setNewCount(0);
    firstLoad.current = true;
  }, [debouncedQ, typeFilter]);

  const maxDay = useMemo(() => {
    if (!summary) return 0;
    return Math.max(
      1,
      ...summary.series_7d.map(
        (d) => d.login + d.dossier_create + d.search + d.lead_view + d.admin_action,
      ),
    );
  }, [summary]);

  const hasFilters = !!debouncedQ || !!typeFilter;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
            <ScrollText className="h-6 w-6 text-primary" />
            Audit log
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Live, org-wide activity — logins, dossier creation, searches, and admin actions.
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75 motion-safe:animate-ping" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
          </span>
          Live · refreshes every {POLL_MS / 1000}s
        </div>
      </div>

      {/* Screen-reader live announcement of new activity. */}
      <div aria-live="polite" className="sr-only">
        {newCount > 0 ? `${newCount} new audit ${newCount === 1 ? "event" : "events"}` : ""}
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiTile label="Events today" value={summary?.events_today ?? "—"} Icon={Activity} />
        <KpiTile label="Active users" value={summary?.active_users_today ?? "—"} Icon={Users} />
        <KpiTile label="Dossiers today" value={summary?.dossiers_today ?? "—"} Icon={FileText} />
        <KpiTile label="Searches today" value={summary?.searches_today ?? "—"} Icon={Search} />
      </div>

      {/* 7-day activity series (stacked CSS bars — no chart dependency). */}
      {summary && summary.total_7d > 0 && (
        <Card className="p-4">
          <div className="text-[10px] uppercase tracking-widest text-muted-foreground mb-3">
            Last 7 days
          </div>
          <div className="flex items-end gap-2">
            {summary.series_7d.map((d) => {
              const total =
                d.login + d.dossier_create + d.search + d.lead_view + d.admin_action;
              const h = (total / maxDay) * 100;
              return (
                <div key={d.date} className="flex-1 flex flex-col items-center gap-1 min-w-0">
                  {/* Fixed-height track gives the percentage-height bar a definite
                     parent to resolve against (a flex item under items-end has no
                     definite height, which would collapse the bar to 0). */}
                  <div className="w-full h-24 flex items-end">
                    <div
                      className="w-full flex flex-col-reverse rounded-t bg-muted/40 overflow-hidden"
                      style={{ height: `${Math.max(h, total > 0 ? 6 : 2)}%` }}
                      title={`${d.date}: ${total} events`}
                    >
                      <div style={{ flexGrow: d.login }} className="bg-sky-500/70" />
                      <div style={{ flexGrow: d.dossier_create }} className="bg-violet-500/70" />
                      <div style={{ flexGrow: d.search }} className="bg-amber-500/70" />
                      <div style={{ flexGrow: d.lead_view }} className="bg-teal-500/70" />
                      <div style={{ flexGrow: d.admin_action }} className="bg-rose-500/70" />
                    </div>
                  </div>
                  <span className="text-[9px] text-muted-foreground tabular-nums">
                    {d.date.slice(5)}
                  </span>
                </div>
              );
            })}
          </div>
        </Card>
      )}

      {/* Filters */}
      <Card className="p-3 sm:p-4">
        <div className="flex flex-col sm:flex-row gap-2">
          <div className="relative flex-1 min-w-0">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search by person, query, or action…"
              className="pl-9"
            />
          </div>
          <div className="flex gap-1 overflow-x-auto -mx-1 px-1 sm:mx-0 sm:px-0">
            {FILTERS.map((f) => (
              <button
                key={f.key || "all"}
                onClick={() => setTypeFilter(f.key)}
                aria-pressed={typeFilter === f.key}
                className={`px-3 py-1.5 text-xs rounded-md border whitespace-nowrap shrink-0 ${
                  typeFilter === f.key
                    ? "bg-primary/15 border-primary/40 text-primary"
                    : "border-border text-muted-foreground hover:text-foreground"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>
        {hasFilters && (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {debouncedQ && (
              <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-primary/10 border border-primary/30 text-primary">
                “{debouncedQ}”
                <button onClick={() => setSearchInput("")} aria-label="Clear search">
                  <X className="h-3 w-3" />
                </button>
              </span>
            )}
            {typeFilter && (
              <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-primary/10 border border-primary/30 text-primary">
                {TYPE_META[typeFilter].label}
                <button onClick={() => setTypeFilter("")} aria-label="Clear type filter">
                  <X className="h-3 w-3" />
                </button>
              </span>
            )}
          </div>
        )}
      </Card>

      {!loading && newCount > 0 && (
        <div className="px-1">
          <span className="text-xs text-emerald-700 dark:text-emerald-300">
            +{newCount} new {newCount === 1 ? "event" : "events"}
          </span>
        </div>
      )}

      {/* Feed */}
      <Card className="p-0 overflow-hidden">
        {loading ? (
          <div className="grid place-items-center py-16 min-h-[40vh] text-muted-foreground">
            <Spinner className="h-5 w-5" />
          </div>
        ) : events.length === 0 ? (
          <div className="py-16 flex flex-col items-center justify-center gap-3 text-center px-6">
            <ScrollText className="h-10 w-10 text-muted-foreground/40" />
            <div className="text-sm font-medium">No activity yet</div>
            <p className="text-xs text-muted-foreground max-w-xs">
              {hasFilters
                ? "No audit events match your filters."
                : "Logins, dossier creation, searches, and admin actions will appear here as they happen."}
            </p>
          </div>
        ) : (
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
        )}
      </Card>

      {!loading && hasMore && (
        <div className="flex justify-center">
          <Button variant="outline" size="sm" onClick={() => setLimit((l) => l + 100)}>
            Load more
          </Button>
        </div>
      )}
    </div>
  );
}
