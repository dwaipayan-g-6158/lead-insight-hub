import { useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";
import { useServerFn } from "@tanstack/react-start";
import { getLead, deleteLead } from "@/server/leads.functions";
import { useAuth } from "@/lib/auth";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { DimensionBar } from "@/components/DimensionBar";
import { ArrowLeft, Loader2, Trash2 } from "lucide-react";
import { tierClasses } from "@/lib/tier";
import type { LeadRow, Signal } from "@/types/leads";

export function LeadDetailPage({ id }: { id: string }) {
  const { isAdmin } = useAuth();
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

  const groupedSignals = signals.reduce<Record<string, Signal[]>>((acc, s) => {
    (acc[s.signal_type] ||= []).push(s); return acc;
  }, {});

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <Link to="/leads" className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4 mr-1" /> Back to leads
        </Link>
        {isAdmin && (
          <Button variant="ghost" size="sm" onClick={onDelete}>
            <Trash2 className="h-4 w-4 mr-2" /> Delete
          </Button>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-4 flex-1 min-h-0">
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
            <DimensionBar label="Fit" score={lead.fit_score} max={lead.fit_max} />
            <DimensionBar label="Intent" score={lead.intent_score} max={lead.intent_max} />
            <DimensionBar label="Timing" score={lead.timing_score} max={lead.timing_max} />
            <DimensionBar label="Budget" score={lead.budget_score} max={lead.budget_max} />
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

        <Card className="p-0 overflow-hidden flex flex-col sticky top-4" style={{ height: 'calc(100vh - 5rem)' }}>
          <div className="px-4 py-2 border-b border-border text-xs text-muted-foreground flex items-center justify-between shrink-0">
            <span>Original dossier</span>
            {lead.report_date && <span>{lead.report_date}</span>}
          </div>
          <iframe
            title="Dossier"
            srcDoc={html?.replace('</head>', `<style>
              ::-webkit-scrollbar { width: 8px; height: 8px; }
              ::-webkit-scrollbar-track { background: transparent; }
              ::-webkit-scrollbar-thumb { background: hsl(215 20% 65% / 0.4); border-radius: 9999px; }
              ::-webkit-scrollbar-thumb:hover { background: hsl(215 20% 65% / 0.6); }
              html { scrollbar-width: thin; scrollbar-color: hsl(215 20% 65% / 0.4) transparent; }
            </style></head>`)}
            sandbox="allow-same-origin allow-scripts"
            className="w-full flex-1 bg-white"
          />
        </Card>
      </div>
    </div>
  );
}