import { useEffect, useMemo, useState } from "react";
import { Link } from "@tanstack/react-router";
import { useServerFn } from "@tanstack/react-start";
import { getDashboardStats, listLeads } from "@/server/leads.functions";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Loader2, Upload, FileSearch, TrendingUp, Flame,
  ArrowRight, ArrowUpRight, Snowflake, Thermometer, Building2,
  Activity, Sparkles, Calendar, ChevronRight,
} from "lucide-react";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip,
  RadialBarChart, RadialBar, PolarAngleAxis,
} from "recharts";
import { tierClasses, tierColor } from "@/lib/tier";

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
type HotLead = {
  id: string; lead_name: string; lead_title: string | null; company: string | null;
  composite_score: number | null; tier: string | null;
};

export function DashboardPage() {
  const statsFn = useServerFn(getDashboardStats);
  const leadsFn = useServerFn(listLeads);
  const [data, setData] = useState<{ leads: StatsLead[]; signals: StatsSignal[] } | null>(null);
  const [hotLeads, setHotLeads] = useState<HotLead[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      statsFn().then((d) => setData(d as { leads: StatsLead[]; signals: StatsSignal[] })),
      leadsFn({ data: {} }).then((r) => setHotLeads((r as { leads: HotLead[] }).leads.slice(0, 6))),
    ]).finally(() => setLoading(false));
  }, [statsFn, leadsFn]);

  const stats = useMemo(() => {
    const leads = data?.leads ?? [];
    const signals = data?.signals ?? [];
    const total = leads.length;
    const tiers = { HOT: 0, WARM: 0, COLD: 0 } as Record<string, number>;
    let scoreSum = 0, scoreN = 0;
    const dimSum = { fit: 0, intent: 0, timing: 0, budget: 0 };
    const dimN = { fit: 0, intent: 0, timing: 0, budget: 0 };
    const buckets: { name: string; min: number; max: number; value: number }[] = [
      { name: "0-19", min: 0, max: 19, value: 0 },
      { name: "20-39", min: 20, max: 39, value: 0 },
      { name: "40-59", min: 40, max: 59, value: 0 },
      { name: "60-79", min: 60, max: 79, value: 0 },
      { name: "80-100", min: 80, max: 100, value: 0 },
    ];
    const byCompany: Record<string, { count: number; total: number }> = {};
    const byWeek: Record<string, { count: number; scoreSum: number; scoreN: number }> = {};

    for (const l of leads) {
      if (l.tier && tiers[l.tier] !== undefined) tiers[l.tier]++;
      if (l.composite_score != null) {
        scoreSum += l.composite_score; scoreN++;
        const s = l.composite_score;
        const b = buckets.find((bk) => s >= bk.min && s <= bk.max);
        if (b) b.value++;
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
      const d = new Date(l.created_at);
      const monday = new Date(d);
      monday.setUTCDate(d.getUTCDate() - ((d.getUTCDay() + 6) % 7));
      const wk = monday.toISOString().slice(0, 10);
      const w = (byWeek[wk] ||= { count: 0, scoreSum: 0, scoreN: 0 });
      w.count++;
      if (l.composite_score != null) { w.scoreSum += l.composite_score; w.scoreN++; }
    }

    const dims = [
      { name: "Fit", value: dimN.fit ? Math.round(dimSum.fit / dimN.fit) : 0 },
      { name: "Intent", value: dimN.intent ? Math.round(dimSum.intent / dimN.intent) : 0 },
      { name: "Timing", value: dimN.timing ? Math.round(dimSum.timing / dimN.timing) : 0 },
      { name: "Budget", value: dimN.budget ? Math.round(dimSum.budget / dimN.budget) : 0 },
    ];

    const companyData = Object.entries(byCompany)
      .map(([name, v]) => ({ name, count: v.count, avgScore: v.count ? Math.round(v.total / v.count) : 0 }))
      .sort((a, b) => b.count - a.count || b.avgScore - a.avgScore)
      .slice(0, 8);

    const weekData = Object.entries(byWeek)
      .sort(([a], [b]) => a.localeCompare(b))
      .slice(-12)
      .map(([wk, v]) => ({
        name: wk.slice(5),
        New: v.count,
        AvgScore: v.scoreN ? Math.round(v.scoreSum / v.scoreN) : 0,
      }));

    const tally = (type: string) => {
      const m: Record<string, { count: number; pts: number; n: number }> = {};
      for (const s of signals) {
        if (s.signal_type !== type) continue;
        const x = (m[s.label] ||= { count: 0, pts: 0, n: 0 });
        x.count++;
        if (s.points != null) { x.pts += s.points; x.n++; }
      }
      return Object.entries(m)
        .map(([name, v]) => ({ name, count: v.count, avgPts: v.n ? Math.round(v.pts / v.n) : 0, type }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 6);
    };

    return {
      total,
      hot: tiers.HOT, warm: tiers.WARM, cold: tiers.COLD,
      avgScore: scoreN ? Math.round(scoreSum / scoreN) : 0,
      buckets, dims, companyData, weekData,
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

  const hotShare = stats.total ? Math.round((stats.hot / stats.total) * 100) : 0;

  return (
    <div className="space-y-6">
      {/* Hero header */}
      <div className="relative overflow-hidden rounded-xl border border-border bg-gradient-to-br from-primary/10 via-card to-card p-6">
        <div className="absolute -right-16 -top-16 h-56 w-56 rounded-full bg-primary/15 blur-3xl pointer-events-none" />
        <div className="relative flex items-end justify-between gap-4 flex-wrap">
          <div>
            <div className="text-[10px] uppercase tracking-[0.25em] text-primary/80">Intel Hub</div>
            <h1 className="text-3xl font-semibold tracking-tight mt-1">Collective Lead Intelligence</h1>
            <p className="text-sm text-muted-foreground mt-1">
              {stats.total} dossier{stats.total === 1 ? "" : "s"} · {stats.hot} hot · avg score {stats.avgScore}
            </p>
          </div>
          <div className="flex gap-2">
            <Link to="/upload"><Button variant="outline"><Upload className="h-4 w-4 mr-2" /> Upload</Button></Link>
            <Link to="/leads"><Button><FileSearch className="h-4 w-4 mr-2" /> Browse leads</Button></Link>
          </div>
        </div>
      </div>

      {/* KPI strip — clickable */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiTile to="/leads" search={{}} label="Total dossiers" value={stats.total} icon={<FileSearch className="h-3.5 w-3.5" />} />
        <KpiTile to="/leads" search={{ tier: "HOT" }} label="Hot leads" value={stats.hot} suffix={`${hotShare}%`} accent="hot" icon={<Flame className="h-3.5 w-3.5" />} />
        <KpiTile to="/leads" search={{ tier: "WARM" }} label="Warm leads" value={stats.warm} accent="warm" icon={<Thermometer className="h-3.5 w-3.5" />} />
        <KpiTile to="/leads" search={{ tier: "COLD" }} label="Cold leads" value={stats.cold} accent="cold" icon={<Snowflake className="h-3.5 w-3.5" />} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Hot leads spotlight — direct dossier links */}
        <Card className="p-5 lg:col-span-2 relative overflow-hidden">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="text-xs uppercase tracking-widest text-muted-foreground">Top opportunities</div>
              <div className="text-sm font-medium mt-0.5">Highest-scoring dossiers right now</div>
            </div>
            <Link to="/leads" search={{ tier: "HOT" }} className="text-xs text-primary hover:underline inline-flex items-center gap-1">
              View all hot <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          {hotLeads.length === 0 ? (
            <Empty>No leads yet</Empty>
          ) : (
            <ul className="divide-y divide-border">
              {hotLeads.map((l) => (
                <li key={l.id}>
                  <Link
                    to="/leads/$leadId"
                    params={{ leadId: l.id }}
                    className="flex items-center gap-3 py-2.5 group"
                  >
                    <div className={`h-9 w-9 rounded-lg grid place-items-center font-semibold text-sm shrink-0 ${
                      (l.composite_score ?? 0) >= 80 ? "bg-[oklch(0.65_0.22_25)]/15 text-[oklch(0.7_0.22_25)]"
                        : (l.composite_score ?? 0) >= 60 ? "bg-[oklch(0.75_0.17_70)]/15 text-[oklch(0.78_0.17_70)]"
                        : "bg-muted text-muted-foreground"
                    }`}>
                      {l.composite_score ?? "—"}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="font-medium truncate group-hover:text-primary">{l.lead_name}</div>
                      <div className="text-xs text-muted-foreground truncate">
                        {[l.lead_title, l.company].filter(Boolean).join(" · ") || "—"}
                      </div>
                    </div>
                    {l.tier && (
                      <span className={`text-[10px] px-2 py-0.5 rounded-full uppercase tracking-wider ${tierClasses(l.tier)}`}>
                        {l.tier}
                      </span>
                    )}
                    <ChevronRight className="h-4 w-4 text-muted-foreground group-hover:text-primary group-hover:translate-x-0.5 transition" />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {/* Tier ring */}
        <Card className="p-5">
          <div className="text-xs uppercase tracking-widest text-muted-foreground">Tier distribution</div>
          <div className="mt-2 relative">
            <ResponsiveContainer width="100%" height={200}>
              <RadialBarChart
                innerRadius="60%" outerRadius="100%"
                data={[
                  { name: "HOT", value: stats.hot, fill: tierColor("HOT") },
                  { name: "WARM", value: stats.warm, fill: tierColor("WARM") },
                  { name: "COLD", value: stats.cold, fill: tierColor("COLD") },
                ]}
                startAngle={90} endAngle={-270}
              >
                <PolarAngleAxis type="number" domain={[0, Math.max(stats.total, 1)]} tick={false} />
                <RadialBar background dataKey="value" cornerRadius={6} />
                <Tooltip contentStyle={tooltipStyle} />
              </RadialBarChart>
            </ResponsiveContainer>
            <div className="absolute inset-0 grid place-items-center pointer-events-none">
              <div className="text-center">
                <div className="text-3xl font-bold">{stats.total}</div>
                <div className="text-[10px] uppercase tracking-widest text-muted-foreground">dossiers</div>
              </div>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-2 mt-3">
            {(["HOT", "WARM", "COLD"] as const).map((t) => {
              const v = t === "HOT" ? stats.hot : t === "WARM" ? stats.warm : stats.cold;
              return (
                <Link key={t} to="/leads" search={{ tier: t }}
                  className="rounded-md border border-border p-2 hover:border-primary/40 hover:bg-accent/30 transition group">
                  <div className="flex items-center justify-between">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded uppercase tracking-wider ${tierClasses(t)}`}>{t}</span>
                    <ArrowUpRight className="h-3 w-3 text-muted-foreground group-hover:text-primary" />
                  </div>
                  <div className="text-lg font-semibold mt-1">{v}</div>
                </Link>
              );
            })}
          </div>
        </Card>

        {/* Score histogram — clickable buckets */}
        <Card className="p-5 lg:col-span-2">
          <div className="flex items-center justify-between mb-3">
            <div className="text-xs uppercase tracking-widest text-muted-foreground">Score distribution</div>
            <div className="text-xs text-muted-foreground">Click any band to filter leads</div>
          </div>
          <div className="grid grid-cols-5 gap-2 items-end h-40">
            {stats.buckets.map((b) => {
              const max = Math.max(...stats.buckets.map((x) => x.value), 1);
              const h = Math.max(4, Math.round((b.value / max) * 100));
              const hue = b.min >= 80 ? 25 : b.min >= 60 ? 70 : b.min >= 40 ? 145 : b.min >= 20 ? 200 : 250;
              return (
                <Link
                  key={b.name}
                  to="/leads"
                  search={{ min: b.min, max: b.max }}
                  className="group flex flex-col items-stretch h-full justify-end"
                >
                  <div className="text-center text-sm font-semibold mb-1">{b.value}</div>
                  <div
                    className="rounded-md border border-transparent group-hover:border-primary/40 transition"
                    style={{
                      height: `${h}%`,
                      background: `linear-gradient(to top, oklch(0.55 0.18 ${hue}), oklch(0.72 0.16 ${hue}))`,
                    }}
                  />
                  <div className="text-[10px] text-center mt-1 text-muted-foreground group-hover:text-primary">{b.name}</div>
                </Link>
              );
            })}
          </div>
        </Card>

        {/* Dimension averages */}
        <Card className="p-5">
          <div className="text-xs uppercase tracking-widest text-muted-foreground mb-3">Dimension averages</div>
          <div className="space-y-3">
            {stats.dims.map((d) => (
              <div key={d.name}>
                <div className="flex justify-between text-xs">
                  <span className="text-muted-foreground">{d.name}</span>
                  <span className="font-semibold">{d.value}%</span>
                </div>
                <div className="h-2 rounded bg-muted mt-1 overflow-hidden">
                  <div
                    className="h-full"
                    style={{
                      width: `${d.value}%`,
                      background: "linear-gradient(to right, oklch(0.6 0.2 275), oklch(0.75 0.18 200))",
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Weekly trend */}
        <Card className="p-5 lg:col-span-3">
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="text-xs uppercase tracking-widest text-muted-foreground flex items-center gap-1">
                <Calendar className="h-3 w-3" /> Activity over time
              </div>
              <div className="text-sm mt-0.5">New dossiers per week and rolling avg score</div>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={stats.weekData} margin={{ top: 5, right: 8, left: -10, bottom: 0 }}>
              <defs>
                <linearGradient id="areaNew" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="oklch(0.65 0.19 275)" stopOpacity={0.7} />
                  <stop offset="100%" stopColor="oklch(0.65 0.19 275)" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="areaScore" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="oklch(0.78 0.17 70)" stopOpacity={0.5} />
                  <stop offset="100%" stopColor="oklch(0.78 0.17 70)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="name" tick={{ fill: "oklch(0.7 0.02 250)", fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: "oklch(0.7 0.02 250)", fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={tooltipStyle} />
              <Area type="monotone" dataKey="New" stroke="oklch(0.65 0.19 275)" strokeWidth={2} fill="url(#areaNew)" />
              <Area type="monotone" dataKey="AvgScore" stroke="oklch(0.78 0.17 70)" strokeWidth={2} fill="url(#areaScore)" />
            </AreaChart>
          </ResponsiveContainer>
        </Card>

        {/* Pipeline by company — clickable */}
        <Card className="p-5 lg:col-span-2">
          <div className="flex items-center justify-between mb-3">
            <div className="text-xs uppercase tracking-widest text-muted-foreground flex items-center gap-1">
              <Building2 className="h-3 w-3" /> Pipeline by company
            </div>
          </div>
          {stats.companyData.length === 0 ? (
            <Empty>No companies yet</Empty>
          ) : (
            <ul className="space-y-1.5">
              {stats.companyData.map((c) => {
                const max = Math.max(...stats.companyData.map((x) => x.count), 1);
                return (
                  <li key={c.name}>
                    <Link
                      to="/leads"
                      search={{ company: c.name }}
                      className="block rounded-md px-2 py-1.5 hover:bg-accent/40 group"
                    >
                      <div className="flex items-center justify-between text-sm">
                        <span className="truncate font-medium group-hover:text-primary">{c.name}</span>
                        <div className="flex items-center gap-3 text-xs text-muted-foreground shrink-0">
                          <span>{c.count} lead{c.count > 1 ? "s" : ""}</span>
                          <span className="font-semibold text-foreground w-8 text-right">{c.avgScore}</span>
                          <ChevronRight className="h-3 w-3 group-hover:text-primary" />
                        </div>
                      </div>
                      <div className="h-1 rounded bg-muted mt-1 overflow-hidden">
                        <div className="h-full bg-primary/70" style={{ width: `${(c.count / max) * 100}%` }} />
                      </div>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>

        {/* Signals — clickable */}
        <Card className="p-5">
          <div className="text-xs uppercase tracking-widest text-muted-foreground flex items-center gap-1 mb-3">
            <Sparkles className="h-3 w-3" /> Top score drivers
          </div>
          <SignalChips items={stats.attribution} />
        </Card>

        <Card className="p-5">
          <div className="text-xs uppercase tracking-widest text-muted-foreground flex items-center gap-1 mb-3">
            <Activity className="h-3 w-3" /> Compliance frameworks
          </div>
          <SignalChips items={stats.compliance} />
        </Card>

        <Card className="p-5 lg:col-span-2">
          <div className="text-xs uppercase tracking-widest text-muted-foreground flex items-center gap-1 mb-3">
            <TrendingUp className="h-3 w-3" /> Competitive threats
          </div>
          <SignalChips items={stats.competitors} />
        </Card>
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

function KpiTile({
  to, search, label, value, suffix, accent, icon,
}: {
  to: "/leads"; search: Record<string, string | number | undefined>;
  label: string; value: number; suffix?: string;
  accent?: "hot" | "warm" | "cold"; icon?: React.ReactNode;
}) {
  const ring = accent === "hot" ? "from-[oklch(0.65_0.22_25)]/20"
    : accent === "warm" ? "from-[oklch(0.75_0.17_70)]/20"
    : accent === "cold" ? "from-[oklch(0.65_0.13_230)]/20"
    : "from-primary/15";
  const text = accent === "hot" ? "text-[oklch(0.7_0.22_25)]"
    : accent === "warm" ? "text-[oklch(0.78_0.17_70)]"
    : accent === "cold" ? "text-[oklch(0.7_0.13_230)]"
    : "text-foreground";
  return (
    <Link to={to} search={search} className="group">
      <Card className={`p-4 relative overflow-hidden bg-gradient-to-br ${ring} to-card hover:border-primary/40 transition`}>
        <div className="text-[10px] uppercase tracking-widest text-muted-foreground flex items-center gap-1">
          {icon} {label}
        </div>
        <div className="flex items-end justify-between mt-1">
          <div className={`text-3xl font-bold ${text}`}>{value}</div>
          {suffix && <div className="text-xs text-muted-foreground mb-1">{suffix}</div>}
        </div>
        <ArrowUpRight className="absolute top-3 right-3 h-3.5 w-3.5 text-muted-foreground group-hover:text-primary" />
      </Card>
    </Link>
  );
}

function SignalChips({ items }: { items: { name: string; count: number; avgPts: number; type: string }[] }) {
  if (items.length === 0) return <Empty>No data yet</Empty>;
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((i) => (
        <Link
          key={`${i.type}-${i.name}`}
          to="/leads"
          search={{ signal: i.name, signal_type: i.type }}
          className="group inline-flex items-center gap-2 px-2.5 py-1.5 rounded-full border border-border bg-accent/30 hover:bg-primary/10 hover:border-primary/40 transition"
        >
          <span className="text-xs font-medium group-hover:text-primary">{i.name}</span>
          <span className="text-[10px] text-muted-foreground">{i.count}</span>
          {i.avgPts > 0 && <span className="text-[10px] text-primary/80 font-semibold">+{i.avgPts}</span>}
        </Link>
      ))}
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <div className="text-sm text-muted-foreground py-6 text-center">{children}</div>;
}