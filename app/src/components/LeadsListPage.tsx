import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { useServerFn } from "@/lib/use-server-fn";
import { listLeads } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Search, Upload, X, FileSearch, Sparkles } from "lucide-react";
import { Spinner } from "@/components/Spinner";
import { tierClasses } from "@/lib/tier";
import { safeDate } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { useDossierActivity } from "@/lib/dossier-activity";
import type { LeadListRow } from "@/types/leads";
import { CreateDossierModal, markDossierOrigin } from "@/components/CreateDossierModal";
import { EngineBadge } from "@/components/EngineBadge";

// Strip Catalyst's trailing midnight (" 00:00:00") so the date pill
// reads cleanly. Shared by table + mobile-card renderers below.
const cleanDate = (s: string | null | undefined): string | null =>
  s ? String(s).replace(/[ T]00:00:00.*$/, "") : null;

// "Stale" pill: report_date older than 90 days flags intel that may need a
// refresh. Tolerates Catalyst's "YYYY-MM-DD HH:mm:ss" by normalizing the
// space to "T" before parsing; an unparseable date is treated as not stale.
const STALE_AFTER_MS = 90 * 24 * 60 * 60 * 1000;
const staleReportDate = (s: string | null | undefined): boolean => {
  if (!s) return false;
  const t = Date.parse(String(s).replace(" ", "T"));
  return Number.isFinite(t) && Date.now() - t > STALE_AFTER_MS;
};

export function LeadsListPage() {
  const { isAdmin } = useAuth();
  const fn = useServerFn(listLeads);
  const { leadsVersion } = useDossierActivity();
  const sp = useSearch({ from: "/leads/" });
  const navigate = useNavigate({ from: "/leads/" });
  const [search, setSearch] = useState(sp.q ?? "");
  const tier = sp.tier ?? "";
  const mine = sp.mine ?? false;
  const [rows, setRows] = useState<LeadListRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);

  // Mark the clicked button as the FLIP origin so the modal flies out from /
  // minimizes back into the exact button the user pressed.
  const openCreate = (e: React.MouseEvent<HTMLButtonElement>) => {
    markDossierOrigin(e.currentTarget);
    setCreateOpen(true);
  };

  // keep input in sync if URL changes externally
  useEffect(() => {
    setSearch(sp.q ?? "");
  }, [sp.q]);

  useEffect(() => {
    setLoading(true);
    const t = setTimeout(() => {
      fn({
        data: {
          search: search || undefined,
          tier: tier || undefined,
          company: sp.company,
          min_score: sp.min,
          max_score: sp.max,
          signal_label: sp.signal,
          signal_type: sp.signal_type,
          confidence: sp.confidence,
          icp_min: sp.icp_min,
          mine: mine ? "1" : undefined,
        },
      })
        .then((r) => setRows((r as { leads: LeadListRow[] }).leads))
        .finally(() => setLoading(false));
    }, 200);
    return () => clearTimeout(t);
  }, [
    fn,
    search,
    tier,
    sp.company,
    sp.min,
    sp.max,
    sp.signal,
    sp.signal_type,
    sp.confidence,
    sp.icp_min,
    mine,
    leadsVersion,
  ]);

  const tiers = useMemo(() => ["", "HOT", "WARM", "COOL", "COLD"] as const, []);

  // Detect re-scored duplicates by email so we can surface a small date
  // pill next to the lead name. Without this, two "Marco Lisboa @ AIG"
  // rows are visually identical apart from the score column.
  const duplicateEmails = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const r of rows) {
      const e = (r as { email?: string | null }).email?.toLowerCase().trim();
      if (e) counts[e] = (counts[e] || 0) + 1;
    }
    return new Set(Object.entries(counts).filter(([, n]) => n > 1).map(([e]) => e));
  }, [rows]);

  const isDuplicate = (l: LeadListRow) => {
    const e = (l as { email?: string | null }).email?.toLowerCase().trim();
    return !!e && duplicateEmails.has(e);
  };

  const setTier = (t: "" | "HOT" | "WARM" | "COOL" | "COLD") => {
    navigate({ search: (prev) => ({ ...prev, tier: t || undefined }), replace: true });
  };
  const setMine = (v: boolean) => {
    navigate({ search: (prev) => ({ ...prev, mine: v || undefined }), replace: true });
  };
  const clearFilter = (
    key: "company" | "min" | "max" | "signal" | "signal_type" | "confidence" | "icp_min" | "mine",
  ) => {
    navigate({ search: (prev) => ({ ...prev, [key]: undefined }), replace: true });
  };
  const clearAll = () => {
    setSearch("");
    navigate({ search: {}, replace: true });
  };

  const setConfidence = (c: "high" | "medium" | "low" | "unknown" | undefined) => {
    navigate({ search: (prev) => ({ ...prev, confidence: c }), replace: true });
  };
  const setIcpMin = (n: 1 | 2 | 3 | 4 | 5 | undefined) => {
    navigate({ search: (prev) => ({ ...prev, icp_min: n }), replace: true });
  };

  const activeFilters: {
    key: "company" | "min" | "max" | "signal" | "signal_type" | "confidence" | "icp_min" | "mine";
    label: string;
  }[] = [];
  if (sp.company) activeFilters.push({ key: "company", label: `Company: ${sp.company}` });
  if (sp.min != null) activeFilters.push({ key: "min", label: `Score \u2265 ${sp.min}` });
  if (sp.max != null) activeFilters.push({ key: "max", label: `Score \u2264 ${sp.max}` });
  if (sp.signal) activeFilters.push({ key: "signal", label: `Signal: ${sp.signal}` });
  if (sp.confidence)
    activeFilters.push({ key: "confidence", label: `Confidence: ${sp.confidence}` });
  if (sp.icp_min != null)
    activeFilters.push({ key: "icp_min", label: `ICP = ${sp.icp_min}\u2605` });
  if (mine) activeFilters.push({ key: "mine", label: "My dossiers" });

  return (
    <div className="space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 sm:gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Leads</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Search every dossier in your collective intelligence
          </p>
        </div>
        <div className="flex flex-col sm:flex-row gap-2 sm:w-auto">
          <Button
            size="sm"
            onClick={openCreate}
            className="w-full sm:w-auto cursor-pointer"
          >
            <Sparkles className="h-3.5 w-3.5 mr-1.5" /> Create dossier
          </Button>
          {isAdmin && (
            <Link to="/upload" className="sm:w-auto">
              <Button variant="outline" size="sm" className="w-full sm:w-auto">
                <Upload className="h-3.5 w-3.5 mr-1.5" /> Upload dossier
              </Button>
            </Link>
          )}
        </div>
      </div>
      <CreateDossierModal open={createOpen} onOpenChange={setCreateOpen} />

      <Card className="p-3 sm:p-4">
        <div className="flex flex-col sm:flex-row gap-2">
          <div className="relative flex-1 min-w-0">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by name, company, title, or email…"
              className="pl-9"
            />
          </div>
          <div className="flex gap-1 overflow-x-auto -mx-1 px-1 sm:mx-0 sm:px-0">
            {tiers.map((t) => (
              <button
                key={t || "all"}
                onClick={() => setTier(t)}
                className={`px-3 py-1.5 text-xs rounded-md border whitespace-nowrap shrink-0 ${
                  tier === t
                    ? "bg-primary/15 border-primary/40 text-primary"
                    : "border-border text-muted-foreground hover:text-foreground"
                }`}
              >
                {t || "All"}
              </button>
            ))}
          </div>
          <div className="flex gap-1 shrink-0" role="group" aria-label="Dossier scope">
            <button
              onClick={() => setMine(false)}
              aria-pressed={!mine}
              className={`px-3 py-1.5 text-xs rounded-md border whitespace-nowrap shrink-0 ${
                !mine
                  ? "bg-primary/15 border-primary/40 text-primary"
                  : "border-border text-muted-foreground hover:text-foreground"
              }`}
            >
              All
            </button>
            <button
              onClick={() => setMine(true)}
              aria-pressed={mine}
              className={`px-3 py-1.5 text-xs rounded-md border whitespace-nowrap shrink-0 ${
                mine
                  ? "bg-primary/15 border-primary/40 text-primary"
                  : "border-border text-muted-foreground hover:text-foreground"
              }`}
            >
              Mine
            </button>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1">
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground mr-1">
              Confidence
            </span>
            {(["high", "medium", "low", "unknown"] as const).map((c) => {
              const active = sp.confidence === c;
              return (
                <button
                  key={c}
                  onClick={() => setConfidence(active ? undefined : c)}
                  className={`px-2 py-1 text-[11px] rounded-md border whitespace-nowrap capitalize transition ${
                    active
                      ? "bg-primary/15 border-primary/40 text-primary"
                      : "border-border text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {c}
                </button>
              );
            })}
          </div>
          <div className="flex items-center gap-1">
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground mr-1">
              ICP =
            </span>
            {([1, 2, 3, 4, 5] as const).map((n) => {
              const active = sp.icp_min === n;
              return (
                <button
                  key={n}
                  onClick={() => setIcpMin(active ? undefined : n)}
                  className={`px-2 py-1 text-[11px] rounded-md border whitespace-nowrap transition ${
                    active
                      ? "bg-primary/15 border-primary/40 text-primary"
                      : "border-border text-muted-foreground hover:text-foreground"
                  }`}
                  aria-label={`ICP exactly ${n} stars`}
                >
                  {n}&#9733;
                </button>
              );
            })}
          </div>
        </div>
        {activeFilters.length > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {activeFilters.map((f) => (
              <button
                key={f.key}
                onClick={() => clearFilter(f.key)}
                className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-primary/10 border border-primary/30 text-primary hover:bg-primary/20"
              >
                {f.label}
                <X className="h-3 w-3" />
              </button>
            ))}
            <button
              onClick={clearAll}
              className="text-xs text-muted-foreground hover:text-foreground underline-offset-2 hover:underline ml-1"
            >
              Clear all
            </button>
          </div>
        )}
      </Card>

      {!loading && rows.length > 0 && (
        <div className="px-1 text-xs text-muted-foreground tabular-nums">
          Showing {rows.length} {rows.length === 1 ? "lead" : "leads"}
        </div>
      )}

      <Card className="p-0 overflow-hidden">
        {loading ? (
          <div className="grid place-items-center py-16 min-h-[60vh] text-muted-foreground">
            <Spinner className="h-5 w-5" />
          </div>
        ) : rows.length === 0 ? (
          <div className="py-16 flex flex-col items-center justify-center gap-3 text-center px-6">
            <FileSearch className="h-10 w-10 text-muted-foreground/40" />
            <div className="text-sm font-medium">No leads match your search</div>
            <p className="text-xs text-muted-foreground max-w-xs">
              {isAdmin
                ? "Try clearing some filters or upload a new ELISS dossier to grow your collective intelligence."
                : "Try clearing some filters or create a new lead to grow your collective intelligence."}
            </p>
            <div className="flex gap-2 mt-1">
              {activeFilters.length > 0 || search ? (
                <Button variant="ghost" size="sm" onClick={clearAll} className="cursor-pointer">
                  Clear all filters
                </Button>
              ) : null}
              {isAdmin ? (
                <Link to="/upload">
                  <Button size="sm" className="cursor-pointer">
                    <Upload className="h-4 w-4 mr-2" /> Upload dossier
                  </Button>
                </Link>
              ) : (
                <Button size="sm" onClick={openCreate} className="cursor-pointer">
                  <Sparkles className="h-4 w-4 mr-2" /> Create dossier
                </Button>
              )}
            </div>
          </div>
        ) : (
          <>
            {/* Desktop / tablet — table */}
            <table className="w-full text-sm hidden sm:table">
              <thead className="bg-muted/40 text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="text-left px-4 py-2.5">Lead</th>
                  <th className="text-left px-4 py-2.5">Company</th>
                  <th className="text-left px-4 py-2.5">Tier</th>
                  <th className="text-right px-4 py-2.5">Score</th>
                  <th className="text-left px-4 py-2.5 hidden md:table-cell">Report date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {rows.map((l) => (
                  <tr key={l.id} className="hover:bg-accent/30 cursor-pointer">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2 flex-wrap">
                        <Link
                          to="/leads/$leadId"
                          params={{ leadId: l.id }}
                          className="font-medium hover:text-primary cursor-pointer focus-visible:outline-none focus-visible:underline focus-visible:text-primary"
                        >
                          {l.lead_name}
                        </Link>
                        {isDuplicate(l) && cleanDate(l.report_date) && (
                          <span
                            className="text-[10px] px-1.5 py-0.5 rounded bg-accent/40 border border-border text-muted-foreground font-normal"
                            title={`Re-scored snapshot from ${cleanDate(l.report_date)}`}
                          >
                            {cleanDate(l.report_date)}
                          </span>
                        )}
                        {l.creator_unopened && (
                          <span
                            className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-full font-medium bg-emerald-500/12 border border-emerald-500/30 text-emerald-700 dark:text-emerald-300"
                            title="Your dossier finished — you haven't opened it yet"
                          >
                            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                            New
                          </span>
                        )}
                        {l.icp_stars === 5 && (
                          <span
                            className="text-[10px] px-1.5 py-0.5 rounded-full font-medium bg-amber-500/15 border border-amber-500/30 text-amber-700 dark:text-amber-300"
                            title="Ideal-fit account — ICP ★5"
                          >
                            Perfect ICP
                          </span>
                        )}
                        {staleReportDate(l.report_date) && (
                          <span
                            className="text-[10px] px-1.5 py-0.5 rounded bg-accent/40 border border-border text-muted-foreground font-normal"
                            title="Report is over 90 days old — may need a refresh"
                          >
                            Stale
                          </span>
                        )}
                        {(l.confidence || "").toUpperCase() === "LOW" && (
                          <span
                            className="text-[10px] px-1.5 py-0.5 rounded-full font-medium bg-rose-500/12 border border-rose-500/30 text-rose-700 dark:text-rose-300"
                            title="Low confidence — score rests on limited data, verify before acting"
                          >
                            Low confidence
                          </span>
                        )}
                        {isAdmin && <EngineBadge engine={l.generation_engine} />}
                      </div>
                      {l.lead_title && (
                        <div className="text-xs text-muted-foreground">{l.lead_title}</div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {l.company || <span className="text-muted-foreground">—</span>}
                    </td>
                    <td className="px-4 py-3">
                      {l.tier ? (
                        <span
                          className={`text-[10px] px-2 py-0.5 rounded-full uppercase tracking-wider ${tierClasses(l.tier)}`}
                        >
                          {l.tier}
                        </span>
                      ) : (
                        <span className="text-muted-foreground text-xs">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right font-semibold">
                      {l.composite_score ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground hidden md:table-cell">
                      {cleanDate(l.report_date) || safeDate(l.created_at)?.toLocaleDateString() || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Mobile — card list */}
            <ul className="sm:hidden divide-y divide-border">
              {rows.map((l) => (
                <li key={l.id}>
                  <Link
                    to="/leads/$leadId"
                    params={{ leadId: l.id }}
                    className="flex items-start gap-3 p-3 hover:bg-accent/30 active:bg-accent/40 cursor-pointer focus-visible:bg-accent/40 focus-visible:outline-none"
                  >
                    <div
                      className={`h-10 w-10 rounded-lg grid place-items-center font-semibold text-sm shrink-0 ${
                        (l.composite_score ?? 0) >= 80
                          ? "bg-[oklch(0.65_0.22_25)]/15 text-[oklch(0.7_0.22_25)]"
                          : (l.composite_score ?? 0) >= 60
                            ? "bg-[oklch(0.75_0.17_70)]/15 text-[oklch(0.78_0.17_70)]"
                            : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {l.composite_score ?? "—"}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="font-medium truncate flex items-center gap-1.5">
                        <span className="truncate">{l.lead_name}</span>
                        {isDuplicate(l) && cleanDate(l.report_date) && (
                          <span
                            className="text-[9px] px-1.5 py-0.5 rounded bg-accent/40 border border-border text-muted-foreground font-normal shrink-0"
                            title={`Re-scored snapshot from ${cleanDate(l.report_date)}`}
                          >
                            {cleanDate(l.report_date)}
                          </span>
                        )}
                        {l.creator_unopened && (
                          <span
                            className="inline-flex items-center gap-1 text-[9px] px-1.5 py-0.5 rounded-full font-medium bg-emerald-500/12 border border-emerald-500/30 text-emerald-700 dark:text-emerald-300 shrink-0"
                            title="Your dossier finished — you haven't opened it yet"
                          >
                            <span className="h-1 w-1 rounded-full bg-emerald-500" />
                            New
                          </span>
                        )}
                        {l.icp_stars === 5 && (
                          <span
                            className="text-[9px] px-1.5 py-0.5 rounded-full font-medium bg-amber-500/15 border border-amber-500/30 text-amber-700 dark:text-amber-300 shrink-0"
                            title="Ideal-fit account — ICP ★5"
                          >
                            ICP★5
                          </span>
                        )}
                        {staleReportDate(l.report_date) && (
                          <span
                            className="text-[9px] px-1.5 py-0.5 rounded bg-accent/40 border border-border text-muted-foreground font-normal shrink-0"
                            title="Report is over 90 days old — may need a refresh"
                          >
                            Stale
                          </span>
                        )}
                        {(l.confidence || "").toUpperCase() === "LOW" && (
                          <span
                            className="text-[9px] px-1.5 py-0.5 rounded-full font-medium bg-rose-500/12 border border-rose-500/30 text-rose-700 dark:text-rose-300 shrink-0"
                            title="Low confidence — verify before acting"
                          >
                            Low conf
                          </span>
                        )}
                        {isAdmin && <EngineBadge engine={l.generation_engine} />}
                      </div>
                      {l.lead_title && (
                        <div className="text-xs text-muted-foreground truncate">{l.lead_title}</div>
                      )}
                      <div className="text-xs text-muted-foreground truncate mt-0.5">
                        {l.company || "—"}
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-1 shrink-0">
                      {l.tier && (
                        <span
                          className={`text-[10px] px-2 py-0.5 rounded-full uppercase tracking-wider ${tierClasses(l.tier)}`}
                        >
                          {l.tier}
                        </span>
                      )}
                      <span className="text-[10px] text-muted-foreground">
                        {cleanDate(l.report_date) || safeDate(l.created_at)?.toLocaleDateString() || "—"}
                      </span>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          </>
        )}
      </Card>
    </div>
  );
}
