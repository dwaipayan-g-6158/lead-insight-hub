import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
  getSettings,
  updateSettings,
  type SettingSpec,
  type SettingsSchema,
  type SettingsValue,
  type SettingsWarning,
} from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Spinner } from "@/components/Spinner";
import {
  Info,
  AlertTriangle,
  RotateCcw,
  Sparkles,
  Save,
} from "lucide-react";

const fmt = (n: number) => n.toLocaleString("en-US");

// Client-side mirror of functions/api/lib/generationSettings.computeWarnings —
// gives live feedback as the super-admin edits. The authoritative list still
// comes back from the server on save.
const CLIP_KEYS = ["clip_verdict_insight", "clip_executive_brief", "clip_demo_playbook"];
const CLIP_WIDTH = 10000;

function computeWarnings(s: Record<string, SettingsValue>): SettingsWarning[] {
  const w: SettingsWarning[] = [];
  const num = (k: string) => Number(s[k]);
  const heavyRisk =
    num("heavy_subagent_timeout_s") >= 700 ||
    (num("heavy_subagent_timeout_s") >= 600 &&
      (s.heavy_parent_model === "claude-opus-4-8" || s.heavy_parent_thinking_enabled === true));
  if (heavyRisk) {
    w.push({
      field: "heavy_subagent_timeout_s",
      level: "warn",
      msg: "Heavy fan-out + parent synthesis + render must finish inside Catalyst's 15-min Job ceiling. A 600s+ subagent timeout combined with an Opus parent and/or parent extended-thinking can push a HOT dossier past it.",
    });
  }
  if (s.heavy_parent_model === "claude-opus-4-8") {
    w.push({ field: "heavy_parent_model", level: "info", msg: "Opus 4.8 on the parent produces the richest dossiers but costs ~3-5x per Heavy run vs Sonnet." });
  }
  if (s.light_model === "claude-opus-4-8") {
    w.push({ field: "light_model", level: "info", msg: "Opus 4.8 on single-call Light costs ~3-5x with limited lift vs Sonnet." });
  }
  if (num("heavy_subagent_web_search_max_uses") >= 12) {
    w.push({ field: "heavy_subagent_web_search_max_uses", level: "warn", msg: "12 searches per subagent (~48 across the fan-out) raises the chance a subagent hits its timeout." });
  }
  for (const k of CLIP_KEYS) {
    if (num(k) >= CLIP_WIDTH) {
      w.push({ field: k, level: "info", msg: `Capped at the ${fmt(CLIP_WIDTH)}-char column width — raising further has no effect (the rendered HTML is uncapped).` });
    }
  }
  return w;
}

function valuesEqual(a: SettingsValue, b: SettingsValue) {
  return a === b;
}

type RowState = "default" | "recommended" | "custom";
function rowState(spec: SettingSpec, v: SettingsValue): RowState {
  if (valuesEqual(v, spec.default)) return "default";
  if (valuesEqual(v, spec.recommended)) return "recommended";
  return "custom";
}

function InfoPopover({ spec }: { spec: SettingSpec }) {
  const recDisplay =
    spec.type === "bool"
      ? spec.recommended
        ? "On"
        : "Off"
      : typeof spec.recommended === "number"
        ? fmt(spec.recommended)
        : String(spec.recommended);
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={`About ${spec.label}`}
          className="inline-grid h-5 w-5 place-items-center rounded-full text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          <Info className="h-4 w-4" />
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className="w-80 text-sm"
        // Avoid the lingering focus-ring on the trigger after a mouse close.
        onCloseAutoFocus={(e) => e.preventDefault()}
      >
        <p className="font-medium text-foreground">{spec.label}</p>
        <p className="mt-1 text-muted-foreground">{spec.help}</p>
        <p className="mt-2 text-muted-foreground">
          <span className="font-medium text-foreground/80">Trade-off: </span>
          {spec.tradeoff}
        </p>
        <p className="mt-2 rounded-md bg-primary/10 px-2.5 py-1.5 text-foreground/90">
          <span className="font-medium">Suggested: {recDisplay}</span>
          {spec.recommendedNote ? ` — ${spec.recommendedNote}` : ""}
        </p>
      </PopoverContent>
    </Popover>
  );
}

function StateBadge({ state }: { state: RowState }) {
  if (state === "default") return <Badge variant="secondary">Default</Badge>;
  if (state === "recommended")
    return <Badge className="bg-primary/20 text-foreground hover:bg-primary/20">Recommended</Badge>;
  return <Badge variant="outline" className="border-amber-500/60 text-amber-600 dark:text-amber-400">Custom</Badge>;
}

function ScaleLine({ spec }: { spec: SettingSpec }) {
  if (spec.type !== "int" || spec.min == null || spec.max == null) return null;
  const rec = typeof spec.recommended === "number" ? spec.recommended : spec.min;
  const pct = ((rec - spec.min) / (spec.max - spec.min)) * 100;
  return (
    <div className="mt-2 select-none">
      <div className="relative h-1.5 rounded-full bg-muted">
        <div
          className="absolute top-1/2 h-3 w-0.5 -translate-y-1/2 rounded bg-primary"
          style={{ left: `${pct}%` }}
          aria-hidden
        />
      </div>
      <div className="mt-1 flex justify-between text-[10px] text-muted-foreground">
        <span>{fmt(spec.min)}</span>
        <span className="text-primary">◆ rec {fmt(rec)}</span>
        <span>{fmt(spec.max)}</span>
      </div>
    </div>
  );
}

function SettingRow({
  fieldKey,
  spec,
  value,
  disabled,
  warnings,
  models,
  onChange,
  onUseRecommended,
}: {
  fieldKey: string;
  spec: SettingSpec;
  value: SettingsValue;
  disabled?: boolean;
  warnings: SettingsWarning[];
  models: { id: string; label: string }[];
  onChange: (v: SettingsValue) => void;
  onUseRecommended: () => void;
}) {
  const state = rowState(spec, value);
  const isRec = valuesEqual(value, spec.recommended);
  const rowWarn = warnings.find((w) => w.level === "warn");
  const rowInfo = warnings.find((w) => w.level === "info");

  return (
    <div className={`py-4 ${disabled ? "opacity-50" : ""}`}>
      <div className="flex flex-wrap items-center gap-2">
        <Label className="text-sm font-medium text-foreground">{spec.label}</Label>
        <InfoPopover spec={spec} />
        <div className="ml-auto flex items-center gap-2">
          <StateBadge state={state} />
          {rowWarn && (
            <span className="inline-block h-2 w-2 rounded-full bg-amber-500" title="May be risky" aria-hidden />
          )}
          {!isRec && (
            <button
              type="button"
              onClick={onUseRecommended}
              disabled={disabled}
              className="text-xs text-primary underline-offset-2 hover:underline disabled:opacity-50"
            >
              Use recommended
            </button>
          )}
        </div>
      </div>

      {/* Control */}
      <div className="mt-2.5">
        {spec.type === "int" && (
          <>
            <div className="flex items-center gap-3">
              <Slider
                value={[Number(value)]}
                min={spec.min}
                max={spec.max}
                step={1}
                disabled={disabled}
                onValueChange={(v) => onChange(v[0])}
                className="flex-1"
              />
              <div className="flex items-center gap-1.5">
                <Input
                  type="number"
                  value={Number(value)}
                  min={spec.min}
                  max={spec.max}
                  disabled={disabled}
                  onChange={(e) => {
                    const n = Number(e.target.value);
                    if (Number.isNaN(n)) return;
                    const clamped = Math.max(spec.min ?? n, Math.min(spec.max ?? n, n));
                    onChange(clamped);
                  }}
                  className="w-24 text-right"
                />
                {spec.unit && (
                  <span className="w-16 text-xs text-muted-foreground">{spec.unit}</span>
                )}
              </div>
            </div>
            <ScaleLine spec={spec} />
          </>
        )}

        {spec.type === "enum" && (
          <Select
            value={String(value)}
            disabled={disabled}
            onValueChange={(v) => onChange(v)}
          >
            <SelectTrigger className="w-full sm:w-96">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(spec.enum ?? []).map((id) => {
                const m = models.find((x) => x.id === id);
                return (
                  <SelectItem key={id} value={id}>
                    {m?.label ?? id}
                  </SelectItem>
                );
              })}
            </SelectContent>
          </Select>
        )}

        {spec.type === "bool" && (
          <div className="flex items-center gap-2">
            <Switch
              checked={Boolean(value)}
              disabled={disabled}
              onCheckedChange={(c) => onChange(c)}
            />
            <span className="text-xs text-muted-foreground">
              {Boolean(value) ? "On" : "Off"}
            </span>
          </div>
        )}
      </div>

      {/* Inline warning/info under the offending field */}
      {rowWarn && (
        <p className="mt-2 flex items-start gap-1.5 text-xs text-amber-600 dark:text-amber-400">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>{rowWarn.msg}</span>
        </p>
      )}
      {!rowWarn && rowInfo && (
        <p className="mt-2 flex items-start gap-1.5 text-xs text-muted-foreground">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>{rowInfo.msg}</span>
        </p>
      )}
    </div>
  );
}

export function SettingsPage() {
  const [schema, setSchema] = useState<SettingsSchema | null>(null);
  const [saved, setSaved] = useState<Record<string, SettingsValue>>({});
  const [draft, setDraft] = useState<Record<string, SettingsValue>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [meta, setMeta] = useState<{ updatedBy: string | null; updatedAt: string | null } | null>(null);
  // Controlled open-state for each engine's "Operational knobs" accordion, keyed
  // by engine. Held in SettingsPage state so it can never be lost to a child
  // re-render/remount during a slider drag (the symptom: accordion collapsing).
  const [opsOpen, setOpsOpen] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const res = await getSettings();
      setSchema(res.schema);
      setSaved(res.settings);
      setDraft(res.settings);
      setMeta(res.meta);
    } catch (e: any) {
      setErr(e?.message || "Failed to load settings");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const liveWarnings = useMemo(() => computeWarnings(draft), [draft]);
  const warningsByField = useMemo(() => {
    const map: Record<string, SettingsWarning[]> = {};
    for (const w of liveWarnings) (map[w.field] ||= []).push(w);
    return map;
  }, [liveWarnings]);

  const dirtyKeys = useMemo(
    () => Object.keys(draft).filter((k) => !valuesEqual(draft[k], saved[k])),
    [draft, saved],
  );
  const dirty = dirtyKeys.length > 0;

  const setField = (k: string, v: SettingsValue) =>
    setDraft((d) => ({ ...d, [k]: v }));

  const resetAll = (mode: "default" | "recommended") => {
    if (!schema) return;
    const next: Record<string, SettingsValue> = { ...draft };
    for (const [k, spec] of Object.entries(schema.settings)) {
      next[k] = mode === "default" ? spec.default : spec.recommended;
    }
    setDraft(next);
  };

  const save = async () => {
    if (!dirty) return;
    setSaving(true);
    try {
      const payload: Record<string, SettingsValue> = {};
      for (const k of dirtyKeys) payload[k] = draft[k];
      const res = await updateSettings({ data: payload });
      setSaved(res.settings);
      setDraft(res.settings);
      setMeta({ updatedBy: res.meta.updatedBy, updatedAt: res.meta.updatedAt });
      const warnCount = res.warnings.filter((w) => w.level === "warn").length;
      toast.success("Settings saved", {
        description: warnCount
          ? `${warnCount} risk warning${warnCount > 1 ? "s" : ""} — review below.`
          : "Applied to the next dossier generation.",
      });
    } catch (e: any) {
      const fields = e?.payload?.fields;
      toast.error("Save failed", {
        description: Array.isArray(fields)
          ? fields.map((f: any) => `${f.field}: ${f.msg}`).join("; ")
          : e?.message || "Validation error",
      });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="grid min-h-[40vh] place-items-center text-muted-foreground">
        <Spinner className="h-6 w-6" />
      </div>
    );
  }
  if (err || !schema) {
    return (
      <Card className="mx-auto mt-10 max-w-lg p-6 text-center">
        <AlertTriangle className="mx-auto h-8 w-8 text-destructive" />
        <h2 className="mt-3 text-lg font-semibold">Couldn't load settings</h2>
        <p className="mt-1 text-sm text-muted-foreground">{err}</p>
        <Button className="mt-4" onClick={load}>Retry</Button>
      </Card>
    );
  }

  const models = schema.models;
  const entries = Object.entries(schema.settings);
  const byEngine = (engine: string, group: string) =>
    entries.filter(([, s]) => s.engine === engine && s.group === group);

  const renderRow = ([key, spec]: [string, SettingSpec]) => {
    const disabled = !!spec.dependsOn && draft[spec.dependsOn] !== true;
    return (
      <div key={key} className="border-b border-border/50 last:border-b-0">
        <SettingRow
          fieldKey={key}
          spec={spec}
          value={draft[key]}
          disabled={disabled}
          warnings={warningsByField[key] ?? []}
          models={models}
          onChange={(v) => setField(key, v)}
          onUseRecommended={() => setField(key, spec.recommended)}
        />
      </div>
    );
  };

  // Plain render function — NOT a nested component. Defining a component inside
  // SettingsPage gives it a new identity every render, so React would unmount +
  // remount this whole subtree on each state change (e.g. a slider's
  // onValueChange), detaching the slider mid-drag and killing the gesture.
  // Invoking it as a function inlines the JSX, which React reconciles normally.
  const renderEngine = (engine: "light" | "heavy") => {
    const richness = byEngine(engine, "richness");
    const operational = byEngine(engine, "operational");
    return (
      <div className="space-y-4">
        <Card className="p-5">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Richness levers
          </h3>
          <div className="mt-1">{richness.map(renderRow)}</div>
        </Card>
        {operational.length > 0 && (
          <Accordion
            type="single"
            collapsible
            value={opsOpen[engine] ?? ""}
            onValueChange={(v) => setOpsOpen((s) => ({ ...s, [engine]: v }))}
          >
            <AccordionItem value="ops" className="rounded-lg border border-border/60 px-4">
              <AccordionTrigger className="text-sm">
                Operational knobs
                <span className="ml-2 text-xs font-normal text-muted-foreground">
                  reliability / storage only — leave unless you know why
                </span>
              </AccordionTrigger>
              <AccordionContent>{operational.map(renderRow)}</AccordionContent>
            </AccordionItem>
          </Accordion>
        )}
      </div>
    );
  };

  const sharedOps = entries.filter(([, s]) => s.engine === "shared");
  const warnList = liveWarnings.filter((w) => w.level === "warn");

  return (
    <TooltipProvider delayDuration={200}>
      <div className="mx-auto max-w-4xl px-4 py-6">
        {/* Header */}
        <div className="flex flex-wrap items-start gap-3">
          <div className="flex-1 min-w-0">
            <h1 className="text-xl font-semibold">Generation settings</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Global, super-admin-only controls for ELISS Light &amp; Heavy. Changes apply to the
              next dossier generation — no redeploy. Each setting shows its safe range and an honest
              recommended value; hover the{" "}
              <Info className="inline h-3.5 w-3.5 align-text-bottom" /> for details.
            </p>
            {meta?.updatedAt && (
              <p className="mt-1 text-xs text-muted-foreground">
                Last changed {meta.updatedAt}
                {meta.updatedBy ? ` by ${meta.updatedBy}` : ""}.
              </p>
            )}
          </div>
          <div className="flex gap-2">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="outline" size="sm" onClick={() => resetAll("recommended")}>
                  <Sparkles className="mr-1.5 h-4 w-4" /> Recommended
                </Button>
              </TooltipTrigger>
              <TooltipContent>Set every field to its suggested happy value</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="sm" onClick={() => resetAll("default")}>
                  <RotateCcw className="mr-1.5 h-4 w-4" /> Defaults
                </Button>
              </TooltipTrigger>
              <TooltipContent>Restore the shipped defaults (inert behavior)</TooltipContent>
            </Tooltip>
          </div>
        </div>

        {/* Risk summary */}
        {warnList.length > 0 && (
          <Card className="mt-4 border-amber-500/40 bg-amber-500/5 p-4">
            <div className="flex items-center gap-2 text-sm font-medium text-amber-600 dark:text-amber-400">
              <AlertTriangle className="h-4 w-4" /> {warnList.length} risk warning
              {warnList.length > 1 ? "s" : ""}
            </div>
            <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
              {warnList.map((w, i) => (
                <li key={i}>• {w.msg}</li>
              ))}
            </ul>
          </Card>
        )}

        {/* Engine tabs */}
        <Tabs defaultValue="light" className="mt-5">
          <TabsList>
            <TabsTrigger value="light">ELISS Light</TabsTrigger>
            <TabsTrigger value="heavy">ELISS Heavy</TabsTrigger>
            <TabsTrigger value="shared">Shared</TabsTrigger>
          </TabsList>
          <TabsContent value="light" className="mt-4">
            {renderEngine("light")}
          </TabsContent>
          <TabsContent value="heavy" className="mt-4">
            {renderEngine("heavy")}
          </TabsContent>
          <TabsContent value="shared" className="mt-4">
            <Card className="p-5">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                Shared — both engines
              </h3>
              <p className="mt-1 text-xs text-muted-foreground">
                Reliability and storage caps used by both pipelines. Not richness levers.
              </p>
              <div className="mt-2">{sharedOps.map(renderRow)}</div>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Sticky save bar */}
        <div className="sticky bottom-0 z-10 mt-6 -mx-4 border-t border-border/60 bg-background/95 px-4 py-3 backdrop-blur">
          <div className="flex items-center justify-between gap-3">
            <span className="text-xs text-muted-foreground">
              {dirty ? `${dirtyKeys.length} unsaved change${dirtyKeys.length > 1 ? "s" : ""}` : "No changes"}
            </span>
            <div className="flex gap-2">
              {dirty && (
                <Button variant="ghost" size="sm" onClick={() => setDraft(saved)} disabled={saving}>
                  Discard
                </Button>
              )}
              <Button size="sm" onClick={save} disabled={!dirty || saving}>
                {saving ? <Spinner className="mr-1.5 h-4 w-4" /> : <Save className="mr-1.5 h-4 w-4" />}
                Save changes
              </Button>
            </div>
          </div>
        </div>
      </div>
    </TooltipProvider>
  );
}
