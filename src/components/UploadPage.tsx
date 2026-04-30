import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { useServerFn } from "@tanstack/react-start";
import { Link } from "@tanstack/react-router";
import { uploadDossier } from "@/server/leads.functions";
import { Card } from "@/components/ui/card";
import { Upload, CheckCircle2, AlertCircle, Loader2, FileText } from "lucide-react";

type Row = { name: string; status: "pending" | "ok" | "error"; message?: string; leadId?: string };

export function UploadPage() {
  const fn = useServerFn(uploadDossier);
  const [rows, setRows] = useState<Row[]>([]);
  const [busy, setBusy] = useState(false);

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
    <div className="space-y-5 max-w-3xl">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Upload dossiers</h1>
        <p className="text-sm text-muted-foreground mt-1">Drop one or many ELISS HTML reports — we parse, store, and index them.</p>
      </div>

      <Card
        {...getRootProps()}
        className={`p-10 border-2 border-dashed cursor-pointer transition-colors ${
          isDragActive ? "border-primary bg-primary/5" : "border-border hover:border-primary/50"
        }`}
      >
        <input {...getInputProps()} />
        <div className="flex flex-col items-center text-center">
          <div className="h-12 w-12 rounded-full bg-primary/15 grid place-items-center mb-3">
            <Upload className="h-5 w-5 text-primary" />
          </div>
          <div className="font-medium">{isDragActive ? "Drop the files here" : "Drag & drop HTML dossiers"}</div>
          <div className="text-sm text-muted-foreground mt-1">or click to browse · supports bulk upload</div>
        </div>
      </Card>

      {rows.length > 0 && (
        <Card className="p-0 overflow-hidden">
          <div className="px-4 py-2 border-b border-border text-xs uppercase tracking-wider text-muted-foreground flex items-center justify-between">
            <span>Processing queue</span>
            {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          </div>
          <ul className="divide-y divide-border">
            {rows.map((r, i) => (
              <li key={i} className="flex items-center gap-3 px-4 py-3 text-sm">
                <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
                <span className="truncate flex-1">{r.name}</span>
                {r.status === "pending" && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
                {r.status === "ok" && (
                  <>
                    <span className="text-xs text-muted-foreground">{r.message}</span>
                    <CheckCircle2 className="h-4 w-4 text-[oklch(0.7_0.18_145)]" />
                    {r.leadId && <Link to="/leads/$leadId" params={{ leadId: r.leadId }} className="text-xs text-primary hover:underline">View</Link>}
                  </>
                )}
                {r.status === "error" && (
                  <>
                    <span className="text-xs text-destructive truncate max-w-[40ch]" title={r.message}>{r.message}</span>
                    <AlertCircle className="h-4 w-4 text-destructive" />
                  </>
                )}
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}