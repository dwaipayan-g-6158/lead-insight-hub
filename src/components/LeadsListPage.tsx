import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { useServerFn } from "@tanstack/react-start";
import { listLeads } from "@/server/leads.functions";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Loader2, Search, Upload, X } from "lucide-react";
import { tierClasses } from "@/lib/tier";
import type { LeadListRow } from "@/types/leads";

export function LeadsListPage() {
  const fn = useServerFn(listLeads);
  const sp = useSearch({ from: "/leads/" });
  const navigate = useNavigate({ from: "/leads/" });
  const [search, setSearch] = useState(sp.q ?? "");
  const tier = sp.tier ?? "";
  const [rows, setRows] = useState<LeadListRow[]>([]);
  const [loading, setLoading] = useState(true);

  // keep input in sync if URL changes externally
  useEffect(() => { setSearch(sp.q ?? ""); }, [sp.q]);

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
        },
      })
        .then((r) => setRows((r as { leads: LeadListRow[] }).leads))
        .finally(() => setLoading(false));
    }, 200);
    return () => clearTimeout(t);
  }, [fn, search, tier, sp.company, sp.min, sp.max, sp.signal, sp.signal_type, sp.confidence]);

  const tiers = useMemo(() => ["", "HOT", "WARM", "COLD"] as const, []);

  const setTier = (t: "" | "HOT" | "WARM" | "COLD") => {
    navigate({ search: (prev) => ({ ...prev, tier: t || undefined }), replace: true });
  };
  const clearFilter = (key: "company" | "min" | "max" | "signal" | "signal_type" | "confidence") => {
    navigate({ search: (prev) => ({ ...prev, [key]: undefined }), replace: true });
  };
  const clearAll = () => {
    setSearch("");
    navigate({ search: {}, replace: true });
  };

  const activeFilters: { key: "company" | "min" | "max" | "signal" | "signal_type" | "confidence"; label: string }[] = [];
  if (sp.company) activeFilters.push({ key: "company", label: `Company: ${sp.company}` });
  if (sp.min != null) activeFilters.push({ key: "min", label: `Score ≥ ${sp.min}` });
  if (sp.max != null) activeFilters.push({ key: "max", label: `Score ≤ ${sp.max}` });
  if (sp.signal) activeFilters.push({ key: "signal", label: `Signal: ${sp.signal}` });
  if (sp.confidence) activeFilters.push({ key: "confidence", label: `Confidence: ${sp.confidence}` });

  return (
    <div className="space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 sm:gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Leads</h1>
          <p className="text-sm text-muted-foreground mt-1">Search every dossier in your collective intelligence</p>
        </div>
        <Link to="/upload" className="sm:w-auto">
          <Button className="w-full sm:w-auto"><Upload className="h-4 w-4 mr-2" /> Upload dossier</Button>
        </Link>
      </div>

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
                  tier === t ? "bg-primary/15 border-primary/40 text-primary" : "border-border text-muted-foreground hover:text-foreground"
                }`}
              >
                {t || "All"}
              </button>
            ))}
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
            <button onClick={clearAll} className="text-xs text-muted-foreground hover:text-foreground underline-offset-2 hover:underline ml-1">
              Clear all
            </button>
          </div>
        )}
      </Card>

      <Card className="p-0 overflow-hidden">
        {loading ? (
          <div className="grid place-items-center py-16 min-h-[60vh] text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
          </div>
        ) : rows.length === 0 ? (
          <div className="py-16 text-center text-sm text-muted-foreground">No leads match your search.</div>
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
                  <tr key={l.id} className="hover:bg-accent/30">
                    <td className="px-4 py-3">
                      <Link to="/leads/$leadId" params={{ leadId: l.id }} className="font-medium hover:text-primary">
                        {l.lead_name}
                      </Link>
                      {l.lead_title && <div className="text-xs text-muted-foreground">{l.lead_title}</div>}
                    </td>
                    <td className="px-4 py-3">{l.company || <span className="text-muted-foreground">—</span>}</td>
                    <td className="px-4 py-3">
                      {l.tier ? (
                        <span className={`text-[10px] px-2 py-0.5 rounded-full uppercase tracking-wider ${tierClasses(l.tier)}`}>
                          {l.tier}
                        </span>
                      ) : <span className="text-muted-foreground text-xs">—</span>}
                    </td>
                    <td className="px-4 py-3 text-right font-semibold">{l.composite_score ?? "—"}</td>
                    <td className="px-4 py-3 text-muted-foreground hidden md:table-cell">
                      {l.report_date || new Date(l.created_at).toLocaleDateString()}
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
                    className="flex items-start gap-3 p-3 hover:bg-accent/30 active:bg-accent/40"
                  >
                    <div className={`h-10 w-10 rounded-lg grid place-items-center font-semibold text-sm shrink-0 ${
                      (l.composite_score ?? 0) >= 80 ? "bg-[oklch(0.65_0.22_25)]/15 text-[oklch(0.7_0.22_25)]"
                        : (l.composite_score ?? 0) >= 60 ? "bg-[oklch(0.75_0.17_70)]/15 text-[oklch(0.78_0.17_70)]"
                        : "bg-muted text-muted-foreground"
                    }`}>
                      {l.composite_score ?? "—"}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="font-medium truncate">{l.lead_name}</div>
                      {l.lead_title && <div className="text-xs text-muted-foreground truncate">{l.lead_title}</div>}
                      <div className="text-xs text-muted-foreground truncate mt-0.5">
                        {l.company || "—"}
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-1 shrink-0">
                      {l.tier && (
                        <span className={`text-[10px] px-2 py-0.5 rounded-full uppercase tracking-wider ${tierClasses(l.tier)}`}>
                          {l.tier}
                        </span>
                      )}
                      <span className="text-[10px] text-muted-foreground">
                        {l.report_date || new Date(l.created_at).toLocaleDateString()}
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