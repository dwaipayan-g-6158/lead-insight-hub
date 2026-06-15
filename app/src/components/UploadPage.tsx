import { useCallback, useEffect, useMemo, useState } from "react";
import { useDropzone } from "react-dropzone";
import { useServerFn } from "@/lib/use-server-fn";
import { Link } from "@tanstack/react-router";
import { listLeads, uploadDossier } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useDossierActivity } from "@/lib/dossier-activity";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { CreateDossierModal, markDossierOrigin } from "@/components/CreateDossierModal";
import { tierClasses } from "@/lib/tier";
import type { LeadListRow } from "@/types/leads";
import {
  Upload,
  CheckCircle2,
  AlertCircle,
  FileText,
  Sparkles,
  Info,
  ArrowLeft,
  History,
} from "lucide-react";
import { Spinner } from "@/components/Spinner";

type Row = { name: string; status: "pending" | "ok" | "error"; message?: string; leadId?: string };

const RECENT_LIMIT = 8;

const cleanDate = (s: string | null | undefined): string | null =>
  s ? String(s).replace(/[ T]00:00:00.*$/, "") : null;

const byNewest = (a: LeadListRow, b: LeadListRow) => {
  const av = String(a.created_at || a.report_date || "");
  const bv = String(b.created_at || b.report_date || "");
  return bv.localeCompare(av);
};

export function UploadPage() {
  const { isAdmin } = useAuth();
  const fn = useServerFn(uploadDossier);
  const list = useServerFn(listLeads);
  const { leadsVersion } = useDossierActivity();
  const [rows, setRows] = useState<Row[]>([]);
  const [busy, setBusy] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);

  // Mark the clicked button as the FLIP origin so the modal flies out from /
  // minimizes back into the exact button the user pressed.
  const openCreate = (e: React.MouseEvent<HTMLButtonElement>) => {
    markDossierOrigin(e.currentTarget);
    setCreateOpen(true);
  };
  const [recent, setRecent] = useState<LeadListRow[]>([]);
  const [recentLoading, setRecentLoading] = useState(true);
  const [refreshTick, setRefreshTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setRecentLoading(true);
    list({ data: {} })
      .then((res) => {
        if (cancelled) return;
        const leads = ((res as { leads: LeadListRow[] }).leads || [])
          .slice()
          .sort(byNewest)
          .slice(0, RECENT_LIMIT);
        setRecent(leads);
      })
      .catch(() => {
        if (!cancelled) setRecent([]);
      })
      .finally(() => {
        if (!cancelled) setRecentLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [list, refreshTick, leadsVersion]);

  const successCount = useMemo(() => rows.filter((r) => r.status === "ok").length, [rows]);
  useEffect(() => {
    if (successCount > 0) setRefreshTick((t) => t + 1);
  }, [successCount]);

  const onDrop = useCallback(async (files: File[]) => {
    const html = files.filter((f) => f.name.toLowerCase().endsWith(".html") || f.type === "text/html");
    if (!html.length) return;
    setBusy(true);
    setRows((r) => [...r, ...html.map((f) => ({ name: f.name, status: "pending" as const }))]);
    for (const file of html) {
      try {
        const text = await file.text();
        const res = await fn({ data: { filename: file.name, html: text } });
        const r = res as { id: string; updated: boolean };
        setRows((prev) => prev.map((x) => x.name === file.name && x.status === "pending"
          ? { ...x, status: "ok", leadId: r.id, message: r.updated ? "Updated" : "Created" }
          : x));
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Failed";
        setRows((prev) => prev.map((x) => x.name === file.name && x.status === "pending"
          ? { ...x, status: "error", message: msg } : x));
      }
    }
    setBusy(false);
  }, [fn]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "text/html": [".html", ".htm"] },
    multiple: true,
  });

  return (
    <div className="space-y-5 max-w-6xl">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 sm:gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            {isAdmin ? "Upload dossiers" : "Create a dossier"}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {isAdmin
              ? "Drop one or many ELISS HTML reports — we parse, store, and index them."
              : "Generate a new lead from a name, email, or LinkedIn URL."}
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
          <Link to="/leads" className="sm:w-auto">
            <Button variant="outline" size="sm" className="w-full sm:w-auto">
              <ArrowLeft className="h-3.5 w-3.5 mr-1.5" /> Back to leads
            </Button>
          </Link>
        </div>
      </div>

      <CreateDossierModal open={createOpen} onOpenChange={setCreateOpen} />

      {isAdmin ? (
        <div className="grid grid-cols-1 md:grid-cols-[1fr_360px] gap-5 items-stretch">
          <Card
            {...getRootProps()}
            className={`flex flex-col items-center justify-center text-center p-6 border-2 border-dashed cursor-pointer transition-colors min-h-[280px] ${
              isDragActive
                ? "border-primary bg-primary/10"
                : "border-border bg-primary/[0.03] hover:border-primary/60 hover:bg-primary/[0.06]"
            }`}
          >
            <input {...getInputProps()} />
            <div className="h-14 w-14 rounded-full bg-primary/15 grid place-items-center mb-3">
              <Upload className="h-6 w-6 text-primary" />
            </div>
            <div className="font-medium text-base">
              {isDragActive ? "Drop the files here" : "Drag & drop HTML dossiers"}
            </div>
            <div className="text-sm text-muted-foreground mt-1">
              or click to browse · supports bulk upload
            </div>
            <div className="text-xs text-muted-foreground/70 mt-3">
              Accepts .html / .htm files generated by <code className="px-1 rounded bg-muted/40">/eliss-light</code>
            </div>
          </Card>

          <Card className="p-5 flex flex-col">
            <div className="flex items-center gap-2 text-sm font-medium">
              <Info className="h-4 w-4 text-primary" />
              Two ways to add leads
            </div>
            <ul className="mt-3 space-y-3 text-sm text-muted-foreground flex-1">
              <li>
                <div className="flex items-center gap-1.5 text-foreground font-medium">
                  <Upload className="h-3.5 w-3.5" /> Upload
                </div>
                <p className="mt-1">
                  Drop HTML you generated locally with <code className="text-xs">/eliss-light</code>.
                  Best for bulk re-imports.
                </p>
              </li>
              <li>
                <div className="flex items-center gap-1.5 text-foreground font-medium">
                  <Sparkles className="h-3.5 w-3.5" /> Create
                </div>
                <p className="mt-1">
                  Let the server generate the dossier end-to-end from just a name,
                  email, or LinkedIn URL. ~3 min per lead.
                </p>
              </li>
            </ul>
            <Button
              className="w-full mt-4 cursor-pointer"
              size="sm"
              onClick={openCreate}
            >
              <Sparkles className="h-3.5 w-3.5 mr-1.5" /> Create dossier now
            </Button>
          </Card>
        </div>
      ) : (
        <Card className="p-5 flex flex-col max-w-md">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Info className="h-4 w-4 text-primary" />
            How to add a lead
          </div>
          <ul className="mt-3 space-y-3 text-sm text-muted-foreground flex-1">
            <li>
              <div className="flex items-center gap-1.5 text-foreground font-medium">
                <Sparkles className="h-3.5 w-3.5" /> Create
              </div>
              <p className="mt-1">
                Let the server generate the dossier end-to-end from just a name,
                email, or LinkedIn URL. ~3 min per lead.
              </p>
            </li>
          </ul>
          <Button
            className="w-full mt-4 cursor-pointer"
            size="sm"
            onClick={openCreate}
          >
            <Sparkles className="h-3.5 w-3.5 mr-1.5" /> Create dossier now
          </Button>
        </Card>
      )}

      {rows.length > 0 && (
        <Card className="p-0 overflow-hidden">
          <div className="px-4 py-2 border-b border-border text-xs uppercase tracking-wider text-muted-foreground flex items-center justify-between">
            <span>Processing queue</span>
            {busy && <Spinner className="h-3.5 w-3.5" />}
          </div>
          <ul className="divide-y divide-border">
            {rows.map((r, i) => (
              <li key={i} className="flex items-center gap-3 px-4 py-3 text-sm">
                <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
                <span className="truncate flex-1">{r.name}</span>
                {r.status === "pending" && <Spinner className="h-4 w-4 text-muted-foreground" />}
                {r.status === "ok" && (
                  <>
                    <span className="text-xs text-muted-foreground">{r.message}</span>
                    <CheckCircle2 className="h-4 w-4 text-[oklch(0.7_0.18_145)]" />
                    {r.leadId && (
                      <Link
                        to="/leads/$leadId"
                        params={{ leadId: r.leadId }}
                        className="text-xs text-primary hover:underline"
                      >
                        View
                      </Link>
                    )}
                  </>
                )}
                {r.status === "error" && (
                  <>
                    <span className="text-xs text-destructive truncate max-w-[40ch]" title={r.message}>
                      {r.message}
                    </span>
                    <AlertCircle className="h-4 w-4 text-destructive" />
                  </>
                )}
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card className="p-0 overflow-hidden">
        <div className="px-4 py-2 border-b border-border text-xs uppercase tracking-wider text-muted-foreground flex items-center gap-2">
          <History className="h-3.5 w-3.5" />
          <span>{isAdmin ? "Recent uploads" : "Recent leads"}</span>
          {recentLoading && <Spinner className="h-3 w-3 ml-1" />}
        </div>
        {recent.length === 0 && !recentLoading ? (
          <div className="py-10 flex flex-col items-center gap-2 text-center px-6 text-muted-foreground">
            <FileText className="h-8 w-8 text-muted-foreground/40" />
            <div className="text-sm">{isAdmin ? "No uploads yet" : "No leads yet"}</div>
            <p className="text-xs max-w-sm">
              {isAdmin ? (
                <>
                  Drop an ELISS HTML above, or use <span className="text-foreground font-medium">Create dossier</span> to
                  generate one on demand.
                </>
              ) : (
                <>
                  Use <span className="text-foreground font-medium">Create dossier</span> to generate one on demand.
                </>
              )}
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-border">
            {recent.map((l) => (
              <li key={l.id}>
                <Link
                  to="/leads/$leadId"
                  params={{ leadId: l.id }}
                  className="flex items-center gap-3 px-4 py-3 text-sm hover:bg-accent/30 transition-colors"
                >
                  <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
                  <div className="min-w-0 flex-1">
                    <div className="font-medium truncate">{l.lead_name || "Unnamed lead"}</div>
                    <div className="text-xs text-muted-foreground truncate">
                      {l.company || "—"}
                      {l.lead_title ? ` · ${l.lead_title}` : ""}
                    </div>
                  </div>
                  {l.tier && (
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded-full uppercase tracking-wider shrink-0 ${tierClasses(l.tier)}`}
                    >
                      {l.tier}
                    </span>
                  )}
                  <span className="text-sm font-semibold tabular-nums w-8 text-right shrink-0">
                    {l.composite_score ?? "—"}
                  </span>
                  <span className="text-xs text-muted-foreground hidden md:inline-block w-24 text-right shrink-0">
                    {cleanDate(l.report_date) || "—"}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
