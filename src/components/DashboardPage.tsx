import { useEffect, useMemo, useState } from "react";
import { Link } from "@tanstack/react-router";
import { getDashboardStats } from "@/server/leads.functions";
import { useServerFn } from "@tanstack/react-start";
import { Card } from "@/components/ui/card";
import { Loader2, Upload, FileSearch, TrendingUp, Flame } from "lucide-react";
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  LineChart, Line, Legend,
} from "recharts";
import { Button } from "@/components/ui/button";
import { tierColor } from "@/lib/tier";

type StatsLead = {
  id: string;
  composite_score: number | null;
  tier: string | null;
  company: string | null;
  fit_score: number | null; intent_score: number | null; timing_score: number | null; budget_score: number | null;
  fit_max: number | null; intent_max: number | null; timing_max: number | null; budget_max: number | null;
  created_at: string;
  report_date: string | null;
};
type StatsSignal = { signal_type: string; label: string; points: number | null };

export function DashboardPage() {
  const fn = useServerFn(getDashboardStats);
  const [data, setData] = useState<{ leads: StatsLead[]; signals: StatsSignal[] } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fn().then((d) => setData(d as { leads: StatsLead[]; signals: StatsSignal[] })).finally(() => setLoading(false));
  }, [fn]);

  const stats = useMemo(() => {
    const leads = data?.leads ?? [];
    const signals = data?.signals ?? [];
    const total = leads.length;
    const tiers = { HOT: 0, WARM: 0, COLD: 0 } as Record<string, number>;
    let scoreSum = 0, scoreN = 0;
    const dimSum = { fit: 0, intent: 0, timing: 0, budget: 0 };
    const dimN = { fit: 0, intent: 0, timing: 0, budget: 0 };
    const buckets: Record<string, number> = { "0-19": 0, "20-39": 0, "40-59": 0, "60-79": 0, "80-100": 0 };
    const byCompany: Record<string, { count: number; total: number }> = {};
    const byWeek: Record<string, { count: number; scoreSum: number; scoreN: number }> = {};

    for (const l of leads) {
      if (l.tier && tiers[l.tier] !== undefined) tiers[l.tier]++;
      if (l.composite_score != null) {
        scoreSum += l.composite_score; scoreN++;
        const s = l.composite_score;
        const bucket = s < 20 ? "0-19" : s < 40 ? "20-39" : s < 60 ? "40-59" : s < 80 ? "60-79" : "80-100";
        buckets[bucket]++;
      }
      const dimPct = (v: number | null, m: number | null) => (v != null && m ? (v / m) * 100 : null);
      const f = dimPct(l.fit_score, l.fit_max); if (f != null) { dimSum.fit += f; dimN.fit++; }
      const i = dimPct(l.intent_score, l.intent_max); if (i != null) { dimSum.intent += i; dimN.intent++; }
      const t = dimPct(l.timing_score, l.timing_max); if (t != null) { dimSum.timing += t; dimN.timing++; }
      const b = dimPct(l.budget_score, l.budget_max); if (b != null) { dimSum.budget += b; dimN.budget++; }
      if (l.company) {
        const c = (byCompany[l.company] ||= { count: 0, total: 0 });
        c.count++; if (l.composite_score != null) c.total += l.composite_score;
      }
      // Week bucket from created_at
      const d = new Date(l.created_at);
      const monday = new Date(d);
      monday.setUTCDate(d.getUTCDate() - ((d.getUTCDay() + 6) % 7));
      const wk = monday.toISOString().slice(0, 10);
      const w = (byWeek[wk] ||= { count: 0, scoreSum: 0, scoreN: 0 });
      w.count++;
      if (l.composite_score != null) { w.scoreSum += l.composite_score; w.scoreN++; }
    }

    const tierData = (Object.keys(tiers) as Array<keyof typeof tiers>).map((k) => ({
      name: k, value: tiers[k], color: tierColor(k),
    })).filter((d) => d.value > 0);

    const dimData = [
      { name: "Fit", value: dimN.fit ? Math.round(dimSum.fit / dimN.fit) : 0 },
      { name: "Intent", value: dimN.intent ? Math.round(dimSum.intent / dimN.intent) : 0 },
      { name: "Timing", value: dimN.timing ? Math.round(dimSum.timing / dimN.timing) : 0 },
      { name: "Budget", value: dimN.budget ? Math.round(dimSum.budget / dimN.budget) : 0 },
    ];

    const histData = Object.entries(buckets).map(([name, value]) => ({ name, value }));

    const companyData = Object.entries(byCompany)
      .map(([name, v]) => ({ name, count: v.count, avgScore: v.count ? Math.round(v.total / v.count) : 0 }))
      .sort((a, b) => b.count - a.count || b.avgScore - a.avgScore)
      .slice(0, 10);

    const weekData = Object.entries(byWeek)
      .sort(([a], [b]) => a.localeCompare(b))
      .slice(-12)
      .map(([wk, v]) => ({
        name: wk.slice(5),
        New: v.count,
        AvgScore: v.scoreN ? Math.round(v.scoreSum / v.scoreN) : 0,
      }));

    // Signal frequencies
    const tally = (type: string) => {
      const m: Record<string, { count: number; pts: number; n: number }> = {};
      for (const s of signals) {
        if (s.signal_type !== type) continue;
        const x = (m[s.label] ||= { count: 0, pts: 0, n: 0 });
        x.count++;
        if (s.points != null) { x.pts += s.points; x.n++; }
      }
      return Object.entries(m)
        .map(([name, v]) => ({ name, count: v.count, avgPts: v.n ? Math.round(v.pts / v.n) : 0 }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 8);
    };

    return {
      total,
      hot: tiers.HOT, warm: tiers.WARM, cold: tiers.COLD,
      avgScore: scoreN ? Math.round(scoreSum / scoreN) : 0,
      tierData, dimData, histData, companyData, weekData,
      compliance: tally("compliance"),
      attribution: tally("attribution"),
      competitors: tally("competitor"),
    };
  }, [data]);

  if (loading) {
    return <div className="grid place-items-center py-24 text-muted-foreground"><Loader2 className="h-5 w-5 animate-spin" /></div>;
  }

  if (stats.total === 0) {
    return (
      <Card className="p-12 text-center">
        <h2 className="text-xl font-semibold mb-2">Welcome to ELISS Intel Hub</h2>
        <p className="text-muted-foreground mb-6">Upload your first dossier to start building your collective lead intelligence.</p>
        <Link to="/upload"><Button><Upload className="h-4 w-4 mr-2" /> Upload first dossier</Button></Link>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-1">Collective intelligence across {stats.total} dossier{stats.total === 1 ? "" : "s"}</p>
        </div>
        <Link to="/leads"><Button variant="outline"><FileSearch className="h-4 w-4 mr-2" /> Browse leads</Button></Link>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <Kpi label="Total" value={stats.total} />
        <Kpi label="HOT" value={stats.hot} accent="hot" icon={<Flame className="h-3.5 w-3.5" />} />
        <Kpi label="WARM" value={stats.warm} accent="warm" />
        <Kpi label="COLD" value={stats.cold} accent="cold" />
        <Kpi label="Avg score" value={stats.avgScore} icon={<TrendingUp className="h-3.5 w-3.5" />} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <ChartCard title="Tier distribution" className="lg:col-span-1">
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie data={stats.tierData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={2}>
                {stats.tierData.map((d) => <Cell key={d.name} fill={d.color} />)}
              </Pie>
              <Tooltip contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Dimension averages (% of max)" className="lg:col-span-2">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={stats.dimData}>
              <CartesianGrid stroke="oklch(0.3 0.02 260)" strokeDasharray="3 3" />
              <XAxis dataKey="name" tick={{ fill: "oklch(0.7 0.02 250)", fontSize: 12 }} />
              <YAxis domain={[0, 100]} tick={{ fill: "oklch(0.7 0.02 250)", fontSize: 12 }} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="value" fill="oklch(0.65 0.19 275)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Score distribution" className="lg:col-span-1">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={stats.histData}>
              <CartesianGrid stroke="oklch(0.3 0.02 260)" strokeDasharray="3 3" />
              <XAxis dataKey="name" tick={{ fill: "oklch(0.7 0.02 250)", fontSize: 12 }} />
              <YAxis tick={{ fill: "oklch(0.7 0.02 250)", fontSize: 12 }} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="value" fill="oklch(0.7 0.18 145)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="New dossiers per week & avg score" className="lg:col-span-2">
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={stats.weekData}>
              <CartesianGrid stroke="oklch(0.3 0.02 260)" strokeDasharray="3 3" />
              <XAxis dataKey="name" tick={{ fill: "oklch(0.7 0.02 250)", fontSize: 11 }} />
              <YAxis yAxisId="left" tick={{ fill: "oklch(0.7 0.02 250)", fontSize: 11 }} />
              <YAxis yAxisId="right" orientation="right" domain={[0, 100]} tick={{ fill: "oklch(0.7 0.02 250)", fontSize: 11 }} />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line yAxisId="left" type="monotone" dataKey="New" stroke="oklch(0.65 0.19 275)" strokeWidth={2} dot={{ r: 3 }} />
              <Line yAxisId="right" type="monotone" dataKey="AvgScore" stroke="oklch(0.75 0.17 70)" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Top compliance frameworks" className="lg:col-span-1">
          <SignalList items={stats.compliance} unit="leads" />
        </ChartCard>

        <ChartCard title="Top score drivers (avg pts)" className="lg:col-span-1">
          <SignalList items={stats.attribution} unit="leads" valueLabel={(i) => `+${i.avgPts}`} />
        </ChartCard>

        <ChartCard title="Competitive threats" className="lg:col-span-1">
          {stats.competitors.length === 0 ? (
            <Empty>No competitor mentions detected</Empty>
          ) : (
            <SignalList items={stats.competitors} unit="leads" />
          )}
        </ChartCard>

        <ChartCard title="Pipeline by company" className="lg:col-span-3">
          {stats.companyData.length === 0 ? (
            <Empty>No companies yet</Empty>
          ) : (
            <div className="divide-y divide-border">
              {stats.companyData.map((c) => (
                <div key={c.name} className="flex items-center justify-between py-2 text-sm">
                  <span className="truncate pr-3">{c.name}</span>
                  <div className="flex gap-6 text-xs text-muted-foreground">
                    <span>{c.count} lead{c.count > 1 ? "s" : ""}</span>
                    <span className="text-foreground font-medium w-10 text-right">{c.avgScore}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </ChartCard>
      </div>
    </div>
  );
}

const tooltipStyle = {
  background: "oklch(0.21 0.025 260)",
  border: "1px solid oklch(0.3 0.025 260)",
  borderRadius: 8,
  fontSize: 12,
  color: "oklch(0.92 0.01 250)",
};

function Kpi({ label, value, accent, icon }: { label: string; value: number; accent?: "hot" | "warm" | "cold"; icon?: React.ReactNode }) {
  const color = accent === "hot" ? "text-[oklch(0.65_0.22_25)]"
    : accent === "warm" ? "text-[oklch(0.75_0.17_70)]"
    : accent === "cold" ? "text-[oklch(0.65_0.13_230)]"
    : "text-foreground";
  return (
    <Card className="p-4">
      <div className="text-[10px] uppercase tracking-widest text-muted-foreground flex items-center gap-1">
        {icon} {label}
      </div>
      <div className={`text-3xl font-bold mt-1 ${color}`}>{value}</div>
    </Card>
  );
}

function ChartCard({ title, children, className }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <Card className={`p-5 ${className ?? ""}`}>
      <div className="text-xs uppercase tracking-widest text-muted-foreground mb-4">{title}</div>
      {children}
    </Card>
  );
}

function SignalList({ items, unit, valueLabel }: { items: { name: string; count: number; avgPts: number }[]; unit: string; valueLabel?: (i: { count: number; avgPts: number }) => string }) {
  if (items.length === 0) return <Empty>No data yet</Empty>;
  const max = Math.max(...items.map((i) => i.count));
  return (
    <div className="space-y-2">
      {items.map((i) => (
        <div key={i.name}>
          <div className="flex justify-between text-xs">
            <span className="truncate pr-2">{i.name}</span>
            <span className="text-muted-foreground">{valueLabel ? valueLabel(i) : `${i.count} ${unit}`}</span>
          </div>
          <div className="h-1.5 rounded bg-muted mt-1 overflow-hidden">
            <div className="h-full bg-primary" style={{ width: `${(i.count / max) * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <div className="text-sm text-muted-foreground py-8 text-center">{children}</div>;
}