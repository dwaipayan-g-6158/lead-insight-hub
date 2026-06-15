import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { useServerFn } from "@/lib/use-server-fn";
import { getDashboardStats, listLeads } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useDossierActivity } from "@/lib/dossier-activity";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Upload,
  FileSearch,
  Flame,
  ArrowRight,
  ArrowUpRight,
  Snowflake,
  Thermometer,
  Building2,
  Activity,
  Sparkles,
  Calendar,
  ChevronRight,
  Star,
  ShieldCheck,
  Info,
  Clock,
  GripVertical,
  RotateCcw,
  Pencil,
  BarChart3,
  Target,
  Crosshair,
  MessageSquareQuote,
  Hourglass,
  Users,
  Layers,
  PieChart as PieChartIcon,
} from "lucide-react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  PieChart,
  Pie,
  Cell,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
} from "recharts";
import { tierClasses, tierColor } from "@/lib/tier";
import { safeDate } from "@/lib/utils";
import { useMounted } from "@/hooks/use-mounted";
import { useCountUp } from "@/hooks/use-count-up";
import type { StatsLead, StatsSignal } from "@/types/leads";

type HotLead = {
  id: string;
  lead_name: string;
  lead_title: string | null;
  company: string | null;
  composite_score: number | null;
  tier: string | null;
  // Extended fields used to disambiguate point-in-time duplicate dossiers
  // (e.g. same email re-scored on different dates) — see DashboardPage's
  // duplicateEmails computation.
  email?: string | null;
  report_date?: string | null;
};

type DashStats = {
  total: number;
  hot: number;
  warm: number;
  cold: number;
  avgScore: number;
  buckets: { name: string; min: number; max: number; value: number }[];
  dims: { name: string; value: number }[];
  companyData: { name: string; count: number; avgScore: number }[];
  weekData: { name: string; New: number; AvgScore: number }[];
  conf: { high: number; medium: number; low: number; unknown: number };
  icpLadder: number[];
  icpUnknown: number;
  recent: StatsLead[];
  compliance: { name: string; count: number; avgPts: number; type: string }[];
  attribution: { name: string; count: number; avgPts: number; type: string }[];
  competitors: { name: string; count: number; avgPts: number; type: string }[];
  headlines: { id: string; text: string }[];
  dimConf: { dim: string; high: number; medium: number; low: number; unknown: number }[];
  freshness: { fresh: number; aging: number; stale: number };
  freshLeadIds: string[];
  agingLeadIds: string[];
  staleLeadIds: string[];
  icpTier: { tier: string; stars: number[] }[];
  roleBreakdown: { role: string; count: number }[];
  // Lowercased emails that appear on >1 lead row. Widgets that show the
  // person's name without other disambiguators (Top Opportunities,
  // Recent Dossiers) consult this to decide whether to render a
  // report_date pill next to the name.
  duplicateEmails: Set<string>;
};

// ── helpers ──────────────────────────────────────────────────────────────
function confBucket(s: string | null | undefined): "high" | "medium" | "low" | "unknown" {
  const v = (s ?? "").toLowerCase();
  if (v.includes("high")) return "high";
  if (v.includes("med")) return "medium";
  if (v.includes("low")) return "low";
  return "unknown";
}
function icpStar(s: string | null | undefined): number | null {
  if (!s) return null;
  // Try numeric (e.g. "5/5", "4 stars")
  const m = s.match(/[1-5]/);
  if (m) return parseInt(m[0], 10);
  // Map text labels to stars
  const v = s.toLowerCase();
  if (/(excellent|perfect|ideal|bullseye|a\+|tier\s*1)/.test(v)) return 5;
  if (/(strong|great|high)/.test(v)) return 4;
  if (/(moderate|medium|good|fair|ok)/.test(v)) return 3;
  if (/(weak|low|marginal)/.test(v)) return 2;
  if (/(poor|none|very\s*weak|reject)/.test(v)) return 1;
  return null;
}
function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const sec = Math.max(1, Math.round(diff / 1000));
  if (sec < 60) return `${sec}s ago`;
  const min = Math.round(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const d = Math.round(hr / 24);
  if (d < 30) return `${d}d ago`;
  const mo = Math.round(d / 30);
  if (mo < 12) return `${mo}mo ago`;
  return `${Math.round(mo / 12)}y ago`;
}

// ── Stagger wrapper ──────────────────────────────────────────────────────
function Stagger({
  delay = 0,
  className = "",
  children,
}: {
  delay?: number;
  className?: string;
  children: React.ReactNode;
}) {
  const mounted = useMounted(delay);
  return (
    <div className={`dash-enter ${mounted ? "dash-enter-active" : ""} ${className}`}>
      {children}
    </div>
  );
}

// ── Animated KPI value ───────────────────────────────────────────────────
function AnimatedNumber({ value, className }: { value: number; className?: string }) {
  const v = useCountUp(value, 900);
  return <span className={className}>{v}</span>;
}

// ── Skeleton placeholder grid ────────────────────────────────────────────
function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="shimmer h-32 rounded-xl" />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="shimmer h-24 rounded-xl" />
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Skeleton className="shimmer h-72 rounded-xl lg:col-span-2" />
        <Skeleton className="shimmer h-72 rounded-xl" />
        <Skeleton className="shimmer h-56 rounded-xl lg:col-span-2" />
        <Skeleton className="shimmer h-56 rounded-xl" />
        <Skeleton className="shimmer h-56 rounded-xl lg:col-span-3" />
      </div>
    </div>
  );
}

// ── Widget ordering (localStorage-persisted) ─────────────────────────────
const STORAGE_KEY = "dash-widget-order";

function useWidgetOrder(defaultIds: string[]) {
  const [order, setOrder] = useState<string[]>(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const saved = JSON.parse(raw) as string[];
        // Reconcile: keep only known ids, append any new ones
        const known = new Set(defaultIds);
        const filtered = saved.filter((id) => known.has(id));
        const missing = defaultIds.filter((id) => !filtered.includes(id));
        return [...filtered, ...missing];
      }
    } catch {}
    return defaultIds;
  });

  const persist = useCallback((next: string[]) => {
    setOrder(next);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  }, []);

  const reset = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setOrder(defaultIds);
  }, [defaultIds]);

  return { order, setOrder: persist, reset };
}

// ── Drag-and-drop grid ───────────────────────────────────────────────────
type WidgetDef = {
  id: string;
  colSpan: 1 | 2 | 3;
  render: () => React.ReactNode;
};

function DraggableGrid({
  widgets,
  order,
  editing,
  onReorder,
}: {
  widgets: Map<string, WidgetDef>;
  order: string[];
  editing: boolean;
  onReorder: (next: string[]) => void;
}) {
  const dragIdx = useRef<number | null>(null);
  const [overIdx, setOverIdx] = useState<number | null>(null);

  const handleDragStart = (e: React.DragEvent, idx: number) => {
    dragIdx.current = idx;
    e.dataTransfer.effectAllowed = "move";
    // ghost
    const el = e.currentTarget as HTMLElement;
    e.dataTransfer.setDragImage(el, el.offsetWidth / 2, 24);
  };

  const handleDragOver = (e: React.DragEvent, idx: number) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    setOverIdx(idx);
  };

  const handleDrop = (e: React.DragEvent, dropIdx: number) => {
    e.preventDefault();
    const from = dragIdx.current;
    if (from == null || from === dropIdx) {
      setOverIdx(null);
      return;
    }
    const next = [...order];
    const [moved] = next.splice(from, 1);
    next.splice(dropIdx, 0, moved);
    onReorder(next);
    setOverIdx(null);
    dragIdx.current = null;
  };

  const handleDragEnd = () => {
    setOverIdx(null);
    dragIdx.current = null;
  };

  const colClass = (span: 1 | 2 | 3) =>
    span === 3 ? "lg:col-span-3" : span === 2 ? "lg:col-span-2" : "";

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
      {order.map((id, idx) => {
        const w = widgets.get(id);
        if (!w) return null;
        const isDragOver = overIdx === idx;
        return (
          <div
            key={id}
            className={`relative group/widget ${colClass(w.colSpan)} ${
              editing ? "cursor-grab active:cursor-grabbing" : ""
            } ${isDragOver ? "widget-drop-target" : ""}`}
            draggable={editing}
            onDragStart={(e) => handleDragStart(e, idx)}
            onDragOver={(e) => handleDragOver(e, idx)}
            onDrop={(e) => handleDrop(e, idx)}
            onDragEnd={handleDragEnd}
            onDragLeave={() => setOverIdx(null)}
          >
            {editing && (
              <div className="absolute -top-0.5 left-1/2 -translate-x-1/2 z-10 flex items-center gap-0.5 px-2 py-0.5 rounded-full bg-primary/90 text-primary-foreground text-[9px] uppercase tracking-widest font-semibold opacity-0 group-hover/widget:opacity-100 transition shadow-lg pointer-events-none">
                <GripVertical className="h-3 w-3" /> Drag
              </div>
            )}
            <Stagger delay={editing ? 0 : idx * 50 + 250} className="h-full">
              {w.render()}
            </Stagger>
          </div>
        );
      })}
    </div>
  );
}

export function DashboardPage() {
  const { isAdmin } = useAuth();
  const statsFn = useServerFn(getDashboardStats);
  const leadsFn = useServerFn(listLeads);
  const { leadsVersion } = useDossierActivity();
  const [data, setData] = useState<{ leads: StatsLead[]; signals: StatsSignal[] } | null>(null);
  const [hotLeads, setHotLeads] = useState<HotLead[]>([]);
  // Independent loading flags. Previously a single `loading` flag waited
  // for BOTH queries — on slow networks the user stared at the skeleton
  // for the slower of the two even though the faster one was ready. Now
  // statsLoading drives the widget grid (since most widgets read from
  // stats) and the dashboard becomes interactive as soon as stats lands.
  // hotLoading drives only the Top Opportunities widget skeleton state.
  const [statsLoading, setStatsLoading] = useState(true);
  const [hotLoading, setHotLoading] = useState(true);
  const loading = statsLoading; // overall page-level skeleton

  useEffect(() => {
    statsFn()
      .then((d) => setData(d as { leads: StatsLead[]; signals: StatsSignal[] }))
      .finally(() => setStatsLoading(false));
    leadsFn({ data: {} })
      .then((r) => {
        const result = r as { leads?: HotLead[] } | undefined;
        setHotLeads((result?.leads ?? []).slice(0, 6));
      })
      .finally(() => setHotLoading(false));
  }, [statsFn, leadsFn, leadsVersion]);

  const stats = useMemo(() => {
    const leads = data?.leads ?? [];
    const signals = data?.signals ?? [];
    const total = leads.length;
    const tiers = { HOT: 0, WARM: 0, COLD: 0 } as Record<string, number>;
    let scoreSum = 0,
      scoreN = 0;
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
    const conf = { high: 0, medium: 0, low: 0, unknown: 0 };
    // EXCLUSIVE buckets: icpLadder[N-1] = count of leads with star === N
    // (equivalent to ICP ≥ N AND ICP < N+1). Each lead lands in exactly
    // one row. The /leads?icp_min=N filter uses the same exact-bucket
    // semantics so clicking a row shows only that bucket.
    const icpLadder = [0, 0, 0, 0, 0];
    let icpUnknown = 0;

    for (const l of leads) {
      if (l.tier && tiers[l.tier] !== undefined) tiers[l.tier]++;
      if (l.composite_score != null) {
        scoreSum += l.composite_score;
        scoreN++;
        const s = l.composite_score;
        const b = buckets.find((bk) => s >= bk.min && s <= bk.max);
        if (b) b.value++;
      }
      const dimPct = (v: number | null, m: number | null) =>
        v != null && m ? (v / m) * 100 : null;
      const f = dimPct(l.fit_score, l.fit_max);
      if (f != null) {
        dimSum.fit += f;
        dimN.fit++;
      }
      const ix = dimPct(l.intent_score, l.intent_max);
      if (ix != null) {
        dimSum.intent += ix;
        dimN.intent++;
      }
      const tx = dimPct(l.timing_score, l.timing_max);
      if (tx != null) {
        dimSum.timing += tx;
        dimN.timing++;
      }
      const bx = dimPct(l.budget_score, l.budget_max);
      if (bx != null) {
        dimSum.budget += bx;
        dimN.budget++;
      }
      if (l.company) {
        const c = (byCompany[l.company] ||= { count: 0, total: 0 });
        c.count++;
        if (l.composite_score != null) c.total += l.composite_score;
      }
      const d = safeDate(l.created_at);
      if (!d) continue;
      const monday = new Date(d);
      monday.setUTCDate(d.getUTCDate() - ((d.getUTCDay() + 6) % 7));
      const wk = monday.toISOString().slice(0, 10);
      const w = (byWeek[wk] ||= { count: 0, scoreSum: 0, scoreN: 0 });
      w.count++;
      if (l.composite_score != null) {
        w.scoreSum += l.composite_score;
        w.scoreN++;
      }

      conf[confBucket(l.confidence)]++;
      const star = icpStar(l.icp_rating);
      if (star) {
        // Exclusive: a 4★ lead lands in icpLadder[3] only.
        icpLadder[star - 1]++;
      } else {
        icpUnknown++;
      }
    }

    const dims = [
      { name: "Fit", value: dimN.fit ? Math.round(dimSum.fit / dimN.fit) : 0 },
      { name: "Intent", value: dimN.intent ? Math.round(dimSum.intent / dimN.intent) : 0 },
      { name: "Timing", value: dimN.timing ? Math.round(dimSum.timing / dimN.timing) : 0 },
      { name: "Budget", value: dimN.budget ? Math.round(dimSum.budget / dimN.budget) : 0 },
    ];

    const companyData = Object.entries(byCompany)
      .map(([name, v]) => ({
        name,
        count: v.count,
        avgScore: v.count ? Math.round(v.total / v.count) : 0,
      }))
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

    // Recent dossiers
    const recent = [...leads]
      .sort(
        (a, b) =>
          (safeDate(b.created_at)?.getTime() ?? 0) -
          (safeDate(a.created_at)?.getTime() ?? 0),
      )
      .slice(0, 5);

    const tally = (type: string) => {
      // Canonicalize labels case-insensitively so "Compliance Need" and
      // "Compliance need" collapse to a single bucket. Keep the
      // first-seen display form (which is now title-cased by the
      // server-side parser canonicalizer, but legacy rows may still
      // carry their original casing — first-seen wins).
      const m: Record<string, { display: string; count: number; pts: number; n: number }> = {};
      for (const s of signals) {
        if (s.signal_type !== type || !s.label) continue;
        const key = s.label.toLowerCase().trim();
        const x = (m[key] ||= { display: s.label, count: 0, pts: 0, n: 0 });
        x.count++;
        if (s.points != null) {
          x.pts += s.points;
          x.n++;
        }
      }
      return Object.values(m)
        .map((v) => ({
          name: v.display,
          count: v.count,
          avgPts: v.n ? Math.round(v.pts / v.n) : 0,
          type,
        }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 6);
    };

    // Verdict headlines
    const headlines = leads
      .filter((l) => l.verdict_headline)
      .map((l) => ({ id: l.id, text: l.verdict_headline as string }))
      .slice(0, 6);

    // Dimension confidence heatmap
    const dcMap: Record<string, { high: number; medium: number; low: number; unknown: number }> = {
      Fit: { high: 0, medium: 0, low: 0, unknown: 0 },
      Intent: { high: 0, medium: 0, low: 0, unknown: 0 },
      Timing: { high: 0, medium: 0, low: 0, unknown: 0 },
      Budget: { high: 0, medium: 0, low: 0, unknown: 0 },
    };
    for (const l of leads) {
      dcMap.Fit[confBucket(l.fit_conf)]++;
      dcMap.Intent[confBucket(l.intent_conf)]++;
      dcMap.Timing[confBucket(l.timing_conf)]++;
      dcMap.Budget[confBucket(l.budget_conf)]++;
    }
    const dimConf = Object.entries(dcMap).map(([dim, v]) => ({ dim, ...v }));

    // Freshness (days since created)
    const now = Date.now();
    const day = 86_400_000;
    const freshness = { fresh: 0, aging: 0, stale: 0 };
    const freshLeadIds: string[] = [];
    const agingLeadIds: string[] = [];
    const staleLeadIds: string[] = [];
    for (const l of leads) {
      const d = safeDate(l.created_at);
      if (!d) continue;
      const age = (now - d.getTime()) / day;
      if (age <= 7) {
        freshness.fresh++;
        freshLeadIds.push(l.id);
      } else if (age <= 30) {
        freshness.aging++;
        agingLeadIds.push(l.id);
      } else {
        freshness.stale++;
        staleLeadIds.push(l.id);
      }
    }

    // ICP × Tier cross-tab
    const icpTierMap: Record<string, number[]> = {
      HOT: [0, 0, 0, 0, 0],
      WARM: [0, 0, 0, 0, 0],
      COLD: [0, 0, 0, 0, 0],
    };
    for (const l of leads) {
      const s = icpStar(l.icp_rating);
      if (s && l.tier && icpTierMap[l.tier]) icpTierMap[l.tier][s - 1]++;
    }
    const icpTier = Object.entries(icpTierMap).map(([tier, stars]) => ({ tier, stars }));

    // Role breakdown
    const roleMap: Record<string, number> = {};
    for (const l of leads) {
      const t = l.lead_title?.split(/[,/]/)[0]?.trim();
      if (t) roleMap[t] = (roleMap[t] || 0) + 1;
    }
    const roleBreakdown = Object.entries(roleMap)
      .map(([role, count]) => ({ role, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 6);

    // Duplicate detection: emails that appear on more than one lead row.
    // The dashboard rows (Top Opportunities, Recent Dossiers) show only
    // name + title + company, so two re-scored snapshots of the same
    // person are indistinguishable. When an email is in this set, the
    // UI surfaces a small report_date pill on each row to disambiguate.
    const emailCounts: Record<string, number> = {};
    for (const l of leads) {
      const e = (l as { email?: string | null }).email?.toLowerCase().trim();
      if (e) emailCounts[e] = (emailCounts[e] || 0) + 1;
    }
    const duplicateEmails = new Set(
      Object.entries(emailCounts).filter(([, n]) => n > 1).map(([e]) => e),
    );

    return {
      total,
      hot: tiers.HOT,
      warm: tiers.WARM,
      cold: tiers.COLD,
      avgScore: scoreN ? Math.round(scoreSum / scoreN) : 0,
      buckets,
      dims,
      companyData,
      weekData,
      conf,
      icpLadder,
      icpUnknown,
      recent,
      compliance: tally("compliance"),
      attribution: tally("attribution"),
      competitors: tally("competitor"),
      headlines,
      dimConf,
      freshness,
      freshLeadIds,
      agingLeadIds,
      staleLeadIds,
      icpTier,
      roleBreakdown,
      duplicateEmails,
    };
  }, [data]);

  // ── Widget definitions (must be before early returns — Rules of Hooks) ──
  const DEFAULT_ORDER = [
    "opportunities",
    "tier",
    "confidence",
    "icp",
    "roles",
    "drivers",
    "compliance",
    "threats",
    "headlines",
    "histogram",
    "radar",
    "weekly",
    "freshness",
    "dimconf",
    "icptier",
    "pipeline",
    "recent",
  ];

  const widgetOrder = useWidgetOrder(DEFAULT_ORDER);
  const [editing, setEditing] = useState(false);

  const widgetMap = useMemo(() => {
    const m = new Map<string, WidgetDef>();
    m.set("opportunities", {
      id: "opportunities",
      colSpan: 2,
      render: () => (
        <WidgetTopOpportunities hotLeads={hotLeads} stats={stats} loading={hotLoading} />
      ),
    });
    m.set("tier", { id: "tier", colSpan: 1, render: () => <WidgetTierRing stats={stats} /> });
    m.set("confidence", {
      id: "confidence",
      colSpan: 2,
      render: () => <WidgetConfidence stats={stats} />,
    });
    m.set("icp", { id: "icp", colSpan: 1, render: () => <WidgetIcpLadder stats={stats} /> });
    m.set("radar", { id: "radar", colSpan: 1, render: () => <WidgetRadar stats={stats} /> });
    m.set("histogram", {
      id: "histogram",
      colSpan: 2,
      render: () => <WidgetHistogram stats={stats} />,
    });
    m.set("recent", { id: "recent", colSpan: 1, render: () => <WidgetRecent stats={stats} /> });
    m.set("weekly", {
      id: "weekly",
      colSpan: 3,
      render: () => <WidgetWeeklyTrend stats={stats} />,
    });
    m.set("pipeline", {
      id: "pipeline",
      colSpan: 2,
      render: () => <WidgetPipeline stats={stats} />,
    });
    m.set("headlines", {
      id: "headlines",
      colSpan: 3,
      render: () => <WidgetHeadlines stats={stats} />,
    });
    m.set("freshness", {
      id: "freshness",
      colSpan: 1,
      render: () => (
        <WidgetFreshness
          stats={stats}
          freshLeadIds={stats.freshLeadIds}
          agingLeadIds={stats.agingLeadIds}
          staleLeadIds={stats.staleLeadIds}
        />
      ),
    });
    m.set("dimconf", {
      id: "dimconf",
      colSpan: 1,
      render: () => <WidgetDimConf stats={stats} />,
    });
    m.set("icptier", {
      id: "icptier",
      colSpan: 1,
      render: () => <WidgetIcpTier stats={stats} />,
    });
    m.set("roles", {
      id: "roles",
      colSpan: 1,
      render: () => <WidgetRoles stats={stats} />,
    });
    m.set("drivers", {
      id: "drivers",
      colSpan: 1,
      render: () => <WidgetDrivers stats={stats} />,
    });
    m.set("compliance", {
      id: "compliance",
      colSpan: 1,
      render: () => <WidgetCompliance stats={stats} />,
    });
    m.set("threats", {
      id: "threats",
      colSpan: 1,
      render: () => <WidgetThreats stats={stats} />,
    });
    return m;
  }, [stats, hotLeads]);

  if (loading) return <DashboardSkeleton />;

  if (stats.total === 0) {
    return (
      <Card className="p-12 text-center">
        <h2 className="text-xl font-semibold mb-2">Welcome to Intel Hub</h2>
        <p className="text-muted-foreground mb-6">
          {isAdmin
            ? "Upload your first dossier to start building your collective lead intelligence."
            : "Generate your first dossier to start building your lead intelligence."}
        </p>
        <Link to="/upload">
          <Button>
            {isAdmin ? (
              <>
                <Upload className="h-4 w-4 mr-2" /> Upload first dossier
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4 mr-2" /> Create first dossier
              </>
            )}
          </Button>
        </Link>
      </Card>
    );
  }

  const hotShare = stats.total ? Math.round((stats.hot / stats.total) * 100) : 0;

  return (
    <div className="space-y-3">
      {/* Hero */}
      <Stagger delay={0}>
        <div className="relative overflow-hidden rounded-xl border border-border bg-gradient-to-br from-primary/10 via-card to-card p-6 shadow-sm">
          <div className="absolute -right-16 -top-16 h-56 w-56 rounded-full bg-primary/10 blur-3xl pointer-events-none" />
          <div className="absolute -left-24 -bottom-24 h-48 w-48 rounded-full bg-primary/5 blur-3xl pointer-events-none" />
          <div className="relative flex items-end justify-between gap-4 flex-wrap">
            <div>
              <h1 className="text-3xl font-semibold tracking-tight">
                Enterprise Lead Intelligence
              </h1>
              <p className="text-sm text-muted-foreground mt-1.5">
                {stats.total} dossier{stats.total === 1 ? "" : "s"} · {stats.hot} hot · avg score{" "}
                {stats.avgScore}
              </p>
            </div>
            <div className="flex gap-2 items-center">
              <Link to="/upload">
                <Button variant="outline" size="sm">
                  {isAdmin ? (
                    <>
                      <Upload className="h-3.5 w-3.5 mr-1.5" /> Upload
                    </>
                  ) : (
                    <>
                      <Sparkles className="h-3.5 w-3.5 mr-1.5" /> Create
                    </>
                  )}
                </Button>
              </Link>
              <Link to="/leads">
                <Button size="sm">
                  <FileSearch className="h-3.5 w-3.5 mr-1.5" /> Browse leads
                </Button>
              </Link>
              <div className="w-px h-5 bg-border" />
              <Button
                variant={editing ? "default" : "ghost"}
                size="sm"
                onClick={() => setEditing(!editing)}
                className="text-xs gap-1.5 h-7"
              >
                <Pencil className="h-3 w-3" />
                {editing ? "Done" : "Edit layout"}
              </Button>
              {editing && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    widgetOrder.reset();
                    setEditing(false);
                  }}
                  className="text-xs gap-1.5 h-7"
                >
                  <RotateCcw className="h-3 w-3" /> Reset
                </Button>
              )}
            </div>
          </div>
        </div>
      </Stagger>

      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stagger delay={50}>
          <KpiTile
            to="/leads"
            search={{}}
            label="Total dossiers"
            value={stats.total}
            icon={<FileSearch className="h-3.5 w-3.5" />}
          />
        </Stagger>
        <Stagger delay={100}>
          <KpiTile
            to="/leads"
            search={{ tier: "HOT" }}
            label="Hot leads"
            value={stats.hot}
            suffix={`${hotShare}%`}
            accent="hot"
            icon={<Flame className="h-3.5 w-3.5" />}
          />
        </Stagger>
        <Stagger delay={150}>
          <KpiTile
            to="/leads"
            search={{ tier: "WARM" }}
            label="Warm leads"
            value={stats.warm}
            accent="warm"
            icon={<Thermometer className="h-3.5 w-3.5" />}
          />
        </Stagger>
        <Stagger delay={200}>
          <KpiTile
            to="/leads"
            search={{ tier: "COLD" }}
            label="Cold leads"
            value={stats.cold}
            accent="cold"
            icon={<Snowflake className="h-3.5 w-3.5" />}
          />
        </Stagger>
      </div>

      {/* Widget grid */}
      <DraggableGrid
        widgets={widgetMap}
        order={widgetOrder.order}
        editing={editing}
        onReorder={widgetOrder.setOrder}
      />
    </div>
  );
}

/* ═══════════════════════ WIDGET RENDERERS (extracted) ═══════════════════ */
/* They are defined as standalone functions that receive props so the main
   component can pass them into the WidgetDef config map. */

function WidgetTopOpportunities({
  hotLeads,
  stats,
  loading,
}: {
  hotLeads: HotLead[];
  stats: DashStats;
  loading?: boolean;
}) {
  return (
    <Card className="p-5 relative overflow-hidden h-full">
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="text-xs uppercase tracking-widest text-muted-foreground flex items-center gap-1">
            <Target className="h-3 w-3" /> Top opportunities
          </div>
          <div className="text-sm font-medium mt-0.5">Highest-scoring dossiers right now</div>
        </div>
        <Link
          to="/leads"
          search={{ tier: "HOT" }}
          className="text-xs text-primary hover:underline inline-flex items-center gap-1"
        >
          View all hot <ArrowRight className="h-3 w-3" />
        </Link>
      </div>
      {loading && hotLeads.length === 0 ? (
        // Per-widget skeleton: rendered while the leads list query is
        // still in flight even though stats already resolved. Without
        // this the user sees "No leads yet" briefly on slow networks.
        <div className="space-y-2.5">
          {[0, 1, 2, 3, 4].map((i) => (
            <div key={i} className="flex items-center gap-3">
              <Skeleton className="shimmer h-9 w-9 rounded-lg" />
              <div className="flex-1 space-y-1.5">
                <Skeleton className="shimmer h-3.5 w-1/2 rounded" />
                <Skeleton className="shimmer h-3 w-3/4 rounded" />
              </div>
            </div>
          ))}
        </div>
      ) : hotLeads.length === 0 ? (
        <Empty>No leads yet</Empty>
      ) : (
        <ul className="divide-y divide-border">
          {hotLeads.map((l) => {
            // Strip Catalyst's trailing midnight (" 00:00:00") so the
            // pill reads as a clean date string.
            const reportDate = l.report_date?.replace(/[ T]00:00:00.*$/, "") ?? null;
            const isDup =
              !!l.email && stats.duplicateEmails.has(l.email.toLowerCase().trim());
            return (
              <li key={l.id}>
                <Link
                  to="/leads/$leadId"
                  params={{ leadId: l.id }}
                  className="flex items-center gap-3 py-2.5 group"
                >
                  <div
                    className={`h-9 w-9 rounded-lg grid place-items-center font-semibold text-sm shrink-0 ${
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
                    <div className="font-medium truncate group-hover:text-primary flex items-center gap-2">
                      <span className="truncate">{l.lead_name}</span>
                      {isDup && reportDate && (
                        <span
                          className="text-[10px] px-1.5 py-0.5 rounded bg-accent/40 border border-border text-muted-foreground font-normal shrink-0"
                          title={`Re-scored snapshot from ${reportDate}`}
                        >
                          {reportDate}
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-muted-foreground truncate">
                      {[l.lead_title, l.company].filter(Boolean).join(" · ") || "—"}
                    </div>
                  </div>
                  {l.tier && (
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded-full uppercase tracking-wider ${tierClasses(l.tier)}`}
                    >
                      {l.tier}
                    </span>
                  )}
                  <ChevronRight className="h-4 w-4 text-muted-foreground group-hover:text-primary group-hover:translate-x-0.5 transition" />
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}

function WidgetTierRing({ stats }: { stats: DashStats }) {
  const navigate = useNavigate();
  const slices = [
    { name: "HOT" as const, value: stats.hot, fill: tierColor("HOT") },
    { name: "WARM" as const, value: stats.warm, fill: tierColor("WARM") },
    { name: "COLD" as const, value: stats.cold, fill: tierColor("COLD") },
  ].filter((d) => d.value > 0);
  return (
    <Card className="p-5 h-full">
      <div className="text-xs uppercase tracking-widest text-muted-foreground flex items-center gap-1">
        <PieChartIcon className="h-3 w-3" /> Tier distribution
      </div>
      <div className="mt-2 relative">
        <ResponsiveContainer width="100%" height={200}>
          <PieChart>
            <Pie
              data={slices}
              dataKey="value"
              cx="50%"
              cy="50%"
              innerRadius="60%"
              outerRadius="90%"
              paddingAngle={2}
              isAnimationActive
              onClick={(_, index) => {
                const tier = slices[index]?.name;
                if (tier) navigate({ to: "/leads", search: { tier } });
              }}
              style={{ cursor: "pointer" }}
            >
              {slices.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={entry.fill}
                  style={{ cursor: "pointer" }}
                />
              ))}
            </Pie>
            <Tooltip contentStyle={tooltipStyle} />
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 grid place-items-center pointer-events-none">
          <div className="text-center">
            <div className="text-3xl font-bold tabular-nums">
              <AnimatedNumber value={stats.total} />
            </div>
            <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
              dossiers
            </div>
          </div>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2 mt-3">
        {(["HOT", "WARM", "COLD"] as const).map((t) => {
          const v = t === "HOT" ? stats.hot : t === "WARM" ? stats.warm : stats.cold;
          return (
            <Link
              key={t}
              to="/leads"
              search={{ tier: t }}
              className="rounded-md border border-border p-2 hover:border-primary/40 hover:bg-accent/30 transition group"
            >
              <div className="flex items-center justify-between">
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded uppercase tracking-wider ${tierClasses(t)}`}
                >
                  {t}
                </span>
                <ArrowUpRight className="h-3 w-3 text-muted-foreground group-hover:text-primary" />
              </div>
              <div className="text-lg font-semibold mt-1">{v}</div>
            </Link>
          );
        })}
      </div>
    </Card>
  );
}

function WidgetConfidence({ stats }: { stats: DashStats }) {
  return (
    <Card className="p-5 h-full">
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="text-xs uppercase tracking-widest text-muted-foreground flex items-center gap-1">
            <ShieldCheck className="h-3 w-3" /> Verdict confidence
          </div>
          <div className="text-sm font-medium mt-0.5">How sure are we across the pipeline?</div>
        </div>
        <div className="text-xs text-muted-foreground">Click a band to filter</div>
      </div>
      <ConfidenceBar conf={stats.conf} total={stats.total} clickable />
      <div className="grid grid-cols-4 gap-2 mt-3">
        {(["high", "medium", "low", "unknown"] as const).map((b) => {
          const v = stats.conf[b];
          const pct = stats.total ? Math.round((v / stats.total) * 100) : 0;
          return (
            <Link
              key={b}
              to="/leads"
              search={{ confidence: b }}
              className="group rounded-md border border-border p-2 hover:border-primary/40 hover:bg-accent/30 transition"
            >
              <div className="flex items-center justify-between">
                <span className={`h-2 w-2 rounded-full ${confDotClass(b)}`} />
                <ArrowUpRight className="h-3 w-3 text-muted-foreground group-hover:text-primary" />
              </div>
              <div className="text-[10px] uppercase tracking-wider text-muted-foreground mt-1 capitalize">
                {b}
              </div>
              <div className="text-base font-semibold tabular-nums">
                {v}
                <span className="text-xs text-muted-foreground ml-1">· {pct}%</span>
              </div>
            </Link>
          );
        })}
      </div>
    </Card>
  );
}

function WidgetIcpLadder({ stats }: { stats: DashStats }) {
  return (
    <Card className="p-5 h-full">
      <div className="flex items-center justify-between mb-1">
        <div className="text-xs uppercase tracking-widest text-muted-foreground flex items-center gap-1">
          <Star className="h-3 w-3" /> ICP ladder
        </div>
        <span className="group relative inline-flex">
          <Info className="h-3.5 w-3.5 text-muted-foreground cursor-help" />
          <span className="pointer-events-none absolute right-0 top-5 z-10 w-56 rounded-md border border-border bg-popover p-2 text-[11px] text-muted-foreground opacity-0 shadow-md transition group-hover:opacity-100">
            <strong className="text-foreground">Ideal Customer Profile</strong> rates how closely
            each lead matches your target buyer (1★ weak fit → 5★ perfect fit). Click a row to see
            leads in exactly that star bucket.
          </span>
        </span>
      </div>
      <div className="space-y-1.5 mt-3">
        {[5, 4, 3, 2, 1].map((star) => {
          const v = stats.icpLadder[star - 1];
          const max = Math.max(...stats.icpLadder, 1);
          return <IcpRow key={star} star={star} value={v} max={max} />;
        })}
        {stats.icpUnknown > 0 && (
          <div className="text-[11px] text-muted-foreground pt-1.5">{stats.icpUnknown} unrated</div>
        )}
      </div>
    </Card>
  );
}

function WidgetRadar({ stats }: { stats: DashStats }) {
  return (
    <Card className="p-5 h-full">
      <div className="flex items-center justify-between mb-1">
        <div className="text-xs uppercase tracking-widest text-muted-foreground flex items-center gap-1">
          <Crosshair className="h-3 w-3" /> Dimension radar
        </div>
        <Link
          to="/leads"
          className="text-xs text-primary hover:underline inline-flex items-center gap-1"
        >
          View all <ArrowRight className="h-3 w-3" />
        </Link>
      </div>
      <div className="text-[11px] text-muted-foreground mb-2">Avg % across all dossiers</div>
      <ResponsiveContainer width="100%" height={220}>
        <RadarChart data={stats.dims} outerRadius="78%">
          <PolarGrid stroke="oklch(0.3 0.025 260)" />
          <PolarAngleAxis dataKey="name" tick={{ fill: "oklch(0.7 0.02 250)", fontSize: 11 }} />
          <Radar
            dataKey="value"
            stroke="oklch(0.65 0.19 275)"
            fill="oklch(0.65 0.19 275)"
            fillOpacity={0.35}
            isAnimationActive
            animationDuration={900}
          />
          <Tooltip contentStyle={tooltipStyle} formatter={(v) => `${v}%`} />
        </RadarChart>
      </ResponsiveContainer>
    </Card>
  );
}

function WidgetHistogram({ stats }: { stats: DashStats }) {
  return (
    <Card className="p-5 h-full">
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs uppercase tracking-widest text-muted-foreground flex items-center gap-1">
          <BarChart3 className="h-3 w-3" /> Score distribution
        </div>
        <div className="text-xs text-muted-foreground">Click any band to filter leads</div>
      </div>
      <div className="grid grid-cols-5 gap-2 items-end h-40">
        {stats.buckets.map((b, i) => (
          <BucketBar
            key={b.name}
            bucket={b}
            maxValue={Math.max(...stats.buckets.map((x) => x.value), 1)}
            delay={i * 60}
          />
        ))}
      </div>
    </Card>
  );
}

function WidgetRecent({ stats }: { stats: DashStats }) {
  return (
    <Card className="p-5 h-full">
      <div className="text-xs uppercase tracking-widest text-muted-foreground flex items-center gap-1 mb-3">
        <Clock className="h-3 w-3" /> Recent dossiers
      </div>
      {stats.recent.length === 0 ? (
        <Empty>Nothing yet</Empty>
      ) : (
        <ol className="relative space-y-3 before:absolute before:left-1.5 before:top-1.5 before:bottom-1.5 before:w-px before:bg-border">
          {stats.recent.map((l) => (
            <li key={l.id} className="relative pl-6">
              <span className="absolute left-0 top-1.5 h-3 w-3 rounded-full border-2 border-primary bg-card" />
              <Link to="/leads/$leadId" params={{ leadId: l.id }} className="group block">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm truncate group-hover:text-primary">
                    {l.lead_name ?? "—"}
                  </span>
                  {l.tier && (
                    <span
                      className={`text-[9px] px-1.5 py-0.5 rounded-full uppercase tracking-wider ${tierClasses(l.tier)}`}
                    >
                      {l.tier}
                    </span>
                  )}
                  <span className="ml-auto text-xs font-semibold tabular-nums">
                    {l.composite_score ?? "—"}
                  </span>
                </div>
                <div className="text-[11px] text-muted-foreground truncate">
                  {l.company ?? "—"} · {relativeTime(l.created_at)}
                </div>
              </Link>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}

function WidgetWeeklyTrend({ stats }: { stats: DashStats }) {
  return (
    <Card className="p-5 h-full">
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="text-xs uppercase tracking-widest text-muted-foreground flex items-center gap-1">
            <Calendar className="h-3 w-3" /> Activity over time
          </div>
          <div className="text-sm mt-0.5">New dossiers per week and rolling avg score</div>
        </div>
        <Link
          to="/leads"
          className="text-xs text-primary hover:underline inline-flex items-center gap-1"
        >
          View all <ArrowRight className="h-3 w-3" />
        </Link>
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
          <XAxis
            dataKey="name"
            tick={{ fill: "oklch(0.7 0.02 250)", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: "oklch(0.7 0.02 250)", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip contentStyle={tooltipStyle} />
          <Area
            type="monotone"
            dataKey="New"
            stroke="oklch(0.65 0.19 275)"
            strokeWidth={2}
            fill="url(#areaNew)"
            isAnimationActive
          />
          <Area
            type="monotone"
            dataKey="AvgScore"
            stroke="oklch(0.78 0.17 70)"
            strokeWidth={2}
            fill="url(#areaScore)"
            isAnimationActive
          />
        </AreaChart>
      </ResponsiveContainer>
    </Card>
  );
}

function WidgetPipeline({ stats }: { stats: DashStats }) {
  return (
    <Card className="p-5 h-full">
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs uppercase tracking-widest text-muted-foreground flex items-center gap-1">
          <Building2 className="h-3 w-3" /> Pipeline by company
        </div>
        <Link
          to="/leads"
          className="text-xs text-primary hover:underline inline-flex items-center gap-1"
        >
          View all <ArrowRight className="h-3 w-3" />
        </Link>
      </div>
      {stats.companyData.length === 0 ? (
        <Empty>No companies yet</Empty>
      ) : (
        <ul className="space-y-1.5">
          {stats.companyData.map((c, i) => {
            const max = Math.max(...stats.companyData.map((x) => x.count), 1);
            return <CompanyRow key={c.name} company={c} max={max} delay={i * 50} />;
          })}
        </ul>
      )}
    </Card>
  );
}

function WidgetDrivers({ stats }: { stats: DashStats }) {
  return (
    <Card className="p-5 h-full">
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs uppercase tracking-widest text-muted-foreground flex items-center gap-1">
          <Sparkles className="h-3 w-3" /> Top score drivers
        </div>
        <Link
          to="/leads"
          className="text-xs text-primary hover:underline inline-flex items-center gap-1"
        >
          View all <ArrowRight className="h-3 w-3" />
        </Link>
      </div>
      <SignalChips items={stats.attribution} />
    </Card>
  );
}

function WidgetCompliance({ stats }: { stats: DashStats }) {
  return (
    <Card className="p-5 h-full">
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs uppercase tracking-widest text-muted-foreground flex items-center gap-1">
          <Activity className="h-3 w-3" /> Compliance frameworks
        </div>
        <Link
          to="/leads"
          className="text-xs text-primary hover:underline inline-flex items-center gap-1"
        >
          View all <ArrowRight className="h-3 w-3" />
        </Link>
      </div>
      <SignalChips items={stats.compliance} />
    </Card>
  );
}

function WidgetHeadlines({ stats }: { stats: DashStats }) {
  if (stats.headlines.length === 0)
    return (
      <Card className="p-5 h-full">
        <div className="flex items-center justify-between mb-3">
          <div className="text-xs uppercase tracking-widest text-muted-foreground flex items-center gap-1">
            <MessageSquareQuote className="h-3 w-3" /> AI verdict headlines
          </div>
          <Link
            to="/leads"
            className="text-xs text-primary hover:underline inline-flex items-center gap-1"
          >
            View all <ArrowRight className="h-3 w-3" />
          </Link>
        </div>
        <Empty>No verdicts yet</Empty>
      </Card>
    );
  return (
    <Card className="p-5 h-full">
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs uppercase tracking-widest text-muted-foreground flex items-center gap-1">
          <MessageSquareQuote className="h-3 w-3" /> AI verdict headlines
        </div>
        <Link
          to="/leads"
          className="text-xs text-primary hover:underline inline-flex items-center gap-1"
        >
          View all <ArrowRight className="h-3 w-3" />
        </Link>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
        {stats.headlines.map((h) => (
          <Link
            key={h.id}
            to="/leads/$leadId"
            params={{ leadId: h.id }}
            className="rounded-lg border bg-accent/20 px-3 py-2 text-xs leading-relaxed line-clamp-3 hover:border-primary/40 hover:bg-primary/5 transition group"
          >
            <span className="group-hover:text-primary">{h.text}</span>
          </Link>
        ))}
      </div>
    </Card>
  );
}

function WidgetFreshness({
  stats,
  freshLeadIds,
  agingLeadIds,
  staleLeadIds,
}: {
  stats: DashStats;
  freshLeadIds: string[];
  agingLeadIds: string[];
  staleLeadIds: string[];
}) {
  const { fresh, aging, stale } = stats.freshness;
  const total = fresh + aging + stale || 1;
  const mounted = useMounted(140);
  const firstFresh = freshLeadIds[0];
  const firstAging = agingLeadIds[0];
  const firstStale = staleLeadIds[0];
  return (
    <Card className="p-5 h-full">
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs uppercase tracking-widest text-muted-foreground flex items-center gap-1">
          <Hourglass className="h-3 w-3" /> Lead freshness
        </div>
        <Link
          to="/leads"
          className="text-xs text-primary hover:underline inline-flex items-center gap-1"
        >
          View all <ArrowRight className="h-3 w-3" />
        </Link>
      </div>
      <div className="flex items-center gap-2 mb-3">
        <div className="h-3 flex-1 rounded-full overflow-hidden bg-muted flex">
          <div
            className="h-full bg-[oklch(0.7_0.18_145)] bar-fill"
            style={{ width: `${mounted ? (fresh / total) * 100 : 0}%` }}
          />
          <div
            className="h-full bg-[oklch(0.78_0.17_70)] bar-fill"
            style={{ width: `${mounted ? (aging / total) * 100 : 0}%` }}
          />
          <div
            className="h-full bg-[oklch(0.7_0.22_25)] bar-fill"
            style={{ width: `${mounted ? (stale / total) * 100 : 0}%` }}
          />
        </div>
      </div>
      <div className="flex justify-between text-[11px] text-muted-foreground">
        {firstFresh ? (
          <Link
            to="/leads/$leadId"
            params={{ leadId: firstFresh }}
            className="hover:text-primary transition"
          >
            🟢 Fresh ≤7d: {fresh}
          </Link>
        ) : (
          <span>🟢 Fresh ≤7d: {fresh}</span>
        )}
        {firstAging ? (
          <Link
            to="/leads/$leadId"
            params={{ leadId: firstAging }}
            className="hover:text-primary transition"
          >
            🟡 Aging 7–30d: {aging}
          </Link>
        ) : (
          <span>🟡 Aging 7–30d: {aging}</span>
        )}
        {firstStale ? (
          <Link
            to="/leads/$leadId"
            params={{ leadId: firstStale }}
            className="hover:text-primary transition"
          >
            🔴 Stale &gt;30d: {stale}
          </Link>
        ) : (
          <span>🔴 Stale &gt;30d: {stale}</span>
        )}
      </div>
    </Card>
  );
}

function WidgetDimConf({ stats }: { stats: DashStats }) {
  return (
    <Card className="p-5 h-full">
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs uppercase tracking-widest text-muted-foreground flex items-center gap-1">
          <Crosshair className="h-3 w-3" /> Dimension confidence
        </div>
        <Link
          to="/leads"
          className="text-xs text-primary hover:underline inline-flex items-center gap-1"
        >
          View all <ArrowRight className="h-3 w-3" />
        </Link>
      </div>
      <div className="space-y-2">
        {stats.dimConf.map((d) => {
          const t = d.high + d.medium + d.low + d.unknown || 1;
          const topBucket =
            d.high >= d.medium && d.high >= d.low
              ? "high"
              : d.medium >= d.low
                ? "medium"
                : "low";
          return (
            <Link
              key={d.dim}
              to="/leads"
              search={{ confidence: topBucket as "high" | "medium" | "low" }}
              className="block rounded-md px-1 py-0.5 hover:bg-accent/40 transition group"
            >
              <div className="flex items-center justify-between text-xs mb-0.5">
                <span className="font-medium group-hover:text-primary">{d.dim}</span>
                <span className="text-muted-foreground">
                  {d.high}H {d.medium}M {d.low}L
                </span>
              </div>
              <ConfidenceBar conf={d} total={t} />
            </Link>
          );
        })}
      </div>
      <div className="flex gap-3 mt-3 text-[10px] text-muted-foreground">
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-[oklch(0.7_0.18_145)]" />
          High
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-[oklch(0.78_0.17_70)]" />
          Med
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-[oklch(0.7_0.22_25)]" />
          Low
        </span>
      </div>
    </Card>
  );
}

function WidgetIcpTier({ stats }: { stats: DashStats }) {
  return (
    <Card className="p-5 h-full">
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs uppercase tracking-widest text-muted-foreground flex items-center gap-1">
          <Target className="h-3 w-3" /> ICP × Tier matrix
        </div>
        <Link
          to="/leads"
          className="text-xs text-primary hover:underline inline-flex items-center gap-1"
        >
          View all <ArrowRight className="h-3 w-3" />
        </Link>
      </div>
      {/* th scope="col"/"row" on every header cell + min-h/w 24px on every
         clickable cell so it passes Lighthouse target-size and td-has-header.
         Previously row labels used <td> and inner counts had 16px height. */}
      <table className="w-full text-xs">
        <thead>
          <tr>
            <th scope="col" className="text-left font-medium pb-1">
              <span className="sr-only">Tier</span>
            </th>
            {[1, 2, 3, 4, 5].map((s) => (
              <th key={s} scope="col" className="text-center font-medium pb-1">
                {"★".repeat(s)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {stats.icpTier.map((row) => (
            <tr key={row.tier}>
              <th scope="row" className="pr-2 py-1 font-semibold text-left">
                <Link
                  to="/leads"
                  search={{ tier: row.tier as "HOT" | "WARM" | "COLD" }}
                  className="inline-flex items-center min-h-6 px-1 rounded hover:text-primary hover:bg-accent/40 transition"
                >
                  {row.tier}
                </Link>
              </th>
              {row.stars.map((v, i) => (
                <td key={i} className="text-center py-1">
                  {v > 0 ? (
                    <Link
                      to="/leads"
                      search={{
                        tier: row.tier as "HOT" | "WARM" | "COLD",
                        icp_min: (i + 1) as 1 | 2 | 3 | 4 | 5,
                      }}
                      className="grid place-items-center min-h-6 min-w-6 mx-auto rounded bg-primary/15 font-semibold hover:bg-primary/25 transition"
                    >
                      {v}
                    </Link>
                  ) : (
                    <span className="inline-grid place-items-center min-h-6 min-w-6 text-muted-foreground/40">
                      0
                    </span>
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

function WidgetRoles({ stats }: { stats: DashStats }) {
  const max = Math.max(...stats.roleBreakdown.map((r) => r.count), 1);
  const mounted = useMounted(160);
  if (stats.roleBreakdown.length === 0)
    return (
      <Card className="p-5 h-full">
        <div className="flex items-center justify-between mb-3">
          <div className="text-xs uppercase tracking-widest text-muted-foreground flex items-center gap-1">
            <Users className="h-3 w-3" /> Role distribution
          </div>
          <Link
            to="/leads"
            className="text-xs text-primary hover:underline inline-flex items-center gap-1"
          >
            View all <ArrowRight className="h-3 w-3" />
          </Link>
        </div>
        <Empty>No title data</Empty>
      </Card>
    );
  return (
    <Card className="p-5 h-full">
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs uppercase tracking-widest text-muted-foreground flex items-center gap-1">
          <Users className="h-3 w-3" /> Role distribution
        </div>
        <Link
          to="/leads"
          className="text-xs text-primary hover:underline inline-flex items-center gap-1"
        >
          View all <ArrowRight className="h-3 w-3" />
        </Link>
      </div>
      <div className="space-y-1.5">
        {stats.roleBreakdown.map((r) => (
          <Link
            key={r.role}
            to="/leads"
            search={{ q: r.role }}
            className="flex items-center gap-2 group rounded-md px-1 py-0.5 hover:bg-accent/40 transition"
          >
            <span className="w-24 truncate text-xs font-medium group-hover:text-primary">
              {r.role}
            </span>
            <div className="flex-1 h-2 rounded bg-muted overflow-hidden">
              <div
                className="h-full bar-fill bg-primary/70"
                style={{ width: `${mounted ? (r.count / max) * 100 : 0}%` }}
              />
            </div>
            <span className="w-6 text-right text-xs tabular-nums">{r.count}</span>
          </Link>
        ))}
      </div>
    </Card>
  );
}

function WidgetThreats({ stats }: { stats: DashStats }) {
  return (
    <Card className="p-5 h-full">
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs uppercase tracking-widest text-muted-foreground flex items-center gap-1">
          <Layers className="h-3 w-3" /> Competitive threats
        </div>
        <Link
          to="/leads"
          className="text-xs text-primary hover:underline inline-flex items-center gap-1"
        >
          View all <ArrowRight className="h-3 w-3" />
        </Link>
      </div>
      <SignalChips items={stats.competitors} />
    </Card>
  );
}

const tooltipStyle = {
  background: "oklch(0.21 0.025 260)",
  border: "1px solid oklch(0.3 0.025 260)",
  borderRadius: 8,
  fontSize: 12,
  color: "oklch(0.92 0.01 250)",
};

function confDotClass(b: "high" | "medium" | "low" | "unknown") {
  return b === "high"
    ? "bg-[oklch(0.7_0.18_145)]"
    : b === "medium"
      ? "bg-[oklch(0.78_0.17_70)]"
      : b === "low"
        ? "bg-[oklch(0.7_0.22_25)]"
        : "bg-muted-foreground";
}

function ConfidenceBar({
  conf,
  total,
  clickable = false,
}: {
  conf: { high: number; medium: number; low: number; unknown: number };
  total: number;
  // When true, each segment is its own Link. When false (default), segments
  // are inert divs — used inside DIMENSION CONFIDENCE rows, which are
  // themselves already wrapped in an outer Link (nested anchors = invalid HTML).
  clickable?: boolean;
}) {
  const mounted = useMounted(120);
  const pct = (n: number) => (total ? (n / total) * 100 : 0);
  const segs: { key: keyof typeof conf; cls: string; w: number }[] = [
    { key: "high", cls: "bg-[oklch(0.7_0.18_145)]", w: pct(conf.high) },
    { key: "medium", cls: "bg-[oklch(0.78_0.17_70)]", w: pct(conf.medium) },
    { key: "low", cls: "bg-[oklch(0.7_0.22_25)]", w: pct(conf.low) },
    { key: "unknown", cls: "bg-muted-foreground/40", w: pct(conf.unknown) },
  ];
  return (
    <div className="h-3 w-full rounded-full overflow-hidden bg-muted flex">
      {segs.map((s) =>
        clickable && s.w > 0 ? (
          <Link
            key={s.key}
            to="/leads"
            search={{ confidence: s.key }}
            className={`${s.cls} bar-fill h-full block hover:opacity-80 transition-opacity`}
            style={{ width: `${mounted ? s.w : 0}%` }}
            title={`${s.key}: ${Math.round(s.w)}% — click to filter`}
            aria-label={`Filter to ${s.key} confidence (${Math.round(s.w)}%)`}
          />
        ) : (
          <div
            key={s.key}
            className={`${s.cls} bar-fill h-full`}
            style={{ width: `${mounted ? s.w : 0}%` }}
            title={`${s.key}: ${Math.round(s.w)}%`}
          />
        ),
      )}
    </div>
  );
}

function IcpRow({ star, value, max }: { star: number; value: number; max: number }) {
  const mounted = useMounted(160 + (5 - star) * 60);
  const pct = max ? (value / max) * 100 : 0;
  return (
    <Link
      to="/leads"
      search={{ icp_min: star as 1 | 2 | 3 | 4 | 5 }}
      className="group block rounded-md px-1.5 py-1 hover:bg-accent/40 transition"
    >
      <div className="flex items-center gap-2">
        <div className="flex w-16 shrink-0 text-[oklch(0.78_0.17_70)]">
          {Array.from({ length: 5 }).map((_, i) => (
            <Star
              key={i}
              className={`h-3 w-3 ${i < star ? "fill-current" : "opacity-25"}`}
              strokeWidth={1.5}
            />
          ))}
        </div>
        <div className="flex-1 h-1.5 rounded bg-muted overflow-hidden">
          <div
            className="h-full bar-fill bg-gradient-to-r from-[oklch(0.65_0.19_275)] to-[oklch(0.78_0.17_70)]"
            style={{ width: `${mounted ? pct : 0}%` }}
          />
        </div>
        <div className="w-8 text-right text-xs font-semibold tabular-nums group-hover:text-primary">
          {value}
        </div>
      </div>
    </Link>
  );
}

function BucketBar({
  bucket,
  maxValue,
  delay,
}: {
  bucket: { name: string; min: number; max: number; value: number };
  maxValue: number;
  delay: number;
}) {
  const mounted = useMounted(180 + delay);
  const h = Math.max(4, Math.round((bucket.value / maxValue) * 100));
  const hue =
    bucket.min >= 80
      ? 25
      : bucket.min >= 60
        ? 70
        : bucket.min >= 40
          ? 145
          : bucket.min >= 20
            ? 200
            : 250;
  return (
    <Link
      to="/leads"
      search={{ min: bucket.min, max: bucket.max }}
      className="group flex flex-col items-stretch h-full justify-end"
    >
      <div className="text-center text-sm font-semibold mb-1">{bucket.value}</div>
      <div
        className="rounded-md border border-transparent group-hover:border-primary/40"
        style={{
          height: `${mounted ? h : 0}%`,
          background: `linear-gradient(to top, oklch(0.55 0.18 ${hue}), oklch(0.72 0.16 ${hue}))`,
          transition: "height 700ms cubic-bezier(0.16, 1, 0.3, 1)",
        }}
      />
      <div className="text-[10px] text-center mt-1 text-muted-foreground group-hover:text-primary">
        {bucket.name}
      </div>
    </Link>
  );
}

function CompanyRow({
  company,
  max,
  delay,
}: {
  company: { name: string; count: number; avgScore: number };
  max: number;
  delay: number;
}) {
  const mounted = useMounted(200 + delay);
  const w = (company.count / max) * 100;
  return (
    <li>
      <Link
        to="/leads"
        search={{ company: company.name }}
        className="block rounded-md px-2 py-1.5 hover:bg-accent/40 group"
      >
        <div className="flex items-center justify-between text-sm">
          <span className="truncate font-medium group-hover:text-primary">{company.name}</span>
          <div className="flex items-center gap-3 text-xs text-muted-foreground shrink-0">
            <span>
              {company.count} lead{company.count > 1 ? "s" : ""}
            </span>
            <span className="font-semibold text-foreground w-8 text-right">{company.avgScore}</span>
            <ChevronRight className="h-3 w-3 group-hover:text-primary" />
          </div>
        </div>
        <div className="h-1 rounded bg-muted mt-1 overflow-hidden">
          <div className="h-full bar-fill bg-primary/70" style={{ width: `${mounted ? w : 0}%` }} />
        </div>
      </Link>
    </li>
  );
}

function KpiTile({
  to,
  search,
  label,
  value,
  suffix,
  accent,
  icon,
}: {
  to: "/leads";
  search: Record<string, string | number | undefined>;
  label: string;
  value: number;
  suffix?: string;
  accent?: "hot" | "warm" | "cold";
  icon?: React.ReactNode;
}) {
  const ring =
    accent === "hot"
      ? "from-[oklch(0.65_0.22_25)]/20"
      : accent === "warm"
        ? "from-[oklch(0.75_0.17_70)]/20"
        : accent === "cold"
          ? "from-[oklch(0.65_0.13_230)]/20"
          : "from-primary/15";
  const text =
    accent === "hot"
      ? "text-[oklch(0.7_0.22_25)]"
      : accent === "warm"
        ? "text-[oklch(0.78_0.17_70)]"
        : accent === "cold"
          ? "text-[oklch(0.7_0.13_230)]"
          : "text-foreground";
  return (
    <Link
      to={to}
      search={search}
      className="group block cursor-pointer rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background"
    >
      <Card
        className={`p-4 relative overflow-hidden bg-gradient-to-br ${ring} to-card hover:border-primary/40 transition`}
      >
        <div className="text-[10px] uppercase tracking-widest text-muted-foreground flex items-center gap-1">
          {icon} {label}
        </div>
        <div className="flex items-end justify-between mt-1">
          <div className={`text-3xl font-bold tabular-nums ${text}`}>
            <AnimatedNumber value={value} />
          </div>
          {suffix && <div className="text-xs text-muted-foreground mb-1">{suffix}</div>}
        </div>
        <ArrowUpRight className="absolute top-3 right-3 h-3.5 w-3.5 text-muted-foreground group-hover:text-primary" />
      </Card>
    </Link>
  );
}

function SignalChips({
  items,
}: {
  items: { name: string; count: number; avgPts: number; type: string }[];
}) {
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
          {i.avgPts > 0 && (
            <span className="text-[10px] text-primary/80 font-semibold">+{i.avgPts}</span>
          )}
        </Link>
      ))}
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-1.5 py-6 px-4 text-center">
      <Sparkles className="h-4 w-4 text-muted-foreground/30" aria-hidden />
      <div className="text-xs text-muted-foreground/70">{children}</div>
      <div className="text-[10px] text-muted-foreground/40">
        Populates after a few dossiers are uploaded
      </div>
    </div>
  );
}
