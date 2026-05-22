import { Label } from "@/components/ui/label";

type Props = {
  value: boolean;
  onChange: (next: boolean) => void;
  disabled?: boolean;
};

// Loaded as a lazy chunk by CreateDossierModal — only emitted into the bundle
// when the localStorage gate is active. The label is intentionally vague
// ("Extended research") so a curious user inspecting a network-loaded chunk
// can't trivially work out what it controls.
export default function ExtendedToggle({ value, onChange, disabled }: Props) {
  return (
    <label
      className="flex items-start gap-3 rounded-md border border-border/60 bg-card/40 px-3 py-2 cursor-pointer select-none has-[:disabled]:opacity-60"
    >
      <input
        type="checkbox"
        checked={value}
        onChange={(e) => onChange(e.target.checked)}
        disabled={disabled}
        className="mt-1 h-4 w-4 rounded border-border accent-primary cursor-pointer"
      />
      <div className="flex-1">
        <Label className="text-sm font-medium cursor-pointer">
          Extended research
        </Label>
        <p className="text-xs text-muted-foreground mt-0.5">
          Slower, broader sourcing. Use sparingly.
        </p>
      </div>
    </label>
  );
}
