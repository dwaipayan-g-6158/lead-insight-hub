import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { useServerFn } from "@/lib/use-server-fn";
import { getLead, deleteLead, fetchLeadPdf } from "@/lib/api";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { DimensionBar } from "@/components/DimensionBar";
import { ArrowLeft, Download, FileWarning, Trash2 } from "lucide-react";
import { Spinner } from "@/components/Spinner";
import { tierClasses } from "@/lib/tier";
import { EngineBadge } from "@/components/EngineBadge";
import type { LeadRow, Signal } from "@/types/leads";

export function LeadDetailPage({ id }: { id: string }) {
  const { isAdmin, user } = useAuth();
  const navigate = useNavigate();
  const get = useServerFn(getLead);
  const del = useServerFn(deleteLead);
  const [data, setData] = useState<{
    lead: LeadRow;
    signals: Signal[];
    html: string | null;
    htmlUrl?: string | null;
    storage_status?: "available" | "missing" | null;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  // PDF download in flight — disables the button + shows a spinner while
  // SmartBrowz renders (first download of a dossier can take a few seconds).
  const [downloading, setDownloading] = useState(false);
  // Ref to the dossier iframe so the parent-side message listener can
  // verify that incoming open-link messages came from THIS iframe
  // (defeats spoofed messages from other tabs / extensions).
  const iframeRef = useRef<HTMLIFrameElement>(null);

  // Signed-in user's full name, used to replace template placeholders
  // like `<rep name>` in dossier email bodies. Falls back to a neutral
  // phrase so the literal token never reaches the screen.
  const repName = useMemo(() => {
    const u = user as { first_name?: string; last_name?: string; email_id?: string } | null;
    const full = [u?.first_name, u?.last_name].filter(Boolean).join(" ").trim();
    return full || u?.email_id || "your account team";
  }, [user]);

  useEffect(() => {
    setLoading(true);
    get({ data: { id } })
      .then((r) =>
        setData(
          r as {
            lead: LeadRow;
            signals: Signal[];
            html: string | null;
            htmlUrl?: string | null;
            storage_status?: "available" | "missing" | null;
          },
        ),
      )
      .catch((e: Error) => setErr(e.message))
      .finally(() => setLoading(false));
  }, [get, id]);

  // Bridge external-link clicks inside the opaque-origin dossier iframe
  // to the parent's window.open(). The iframe (sandbox without
  // allow-same-origin) cannot open new tabs reliably on iOS Safari — the
  // browser blocks the navigation with a Cross-Origin-Opener-Policy
  // error. The injected iframe script intercepts http(s) <a> clicks,
  // preventDefault()s them, and postMessages the URL up here, where
  // window.open() runs in the parent's same-origin context with
  // 'noopener,noreferrer' — same security posture as the old
  // target="_blank" rel="noopener" rewrite, but COOP-clean.
  useEffect(() => {
    function onMessage(ev: MessageEvent) {
      if (!iframeRef.current || ev.source !== iframeRef.current.contentWindow) return;
      const data = ev.data as { source?: unknown; type?: unknown; url?: unknown } | null;
      if (!data || data.source !== "eliss-dossier" || data.type !== "open-link") return;
      const url = typeof data.url === "string" ? data.url : "";
      if (!/^https?:\/\//i.test(url)) return;
      const win = window.open(url, "_blank", "noopener,noreferrer");
      if (!win) {
        console.warn("dossier link open blocked by popup blocker:", url);
      }
    }
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, []);

  const onDelete = async () => {
    if (!confirm("Delete this dossier? This cannot be undone.")) return;
    try {
      await del({ data: { id } });
    } catch (e) {
      setErr((e as Error)?.message ?? "Delete failed");
      return;
    }
    // Use the router so the navigation respects hash-history routing.
    // window.location.href = "/leads" would 404 — Catalyst has no SPA fallback
    // outside /app/, so absolute paths return INVALID_URL_PATTERN.
    void navigate({ to: "/leads" });
  };

  // Download the dossier as a professionally formatted PDF. The server renders
  // the stored report HTML to PDF via SmartBrowz (cached after the first call)
  // and streams it back; we save the returned Blob. Filename uses lead-name + ID
  // for disambiguating duplicate-email leads.
  const onDownload = async () => {
    if (!data || downloading) return;
    setDownloading(true);
    try {
      const baseName = `${(data.lead.lead_name || "dossier").replace(/[^a-zA-Z0-9._-]/g, "_")}-${id}.pdf`;
      const blob = await fetchLeadPdf(id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = baseName;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch (e) {
      toast.error((e as Error)?.message || "Couldn't generate the PDF — please try again");
    } finally {
      setDownloading(false);
    }
  };

  if (loading) return <div className="grid place-items-center py-24"><Spinner className="h-5 w-5 text-muted-foreground" /></div>;
  if (err || !data) return <Card className="p-6 text-sm text-destructive">{err || "Not found"}</Card>;

  const { lead, signals, html, htmlUrl, storage_status } = data;
  // Always prefer srcdoc when inline html is available: Stratus signed URLs
  // ship `X-Frame-Options: SAMEORIGIN` which blocks cross-origin iframe
  // embedding, so the signed URL is only safe for the Download button.
  const useSrcDoc = typeof html === "string" && html.length > 0;
  // storage_status === "missing" means the lead row points at a Stratus object
  // that no longer exists (or is unreachable). Without this flag we'd render
  // a blank iframe with no explanation; instead we swap in an empty-state card
  // so the user knows the original HTML is gone and can act on it (admins
  // can re-upload from /upload).
  const storageMissing = storage_status === "missing";
  const canDownload = !storageMissing && (Boolean(htmlUrl) || (typeof html === "string" && html.length > 0));

  const groupedSignals = signals.reduce<Record<string, Signal[]>>((acc, s) => {
    (acc[s.signal_type] ||= []).push(s); return acc;
  }, {});

  // Strip midnight time component from "2026-05-07 00:00:00" so the chrome
  // shows a clean date. Leaves dates with a real time-of-day untouched.
  const formatReportDate = (s: string | null | undefined): string => {
    if (!s) return "";
    return String(s).replace(/[ T]00:00:00(?:[.:]\d+)?$/, "");
  };

  // Script injected into the dossier iframe (srcdoc path only).
  // Intercepts http(s) link clicks and hands the URL up to the parent
  // via postMessage. The parent opens the new tab in its own (proper)
  // origin context, avoiding the iOS Safari COOP block that triggers
  // when an opaque-origin sandboxed iframe tries to open a new tab.
  // postMessage works across the opaque-origin boundary by design and
  // does NOT require allow-same-origin.
  const iframeTargetBlankScript = `<script>
    (function(){
      document.addEventListener('click', function(e){
        var a = e.target && e.target.closest && e.target.closest('a[href]');
        if (!a) return;
        var h = a.getAttribute('href') || '';
        if (h.charAt(0) === '#' || h.indexOf('mailto:') === 0 || h.indexOf('tel:') === 0) return;
        if (h.indexOf('http://') !== 0 && h.indexOf('https://') !== 0) return;
        e.preventDefault();
        try {
          window.parent.postMessage(
            { source: 'eliss-dossier', type: 'open-link', url: h },
            '*'
          );
        } catch(_) {}
      }, true);
    })();
  </script>`;

  // Mobile-responsive overrides injected into the dossier srcdoc.
  //
  // The dossier renders rich 5-column tables (Deal Execution Risks,
  // Competitive Threat Matrix, Score Summary, etc.) as real <table>
  // elements wrapped in `.md-table-wrap`. The previous baseline used
  // `table-layout: fixed`, which crammed all 5 columns to ~75px each on
  // a 375px iPhone viewport — every cell wrapped into a tall ribbon,
  // and adjacent rows visually fused. Fix: switch to `table-layout:
  // auto` so columns size to content, force a min-width on tables wider
  // than the viewport, and let the `.md-table-wrap` scroll horizontally
  // inside its own box (instead of dragging the whole body sideways).
  //
  // The body-level `overflow-x: hidden` keeps stray inline-styled
  // children from leaking and forcing the page itself to scroll.
  const iframeMobileCss = `<style>
    img, video { max-width: 100%; height: auto; }
    pre, code { white-space: pre-wrap; word-break: break-word; }
    a, p, li { overflow-wrap: anywhere; }
    /* Table cells use break-word, NOT anywhere — "anywhere" causes
       narrow cells to break headers character-by-character ("DIM EN
       SIO N" instead of "DIMENSION"). break-word only splits if a
       whole word can't fit. */
    td, th { overflow-wrap: break-word; word-break: normal; }
    body { -webkit-text-size-adjust: 100%; }
    /* Keep the page itself from scrolling sideways — wide content gets
       its own horizontal scroll inside .md-table-wrap below.
       'overflow: clip' (modern browsers) prevents horizontal overflow
       like 'hidden' but does NOT create a scroll container, so the
       dossier's position:sticky elements (the .tab-nav toggle and the
       sticky th column headers) continue sticking to their natural
       scroll ancestor. 'overflow: hidden' would break sticky on every
       descendant. The plain 'hidden' rule below is the fallback for
       browsers that do not support 'clip' (pre-Chrome-90, pre-Safari-
       15.4): they keep horizontal-scroll prevention at the cost of
       sticky, which is strictly no worse than today. */
    html, body { overflow-x: hidden; max-width: 100%; }
    @supports (overflow: clip) {
      html, body { overflow-x: clip; }
    }
    @media (max-width: 640px) {
      body { padding: 12px !important; font-size: 14px; }
      /* Wrap every dossier table in its own horizontal scroller so wide
         5-column matrices remain readable instead of compressing into
         unreadable ribbons. .md-table-wrap is the generator-emitted
         shell around every Markdown-rendered table, including:
            - Deal Execution Risks (.der-wrap > .der-table)
            - Competitive Threat Matrix (.comp-matrix-wrap > .comp-matrix)
            - Score Summary (.md-table-wrap > .md-table) */
      /* !important on these rules so they win over the dossier's own
         CSS rules baked into the verbatim copy of the report. The
         "Complete Intelligence Dossier" tab renders .dossier-verbatim,
         which contains the original generator's <style> block. Without
         !important, the generators .md-table rule with min-width:480px
         and max-width:100% clamps the table to 480px AND caps it at
         the wrap's 255px width — producing the "DIM EN SIO N" crush. */
      .md-table-wrap {
        overflow-x: auto !important;
        -webkit-overflow-scrolling: touch;
        max-width: 100% !important;
        margin-left: 0 !important;
        margin-right: 0 !important;
        padding: 0 !important;
      }
      /* Legacy dossiers (rendered before the stacked-card generator CSS)
         carry no per-cell data-label, so keep the horizontal-scroll fix for
         them. New dossiers emit td[data-label] and use the generator's baked
         stacked-card layout at <=600px — scope these overrides away from
         those so we don't force them back into a 560px scroller. */
      table.md-table:not(:has(td[data-label])) {
        table-layout: auto !important;
        font-size: 12px;
        min-width: 560px !important;
        /* Drop width:max-content and let table-layout:auto pick a
           natural width that satisfies the cell max-widths below. Some
           dossier rows have very long prose cells (evidence, basis,
           key driver) that with max-content would blow the table out
           to 4500px+; we cap each cell at ~38vw (~142 px on iPhone)
           so prose wraps vertically and the total table stays under
           ~5 * 38vw + padding for typical 5-col layouts. */
        max-width: none !important;
        width: auto !important;
      }
      table.md-table:not(:has(td[data-label])) th,
      table.md-table:not(:has(td[data-label])) td {
        padding: 6px 8px !important;
        vertical-align: top;
        line-height: 1.4;
        /* anywhere is needed for long URL chips inside cells; break-word
           alone wouldn't split a 60-char URL so the column would blow out.
           At ~142px column width the headers "DIMENSION", "CONFIDENCE"
           etc still fit on one line, so we won't see "DIM EN SIO N" any
           more — that crush was driven by the 480px min-width clamp,
           not by overflow-wrap:anywhere. */
        overflow-wrap: anywhere !important;
        word-break: normal !important;
        max-width: 38vw !important;
      }
      /* Generic fallback for any other <table> the generator emits
         without the md-table-wrap shell. */
      table:not(.md-table) {
        display: block !important;
        overflow-x: auto !important;
        max-width: 100% !important;
        font-size: 12px;
      }
      /* Defeat the dossier generator's per-table inline width attributes
         like <table width="600"> that would otherwise lock columns
         narrower than the viewport. */
      table[width] { width: auto !important; }
      /* Div-based "pseudo-table" rows (dim-row, attr-leg-row, heatmap-row,
         readiness-row, ras-cell, etc.) — let them wrap instead of clipping. */
      .dim-row,
      .attr-leg-row,
      .heatmap-row,
      .readiness-row,
      .risk-adjusted-strip,
      .donut-row,
      .rr-dept-row,
      .rr-trend-row,
      .dt-row,
      .dt-row-body,
      .field-grid,
      .sc-grid,
      .sc-tier-row,
      .talking-grid,
      .dq-grid,
      .wf-grid {
        flex-wrap: wrap !important;
        gap: 6px 8px !important;
        column-gap: 8px !important;
      }
      /* Multi-column grids — collapse to a single column at this width. */
      .field-grid,
      .sc-grid,
      .talking-grid,
      .dq-grid,
      .wf-grid,
      .profile-grid,
      .source-quality-wrap,
      .ghost-card-header {
        grid-template-columns: minmax(0, 1fr) !important;
      }
      /* Long evidence-chip links keep wrapping cleanly instead of
         dragging the cell width past 100%. */
      .evidence-chips { flex-wrap: wrap; gap: 4px; }
      .evidence-chip { word-break: break-all; }
      /* Tab navigation — let chips wrap so they don't overflow. */
      .tab-nav { flex-wrap: wrap; gap: 4px; }
      /* Key:Value bullet rows inside .dossier-verbatim use a hardcoded
         grid-template-columns: <label-width>px <value-width>px from
         the generator's CSS. On a narrow viewport the value column
         frequently collapses to a single-digit pixel width and the
         long prose then breaks character-by-character. Stack the two
         cells vertically on mobile so each gets the full width. */
      .md-li-kv {
        grid-template-columns: minmax(0, 1fr) !important;
        gap: 2px 0 !important;
      }
      .md-li-kv-key,
      .md-li-kv-val {
        max-width: 100% !important;
        min-width: 0 !important;
      }
      .md-li-kv-key { font-weight: 600; }
    }
  </style>`;

  // Replace template placeholders the dossier generator leaves
  // unsubstituted ("<rep name>", "<sender name>", "<your name>") with
  // the signed-in user's display name. Trailing-space-tolerant regex
  // catches both "<rep name>" and "<rep name >". Also collapses doubled
  // smart quotes that occasionally slip through the dossier generator's
  // HTML-escape pipeline (e.g. `""quote""` → `"quote"`). Runs
  // client-side so legacy stored dossiers are cleaned at render time.
  const substituteTokens = (raw: string): string =>
    raw
      .replace(/&lt;rep\s*name\s*&gt;/gi, repName)
      .replace(/<rep\s*name\s*>/gi, repName)
      .replace(/&lt;sender\s*name\s*&gt;/gi, repName)
      .replace(/<sender\s*name\s*>/gi, repName)
      .replace(/&lt;your\s*name\s*&gt;/gi, repName)
      .replace(/<your\s*name\s*>/gi, repName)
      // Collapse pairs of identical smart-quote characters that result
      // from double-escaping. Use only when adjacent; intentional
      // emphasis like "" (with content between) is untouched.
      .replace(/""(?=\S)/g, '"')
      .replace(/(?<=\S)""/g, '"')
      .replace(/““(?=\S)/g, "“")
      .replace(/(?<=\S)””/g, "”");

  return (
    <div className="lg:flex lg:flex-col lg:gap-2 lg:h-full lg:min-h-0">
      {/* Desktop-only action row sits above the grid. The mobile action row
         lives inside the first snap section so it scrolls away with the
         summary view. */}
      {/* Visually-hidden h1 anchors the page's accessible outline at the
         lead's name. The visible "Lead" panel below renders the same
         info with display typography; this h1 exists for screen readers
         and document-outline tools, not pixels. */}
      <h1 className="sr-only">
        {lead.lead_name}
        {lead.company ? ` — ${lead.company}` : ""}
      </h1>
      <div className="hidden lg:flex items-center justify-between gap-3 flex-wrap shrink-0">
        <Link to="/leads" className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4 mr-1" /> Back to leads
        </Link>
        <div className="flex items-center gap-2">
          <Button
                variant="ghost"
                size="sm"
                onClick={onDownload}
                disabled={!canDownload || downloading}
                title={canDownload ? undefined : "Original dossier is no longer available"}
                aria-label="Download dossier as PDF"
              >
            {downloading ? (
              <Spinner className="h-4 w-4 mr-2" />
            ) : (
              <Download className="h-4 w-4 mr-2" />
            )}
            {downloading ? "Preparing PDF…" : "Download PDF"}
          </Button>
          {isAdmin && (
            <Button variant="ghost" size="sm" onClick={onDelete} aria-label={`Delete lead ${lead.lead_name}`}>
              <Trash2 className="h-4 w-4 mr-2" /> Delete
            </Button>
          )}
        </div>
      </div>

      {/*
        Mobile = vertical scroll-snap container with TWO snap sections.
          Section 1 (aside): lead summary fills the viewport.
          Section 2 (Card):  dossier fills the viewport, scrolls internally.
        Desktop (lg+) = the lg: overrides collapse everything to the original
        side-by-side grid layout (320px sidebar + iframe filling the rest).
      */}
      <div
        className="
          h-[calc(100dvh-3.5rem)] overflow-y-auto snap-y snap-mandatory
          lg:h-auto lg:overflow-visible lg:snap-none
          lg:grid lg:grid-cols-[320px_1fr] lg:gap-4 lg:flex-1 lg:min-h-0
        "
      >
        <aside className="snap-start min-h-[calc(100dvh-3.5rem)] space-y-4 p-1 lg:snap-none lg:min-h-0 lg:p-0 lg:overflow-y-auto lg:pr-1">
          {/* Mobile-only action row — part of the summary snap section */}
          <div className="lg:hidden flex items-center justify-between gap-3 flex-wrap">
            <Link to="/leads" className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground">
              <ArrowLeft className="h-4 w-4 mr-1" /> Back to leads
            </Link>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={onDownload}
                disabled={!canDownload || downloading}
                title={canDownload ? undefined : "Original dossier is no longer available"}
                aria-label="Download dossier as PDF"
              >
                {downloading ? (
                  <Spinner className="h-4 w-4 mr-2" />
                ) : (
                  <Download className="h-4 w-4 mr-2" />
                )}
                {downloading ? "Preparing PDF…" : "Download PDF"}
              </Button>
              {isAdmin && (
                <Button variant="ghost" size="sm" onClick={onDelete} aria-label={`Delete lead ${lead.lead_name}`}>
                  <Trash2 className="h-4 w-4 mr-2" /> Delete
                </Button>
              )}
            </div>
          </div>
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
              {isAdmin && <EngineBadge engine={lead.generation_engine} />}
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

          {lead.demo_playbook?.has_playbook && (
            <Card className="p-5 space-y-3 border-indigo-500/30 bg-gradient-to-br from-indigo-500/5 to-sky-500/5">
              <div className="flex items-center justify-between gap-2">
                <div className="text-xs uppercase tracking-widest text-muted-foreground">Demo Playbook</div>
                <span className="text-[9px] px-1.5 py-0.5 rounded-full font-medium bg-gradient-to-r from-indigo-500/15 to-sky-500/15 border border-indigo-500/30 text-indigo-700 dark:text-indigo-300">
                  v7.6
                </span>
              </div>
              {lead.demo_playbook.persona && (
                <div>
                  <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-0.5">For</div>
                  <div className="text-sm font-medium">{lead.demo_playbook.persona}</div>
                </div>
              )}
              {lead.demo_playbook.opening_hook && (
                <div>
                  <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-0.5">Opening hook</div>
                  <p className="text-sm text-muted-foreground italic">"{lead.demo_playbook.opening_hook}"</p>
                </div>
              )}
              <div className="flex flex-wrap gap-1 pt-1">
                {lead.demo_playbook.has_ad360 && (
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/15 text-indigo-700 dark:text-indigo-300 border border-indigo-500/30">
                    AD360 demo
                  </span>
                )}
                {lead.demo_playbook.has_log360 && (
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-sky-500/15 text-sky-700 dark:text-sky-300 border border-sky-500/30">
                    Log360 demo
                  </span>
                )}
              </div>
              <p className="text-[10px] text-muted-foreground pt-1">
                Full playbook is rendered inside the dossier — scroll to the Demo Playbook section.
              </p>
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
                        {s.label}
                        {s.points != null && s.points !== 0 && (
                          <span className={s.points > 0 ? "ml-1 text-emerald-500" : "ml-1 text-rose-500"}>
                            {s.points > 0 ? `+${s.points}` : String(s.points)}
                          </span>
                        )}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </Card>
          )}
        </aside>

        <Card className="snap-start h-[calc(100dvh-3.5rem)] p-0 overflow-hidden flex flex-col lg:snap-none lg:h-full lg:min-h-0">
          <div className="px-4 py-2 border-b border-border text-xs text-muted-foreground flex items-center justify-between shrink-0">
            <span>Original dossier</span>
            {lead.report_date && <span>{formatReportDate(lead.report_date)}</span>}
          </div>
          {storageMissing ? (
            <div className="flex-1 grid place-items-center bg-muted/10 px-6 py-12 text-center">
              <div className="max-w-md space-y-3">
                <FileWarning className="h-10 w-10 text-muted-foreground/60 mx-auto" />
                <div className="text-sm font-medium">Original dossier HTML is no longer available</div>
                <p className="text-xs text-muted-foreground">
                  The lead record is intact and the score/verdict data is still here, but the
                  underlying HTML file in storage can't be loaded. Sidebar data and signals
                  remain accurate.
                </p>
                {isAdmin && (
                  <p className="text-xs text-muted-foreground">
                    Re-upload the original ELISS HTML from the{" "}
                    <Link to="/upload" className="text-primary hover:underline">
                      Upload
                    </Link>{" "}
                    page to restore the dossier view.
                  </p>
                )}
              </div>
            </div>
          ) : (
            <iframe
              ref={iframeRef}
              title="Dossier"
              {...(useSrcDoc
                ? {
                    srcDoc: substituteTokens(html as string).replace(
                      "</head>",
                      `<style>
                        ::-webkit-scrollbar { width: 8px; height: 8px; }
                        ::-webkit-scrollbar-track { background: transparent; }
                        ::-webkit-scrollbar-thumb { background: hsl(215 20% 65% / 0.4); border-radius: 9999px; }
                        ::-webkit-scrollbar-thumb:hover { background: hsl(215 20% 65% / 0.6); }
                        html { scrollbar-width: thin; scrollbar-color: hsl(215 20% 65% / 0.4) transparent; }
                      </style>${iframeMobileCss}${iframeTargetBlankScript}</head>`,
                    ),
                  }
                : { src: htmlUrl || undefined })}
              /* SECURITY: deliberately omit `allow-same-origin` so user-uploaded
                 dossier HTML, even if it contains scripts that slip through
                 server-side sanitization, cannot read this app's cookies,
                 localStorage, or call /server/api/* with the viewer's
                 credentials. Sandbox-escape requires BOTH allow-scripts AND
                 allow-same-origin together — removing one closes the hole. */
              sandbox="allow-scripts allow-popups"
              className="w-full flex-1 bg-white"
              /* onLoad handler intentionally removed: with allow-same-origin
                 gone, parent JS cannot reach the iframe document. Link
                 retargeting now lives entirely inside the srcdoc-injected
                 script, which runs in the iframe's own context. */
            />
          )}
        </Card>
      </div>
    </div>
  );
}