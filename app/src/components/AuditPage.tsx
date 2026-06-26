import { useEffect, useMemo, useRef, useState } from "react";
import { useServerFn } from "@/lib/use-server-fn";
import { getAuditLog, getAuditSummary } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/Spinner";
import { AuditEventList, TYPE_META, FILTERS } from "@/components/AuditEventList";
import { AuditDrilldownDialog } from "@/components/AuditDrilldownDialog";
import { Search, X, ScrollText, Users, FileText, Activity } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import type {
  AuditEvent,
  AuditEventType,
  AuditSummary,
  AuditDrilldownCard,
} from "@/types/audit";

const POLL_MS = 7000;

function KpiTile({
  label,
  value,
  Icon,
  onClick,
  kpiKey,
}: {
  label: string;
  value: number | string;
  Icon: typeof Activity;
  onClick?: () => void;
  /** Stable selector hook so the drill-down popup can FLIP-minimize into this card. */
  kpiKey?: string;
}) {
  const interactive = !!onClick;
  return (
    <Card
      data-kpi={kpiKey}
      className={`p-4 ${
        interactive
          ? "cursor-pointer transition-colors hover:bg-accent/30 hover:border-primary/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          : ""
      }`}
      {...(interactive
        ? {
            role: "button",
            tabIndex: 0,
            "aria-haspopup": "dialog" as const,
            onClick,
            onKeyDown: (e: React.KeyboardEvent) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onClick();
              }
            },
          }
        : {})}
    >
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

  // Which KPI card's drill-down popup is open (null = closed).
  const [drillCard, setDrillCard] = useState<AuditDrilldownCard | null>(null);

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
      <PageHeader
        eyebrow="Audit"
        icon={ScrollText}
        title="Audit log"
        description="Live, org-wide activity — logins, dossier creation, searches, and admin actions."
        aside={
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75 motion-safe:animate-ping" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>
            Live · refreshes every {POLL_MS / 1000}s
          </div>
        }
      />

      {/* Screen-reader live announcement of new activity. */}
      <div aria-live="polite" className="sr-only">
        {newCount > 0 ? `${newCount} new audit ${newCount === 1 ? "event" : "events"}` : ""}
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiTile
          label="Events today"
          value={summary?.events_today ?? "—"}
          Icon={Activity}
          kpiKey="events"
          onClick={summary ? () => setDrillCard("events") : undefined}
        />
        <KpiTile
          label="Active users"
          value={summary?.active_users_today ?? "—"}
          Icon={Users}
          kpiKey="active_users"
          onClick={summary ? () => setDrillCard("active_users") : undefined}
        />
        <KpiTile
          label="Dossiers today"
          value={summary?.dossiers_today ?? "—"}
          Icon={FileText}
          kpiKey="dossiers"
          onClick={summary ? () => setDrillCard("dossiers") : undefined}
        />
        <KpiTile
          label="Searches today"
          value={summary?.searches_today ?? "—"}
          Icon={Search}
          kpiKey="searches"
          onClick={summary ? () => setDrillCard("searches") : undefined}
        />
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
          <AuditEventList events={events} />
        )}
      </Card>

      {!loading && hasMore && (
        <div className="flex justify-center">
          <Button variant="outline" size="sm" onClick={() => setLimit((l) => l + 100)}>
            Load more
          </Button>
        </div>
      )}

      <AuditDrilldownDialog
        card={drillCard}
        onOpenChange={(open) => {
          if (!open) setDrillCard(null);
        }}
      />
    </div>
  );
}
