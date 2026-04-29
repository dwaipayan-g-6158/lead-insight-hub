export function tierClasses(tier: string | null | undefined) {
  switch ((tier ?? "").toUpperCase()) {
    case "HOT":
      return "bg-[oklch(var(--tier-hot)/0.15)] text-[oklch(var(--tier-hot))] border border-[oklch(var(--tier-hot)/0.4)]";
    case "WARM":
      return "bg-[oklch(var(--tier-warm)/0.15)] text-[oklch(var(--tier-warm))] border border-[oklch(var(--tier-warm)/0.4)]";
    case "COLD":
      return "bg-[oklch(var(--tier-cold)/0.15)] text-[oklch(var(--tier-cold))] border border-[oklch(var(--tier-cold)/0.4)]";
    default:
      return "bg-muted text-muted-foreground border border-border";
  }
}

export function tierColor(tier: string | null | undefined): string {
  switch ((tier ?? "").toUpperCase()) {
    case "HOT": return "oklch(0.65 0.22 25)";
    case "WARM": return "oklch(0.75 0.17 70)";
    case "COLD": return "oklch(0.65 0.13 230)";
    default: return "oklch(0.55 0.02 260)";
  }
}