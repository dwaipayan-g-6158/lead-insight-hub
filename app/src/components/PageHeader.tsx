import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

/**
 * Shared page header. Standardizes the hero block across every page so the
 * structure is identical: an uppercase eyebrow label, a route icon beside the
 * title, and a muted description. Page-level controls (buttons, live
 * indicators) go in the right-aligned `aside` slot.
 *
 * Before this existed each page inlined its own header — Audit had an icon,
 * Admin had an icon + eyebrow, and Leads/Upload/Settings had a bare <h1>.
 */
export function PageHeader({
  eyebrow,
  icon: Icon,
  title,
  description,
  aside,
}: {
  eyebrow: string;
  icon: LucideIcon;
  title: ReactNode;
  description?: ReactNode;
  aside?: ReactNode;
}) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 sm:gap-4">
      <div className="min-w-0">
        <div className="text-xs uppercase tracking-[0.2em] text-primary">{eyebrow}</div>
        <h1 className="text-2xl font-semibold tracking-tight mt-1 flex items-center gap-2">
          <Icon className="h-6 w-6 text-primary shrink-0" aria-hidden />
          {title}
        </h1>
        {description && (
          <p className="text-sm text-muted-foreground mt-1">{description}</p>
        )}
      </div>
      {aside}
    </div>
  );
}
