import { Suspense, lazy, useEffect, useState } from "react";
import { toast } from "sonner";
import { AlertCircle, Sparkles } from "lucide-react";
import { Spinner } from "@/components/Spinner";

// Lazy chunk — only fetched when the localStorage gate flag is present.
// Bundled into its own JS file by Vite's code splitter, so the main bundle
// never references the file's contents for users without the flag.
const ExtendedToggle = lazy(() => import("./ExtendedToggle"));

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

import { ApiError, createDossierRequest } from "@/lib/api";
import { useDossierActivity } from "@/lib/dossier-activity";
import { useAuth } from "@/lib/auth";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

type IntakeForm = {
  name: string;
  email: string;
  linkedin_url: string;
  company_url: string;
  notes: string;
};

const EMPTY_FORM: IntakeForm = {
  name: "",
  email: "",
  linkedin_url: "",
  company_url: "",
  notes: "",
};

// The Create-Dossier modal can be opened from several "Create dossier" buttons
// (LeadsListPage header + empty state, UploadPage header + cards). The FLIP
// "fly to corner" animation in ui/dialog.tsx targets a CSS selector, so to make
// the modal emerge from — and minimize back into — the EXACT button the user
// clicked (e.g. Cancel reads as "put it back where I got it"), each trigger
// stamps itself with this data-attribute on click. Only one element carries the
// marker at a time; the dialog's selector resolves to it. If the marker is
// missing/hidden the dialog falls back to the top-right viewport corner.
const ORIGIN_SELECTOR = "[data-cd-origin]";

export function markDossierOrigin(el: HTMLElement | null): void {
  if (typeof document === "undefined") return;
  document
    .querySelectorAll(ORIGIN_SELECTOR)
    .forEach((n) => n.removeAttribute("data-cd-origin"));
  if (el) el.setAttribute("data-cd-origin", "");
}

// Mirrors the server-side intake invariant in routes/dossiers.js — at least
// one of (name AND email), linkedin_url, or company_url must be present.
function validateIntake(form: IntakeForm): string | null {
  const name = form.name.trim();
  const email = form.email.trim();
  const linkedin = form.linkedin_url.trim();
  const company = form.company_url.trim();
  if ((name && email) || linkedin || company) return null;
  return "Provide at least one of: (name AND email), LinkedIn URL, or company URL";
}

export function CreateDossierModal({ open, onOpenChange }: Props) {
  const { openActivity } = useDossierActivity();
  const { heavyAllowed } = useAuth();
  const [form, setForm] = useState<IntakeForm>(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  // Gate flag is a 60s-TTL activation: AppShell stores Date.now() on 5-tap;
  // we treat the value as a fresh activation iff (now - ts) < 60_000 ms.
  // Single-use: cleared after a successful submit (see handleSubmit success
  // branch), so each heavy run needs its own logo-tap re-arming.
  const isArmed = (): boolean => {
    if (typeof window === "undefined") return false;
    // Entitlement gate first: a non-allowlisted user can never arm the toggle,
    // even with a stale/forged _lih_x flag. The server still re-checks, so this
    // is purely to keep the UI honest (no toggle, no `_x` sent).
    if (!heavyAllowed) return false;
    try {
      const raw = window.localStorage.getItem("_lih_x");
      const ts = raw ? parseInt(raw, 10) : 0;
      return Number.isFinite(ts) && ts > 0 && (Date.now() - ts) < 60_000;
    } catch {
      return false;
    }
  };
  const [gated, setGated] = useState<boolean>(() => isArmed());
  const [extended, setExtended] = useState<boolean>(false);

  // Reset state every time the modal opens fresh.
  useEffect(() => {
    if (open) {
      setForm(EMPTY_FORM);
      setValidationError(null);
      setExtended(false);
      // Re-read the gate flag on each open. Expired timestamps return false
      // here, which hides the toggle and forces a fresh 5-tap.
      setGated(isArmed());
    }
  }, [open]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const err = validateIntake(form);
    if (err) {
      setValidationError(err);
      return;
    }
    setValidationError(null);
    setSubmitting(true);
    try {
      const payload: Record<string, string> = {};
      if (form.name.trim()) payload.name = form.name.trim();
      if (form.email.trim()) payload.email = form.email.trim();
      if (form.linkedin_url.trim()) payload.linkedin_url = form.linkedin_url.trim();
      if (form.company_url.trim()) payload.company_url = form.company_url.trim();
      if (form.notes.trim()) payload.notes = form.notes.trim();
      // Server gates the meaning of `_x`; non-allowlisted callers get the
      // same response shape and the same dossier as if it weren't sent.
      if (gated && extended) payload._x = "h";
      const res = await createDossierRequest({ data: payload });
      // Single-use semantics: clear the activation flag on success so the
      // next heavy run needs a fresh 5-tap re-arming. Failed submits do not
      // clear the flag — the user can retry within the original 60s window.
      if (gated && extended) {
        try {
          window.localStorage.removeItem("_lih_x");
        } catch {
          /* ignore */
        }
      }
      // Hand off to the global activity popup, then close this intake modal.
      openActivity(res.request_id);
      onOpenChange(false);
    } catch (e) {
      // Dedup hit — server says "this person already has a request in
      // flight". Treat as a soft success: jump into the existing request's
      // activity popup rather than dumping the user back at intake.
      if (
        e instanceof ApiError &&
        e.status === 409 &&
        e.payload?.error === "duplicate_in_flight" &&
        e.payload?.request_id
      ) {
        toast.info("Already in progress for this person — joining the live request");
        openActivity(String(e.payload.request_id));
        onOpenChange(false);
      } else {
        const msg = e instanceof Error ? e.message : "Submission failed";
        toast.error(msg);
      }
    } finally {
      setSubmitting(false);
    }
  };

  // Clear the "please supply one of…" error the moment the form satisfies
  // the invariant, so users don't keep seeing a stale message after they
  // typed the fix.
  useEffect(() => {
    if (validationError && !validateIntake(form)) {
      setValidationError(null);
    }
  }, [form, validationError]);

  const set = (k: keyof IntakeForm) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm({ ...form, [k]: e.target.value });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl" flyTarget={ORIGIN_SELECTOR}>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            Create dossier
          </DialogTitle>
          <DialogDescription>
            We'll enrich the prospect, score the lead, and render a full dossier — usually 2-3 minutes.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 mt-2">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="cd-name">Name</Label>
              <Input
                id="cd-name"
                value={form.name}
                onChange={set("name")}
                placeholder="Sarah Johnson"
                autoComplete="off"
                autoFocus
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="cd-email">Work email</Label>
              <Input
                id="cd-email"
                type="email"
                value={form.email}
                onChange={set("email")}
                placeholder="sarah.johnson@contoso.org"
                autoComplete="off"
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="cd-linkedin">LinkedIn URL</Label>
            <Input
              id="cd-linkedin"
              type="url"
              value={form.linkedin_url}
              onChange={set("linkedin_url")}
              placeholder="https://www.linkedin.com/in/…"
              autoComplete="off"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="cd-company">Company URL</Label>
            <Input
              id="cd-company"
              type="url"
              value={form.company_url}
              onChange={set("company_url")}
              placeholder="https://www.contoso.org"
              autoComplete="off"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="cd-notes">
              Notes <span className="text-muted-foreground font-normal">(optional)</span>
            </Label>
            <Textarea
              id="cd-notes"
              value={form.notes}
              onChange={set("notes")}
              placeholder="Met at ManageEngine Shield - Interested in Log360 SIEM replacement."
              rows={3}
            />
          </div>
          {gated && (
            <Suspense fallback={null}>
              <ExtendedToggle
                value={extended}
                onChange={setExtended}
                disabled={submitting}
              />
            </Suspense>
          )}
          {validationError && (
            <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
              <span>{validationError}</span>
            </div>
          )}
          <p className="text-xs text-muted-foreground">
            At least one of: <span className="font-medium">(name AND email)</span>,{" "}
            <span className="font-medium">LinkedIn URL</span>, or{" "}
            <span className="font-medium">company URL</span>.
          </p>
          <div className="flex flex-row-reverse gap-2 pt-1">
            <Button type="submit" disabled={submitting} className="cursor-pointer">
              {submitting ? (
                <>
                  <Spinner className="h-4 w-4 mr-2" />
                  Submitting…
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4 mr-2" />
                  Generate
                </>
              )}
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => onOpenChange(false)}
              disabled={submitting}
              className="cursor-pointer"
            >
              Cancel
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
