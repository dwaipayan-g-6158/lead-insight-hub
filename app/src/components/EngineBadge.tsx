/**
 * Admin-only pill showing which pipeline produced a dossier.
 *
 * `generation_engine` is stamped at store time by the backend:
 *   - "heavy"  → eliss-heavy-generator (extended 20-profile fan-out)
 *   - "light"  → eliss-generator
 *   - "import" → CSV/HTML upload (not generated here)
 *
 * Returns null for null/legacy/unknown values so legacy leads render nothing.
 * Visibility is gated by the CALLER (wrap in `{isAdmin && ...}`); this
 * component is purely presentational. Styling mirrors the existing list-page
 * status pills (native `title` tooltip, same sizing).
 */

const ENGINE_META: Record<
  string,
  { label: string; className: string; title: string }
> = {
  heavy: {
    label: "Heavy",
    className:
      "bg-amber-500/15 border border-amber-500/30 text-amber-700 dark:text-amber-300",
    title: "Generated with ELISS-Heavy (extended 20-profile fan-out)",
  },
  light: {
    label: "Light",
    className: "bg-accent/40 border border-border text-muted-foreground",
    title: "Generated with ELISS-Light",
  },
  import: {
    label: "Imported",
    className: "bg-accent/40 border border-border text-muted-foreground",
    title: "Imported dossier — uploaded, not generated here",
  },
};

export function EngineBadge({ engine }: { engine: string | null | undefined }) {
  const key = (engine || "").toLowerCase().trim();
  const meta = ENGINE_META[key];
  if (!meta) return null;
  return (
    <span
      className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${meta.className}`}
      title={meta.title}
    >
      {meta.label}
    </span>
  );
}
