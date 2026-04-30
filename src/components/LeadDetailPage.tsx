import { useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";
import { useServerFn } from "@tanstack/react-start";
import { getLead, deleteLead } from "@/server/leads.functions";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Loader2, Trash2 } from "lucide-react";
import { tierClasses } from "@/lib/tier";

type LeadRow = {
  id: string; lead_name: string; lead_title: string | null; company: string | null;
  email: string | null; report_date: string | null; eliss_version: string | null;
  composite_score: number | null; tier: string | null; confidence: string | null;
  icp_rating: string | null; icp_reason: string | null;
  fit_score: number | null; fit_max: number | null; fit_conf: string | null;
  intent_score: number | null; intent_max: number | null; intent_conf: string | null;
  timing_score: number | null; timing_max: number | null; timing_conf: string | null;
  budget_score: number | null; budget_max: number | null; budget_conf: string | null;
  verdict_headline: string | null; verdict_insight: string | null; verdict_next: string | null;
  executive_brief: string | null;
};
type Signal = { id: string; signal_type: string; label: string; points: number | null; detail: string | null };

export function LeadDetailPage({ id }: { id: string }) {
  const get = useServerFn(getLead);
  const del = useServerFn(deleteLead);
  const [data, setData] = useState<{ lead: LeadRow; signals: Signal[]; html: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    get({ data: { id } })
      .then((r) => setData(r as { lead: LeadRow; signals: Signal[]; html: string }))
      .catch((e: Error) => setErr(e.message))
      .finally(() => setLoading(false));
  }, [get, id]);

  const onDelete = async () => {
    if (!confirm("Delete this dossier? This cannot be undone.")) return;
    await del({ data: { id } });
    window.location.href = "/leads";
  };

  if (loading) return <div className="grid place-items-center py-24"><Loader2 className="h-5 w-5 animate-spin text-muted-foreground" /></div>;
  if (err || !data) return <Card className="p-6 text-sm text-destructive">{err || "Not found"}</Card>;

  const { lead, signals, html } = data;
  const dim = (label: string, s: number | null, m: number | null) => {
    const pct = s != null && m ? Math.round((s / m) * 100) : null;
    return (
      <div>
        <div className="flex justify-between text-xs">
          <span className="text-muted-foreground">{label}</span>
          <span className="font-medium">{s ?? "—"}{m ? ` / ${m}` : ""}</span>
        </div>
        <div className="h-1.5 rounded bg-muted mt-1 overflow-hidden">
          <div className="h-full bg-primary" style={{ width: `${pct ?? 0}%` }} />
        </div>
      </div>
    );
  };

  const groupedSignals = signals.reduce<Record<string, Signal[]>>((acc, s) => {
    (acc[s.signal_type] ||= []).push(s); return acc;
  }, {});

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <Link to="/leads" className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4 mr-1" /> Back to leads
        </Link>
        <Button variant="ghost" size="sm" onClick={onDelete}>
          <Trash2 className="h-4 w-4 mr-2" /> Delete
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-4">
        <aside className="space-y-4">
          <Card className="p-5">
            <div className="text-xs uppercase tracking-widest text-muted-foreground">Lead</div>
            <div className="text-lg font-semibold mt-1">{lead.lead_name}</div>
            {lead.lead_title && <div className="text-sm text-muted-foreground">{lead.lead_title}</div>}
            {lead.company && <div className="text-sm mt-1">{lead.company}</div>}
            {lead.email && <div className="text-xs text-muted-foreground mt-1">{lead.email}</div>}
            <div className="mt-4 flex items-center gap-2">
              {lead.tier && (
                <span className={`text-[10px] px-2 py-0.5 rounded-full uppercase tracking-wider ${tierClasses(lead.tier)}`}>
                  {lead.tier}
                </span>
              )}
              <div className="text-3xl font-bold ml-auto">{lead.composite_score ?? "—"}</div>
            </div>
          </Card>

          <Card className="p-5 space-y-3">
            <div className="text-xs uppercase tracking-widest text-muted-foreground">Dimensions</div>
            {dim("Fit", lead.fit_score, lead.fit_max)}
            {dim("Intent", lead.intent_score, lead.intent_max)}
            {dim("Timing", lead.timing_score, lead.timing_max)}
            {dim("Budget", lead.budget_score, lead.budget_max)}
          </Card>

          {(lead.verdict_headline || lead.verdict_insight || lead.verdict_next) && (
            <Card className="p-5 space-y-2">
              <div className="text-xs uppercase tracking-widest text-muted-foreground">Verdict</div>
              {lead.verdict_headline && <div className="text-sm font-semibold">{lead.verdict_headline}</div>}
              {lead.verdict_insight && <p className="text-sm text-muted-foreground">{lead.verdict_insight}</p>}
              {lead.verdict_next && <p className="text-sm"><span className="text-muted-foreground">Next: </span>{lead.verdict_next}</p>}
            </Card>
          )}

          {Object.keys(groupedSignals).length > 0 && (
            <Card className="p-5 space-y-3">
              <div className="text-xs uppercase tracking-widest text-muted-foreground">Signals</div>
              {Object.entries(groupedSignals).map(([type, items]) => (
                <div key={type}>
                  <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">{type}</div>
                  <div className="flex flex-wrap gap-1">
                    {items.map((s) => (
                      <span key={s.id} className="text-xs px-2 py-0.5 rounded bg-accent/40 border border-border">
                        {s.label}{s.points != null ? ` +${s.points}` : ""}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </Card>
          )}
        </aside>

        <Card className="p-0 overflow-hidden">
          <div className="px-4 py-2 border-b border-border text-xs text-muted-foreground flex items-center justify-between">
            <span>Original dossier</span>
            {lead.report_date && <span>{lead.report_date}</span>}
          </div>
          <iframe
            title="Dossier"
            srcDoc={html}
            sandbox="allow-same-origin"
            className="w-full h-[80vh] bg-white"
          />
        </Card>
      </div>
    </div>
  );
}