import { useEffect, useMemo, useState } from "react";
import { Link } from "@tanstack/react-router";
import { useServerFn } from "@tanstack/react-start";
import { listLeads } from "@/server/leads.functions";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Loader2, Search, Upload } from "lucide-react";
import { tierClasses } from "@/lib/tier";

type Row = {
  id: string;
  lead_name: string;
  lead_title: string | null;
  company: string | null;
  email: string | null;
  composite_score: number | null;
  tier: string | null;
  report_date: string | null;
  created_at: string;
};

export function LeadsListPage() {
  const fn = useServerFn(listLeads);
  const [search, setSearch] = useState("");
  const [tier, setTier] = useState<"" | "HOT" | "WARM" | "COLD">("");
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const t = setTimeout(() => {
      fn({ data: { search: search || undefined, tier: tier || undefined } })
        .then((r) => setRows((r as { leads: Row[] }).leads))
        .finally(() => setLoading(false));
    }, 200);
    return () => clearTimeout(t);
  }, [fn, search, tier]);

  const tiers = useMemo(() => ["", "HOT", "WARM", "COLD"] as const, []);

  return (
    <div className="space-y-5">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Leads</h1>
          <p className="text-sm text-muted-foreground mt-1">Search every dossier in your collective intelligence</p>
        </div>
        <Link to="/upload"><Button><Upload className="h-4 w-4 mr-2" /> Upload dossier</Button></Link>
      </div>

      <Card className="p-4">
        <div className="flex gap-2 flex-wrap">
          <div className="relative flex-1 min-w-[240px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by name, company, title, or email…"
              className="pl-9"
            />
          </div>
          <div className="flex gap-1">
            {tiers.map((t) => (
              <button
                key={t || "all"}
                onClick={() => setTier(t)}
                className={`px-3 py-1.5 text-xs rounded-md border ${
                  tier === t ? "bg-primary/15 border-primary/40 text-primary" : "border-border text-muted-foreground hover:text-foreground"
                }`}
              >
                {t || "All"}
              </button>
            ))}
          </div>
        </div>
      </Card>

      <Card className="p-0 overflow-hidden">
        {loading ? (
          <div className="grid place-items-center py-16 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
          </div>
        ) : rows.length === 0 ? (
          <div className="py-16 text-center text-sm text-muted-foreground">No leads match your search.</div>
        ) : (
          <table className="w-full text-sm">
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
        )}
      </Card>
    </div>
  );
}