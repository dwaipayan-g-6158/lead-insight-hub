import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useRouter } from "@tanstack/react-router";
import { CheckCircle2, Heart, Loader2, Lock, Network, Radar, Sparkles, UserPlus, Zap } from "lucide-react";
import { selfSignup, getSignupConfig, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";

const GRID_BG =
  "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='40' height='40' viewBox='0 0 40 40'><path d='M40 0H0V40' stroke='%239aa0b8' stroke-width='0.5' fill='none'/></svg>\")";

// Client-side fallback allowlist. The server is the source of truth — this
// is just for the helper text + an immediate, non-roundtripping client
// validation. If /auth/signup/config returns a different list, the rendered
// helper text updates accordingly.
const FALLBACK_DOMAINS = ["@zohocorp.com", "@zohotest.com"];

const schema = z.object({
  first_name: z.string().trim().min(1, "First name is required"),
  last_name: z.string().trim().optional().default(""),
  email_id: z.string().trim().toLowerCase().email("Enter a valid email"),
});
type FormValues = z.infer<typeof schema>;

export function SignUpPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const logoSrc = `${import.meta.env.BASE_URL}logo.svg`;
  const [busy, setBusy] = useState(false);
  const [success, setSuccess] = useState<{ email: string; message: string } | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const [allowedDomains, setAllowedDomains] = useState<string[]>(FALLBACK_DOMAINS);

  // Already signed in? Bounce to the dashboard — there's no reason for an
  // authed user to be on /signup. Gate on !authLoading so we don't redirect
  // during the initial SDK probe (otherwise we'd flicker the redirect for
  // unauthenticated visitors whose `user` hasn't resolved to null yet).
  useEffect(() => {
    if (!authLoading && user) {
      router.navigate({ to: "/" });
    }
  }, [authLoading, user, router]);

  useEffect(() => {
    let cancelled = false;
    getSignupConfig()
      .then((res) => {
        if (cancelled) return;
        if (Array.isArray(res?.allowed_domains) && res.allowed_domains.length > 0) {
          setAllowedDomains(res.allowed_domains);
        }
      })
      .catch(() => {
        // Network/unknown failure — keep the fallback; the server still
        // re-validates on submit so this is purely cosmetic.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { first_name: "", last_name: "", email_id: "" },
  });

  const goToSignIn = () => router.navigate({ to: "/" });

  const onSubmit = async (values: FormValues) => {
    setServerError(null);

    // Client-side domain pre-check using whatever list we resolved from
    // /auth/signup/config (falls back to the hardcoded list above). The
    // server re-validates so this is just to avoid a roundtrip on the
    // obvious cases.
    const at = values.email_id.lastIndexOf("@");
    const domain = at >= 0 ? "@" + values.email_id.slice(at + 1) : "";
    if (allowedDomains.length > 0 && !allowedDomains.includes(domain)) {
      form.setError("email_id", {
        type: "manual",
        message: `Only ${allowedDomains.join(", ")} emails can self-signup.`,
      });
      return;
    }

    setBusy(true);
    try {
      const res = await selfSignup({
        data: { ...values, last_name: values.last_name || "" },
      });
      setSuccess({
        email: res.email,
        message: res.message || "Check your email to activate your account.",
      });
      form.reset();
    } catch (e) {
      if (e instanceof ApiError) {
        const msg = e.payload?.error || e.message;
        if (e.status === 409) {
          form.setError("email_id", { type: "manual", message: msg });
        } else if (e.status === 403 || e.status === 400) {
          form.setError("email_id", { type: "manual", message: msg });
        } else {
          setServerError(msg);
        }
      } else {
        setServerError((e as Error)?.message || "Signup failed.");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="relative min-h-[100svh] min-h-[100dvh] w-full overflow-x-hidden bg-background text-foreground">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(124,111,240,0.18),transparent_55%)]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 bottom-0 h-1/2 bg-[radial-gradient(ellipse_at_bottom,rgba(99,102,241,0.08),transparent_60%)]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.04]"
        style={{ backgroundImage: GRID_BG }}
      />

      <div className="relative z-10 grid min-h-[100svh] min-h-[100dvh] w-full lg:grid-cols-[1.05fr_1fr]">
        {/* LEFT — brand panel (lg+) mirrors LoginScreen for consistency. */}
        <aside className="hidden lg:flex flex-col justify-between border-r border-border/60 p-10 xl:p-14">
          <div className="flex items-center gap-3">
            <img src={logoSrc} alt="ELISS Logo" width={40} height={40} className="h-10 w-auto brand-breathe" />
            <div className="flex flex-col leading-none">
              <span className="text-[10px] font-semibold uppercase tracking-[0.34em] text-primary">
                ELISS
              </span>
              <span className="mt-1 text-[10px] uppercase tracking-[0.22em] text-muted-foreground/70">
                Enterprise Edition
              </span>
            </div>
          </div>

          <div className="max-w-md">
            <h1 className="text-3xl font-semibold leading-[1.12] tracking-tight xl:text-[2.5rem]">
              Join the workspace,
              <br />
              built for the team.
            </h1>
            <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
              Self-signup is open to{" "}
              <span className="font-medium text-foreground">@zohocorp.com</span>{" "}
              addresses. You'll get an activation email from ELISS to set your
              password.
            </p>

            <ul className="mt-8 space-y-3 text-sm feature-stagger">
              <li className="feature-item flex items-start gap-3 text-foreground/85">
                <span className="mt-0.5 inline-grid h-7 w-7 place-items-center rounded-md border border-border/60 bg-card/50 text-primary">
                  <Sparkles className="h-3.5 w-3.5" />
                </span>
                <div>
                  <div className="font-medium text-foreground">Auto-parsed dossiers</div>
                  <div className="text-xs text-muted-foreground">
                    ELISS HTML reports turned into structured scores in seconds.
                  </div>
                </div>
              </li>
              <li className="feature-item flex items-start gap-3 text-foreground/85">
                <span className="mt-0.5 inline-grid h-7 w-7 place-items-center rounded-md border border-border/60 bg-card/50 text-primary">
                  <Zap className="h-3.5 w-3.5" />
                </span>
                <div>
                  <div className="font-medium text-foreground">Fit · Intent · Timing · Budget</div>
                  <div className="text-xs text-muted-foreground">
                    Multi-dimensional scoring with tier and confidence rollups.
                  </div>
                </div>
              </li>
              <li className="feature-item flex items-start gap-3 text-foreground/85">
                <span className="mt-0.5 inline-grid h-7 w-7 place-items-center rounded-md border border-border/60 bg-card/50 text-primary">
                  <Network className="h-3.5 w-3.5" />
                </span>
                <div>
                  <div className="font-medium text-foreground">ManageEngine Ecosystem lean</div>
                  <div className="text-xs text-muted-foreground">
                    AD360 &amp; Log360 aware-GTM — backed by{" "}
                    <span className="inline-flex items-center gap-1 align-baseline">
                      <span className="font-medium text-foreground">Love</span>
                      <Heart
                        aria-label="love"
                        className="h-3.5 w-3.5 text-[oklch(0.65_0.22_25)] fill-[oklch(0.65_0.22_25)] heart-beat"
                      />
                    </span>
                    .
                  </div>
                </div>
              </li>
            </ul>
          </div>

          <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.2em] text-muted-foreground/80">
            <Radar className="h-3.5 w-3.5 text-primary/70" />
            <span>Enterprise Lead Intelligence and Scoring System</span>
          </div>
        </aside>

        {/* RIGHT — form panel */}
        <main className="flex min-h-[100svh] min-h-[100dvh] flex-col items-center justify-start lg:justify-center px-4 py-6 pt-[max(env(safe-area-inset-top),1.5rem)] pb-[max(env(safe-area-inset-bottom),1.5rem)] sm:px-8">
          <div className="w-full max-w-[420px]">
            <div className="mb-6 flex flex-col items-center gap-2 text-center lg:hidden">
              <img src={logoSrc} alt="" aria-hidden width={36} height={36} className="h-9 w-auto" />
              <div className="text-[11px] font-semibold uppercase tracking-[0.18em] leading-tight text-foreground/85">
                Enterprise Lead Intelligence
                <br />
                and Scoring System
              </div>
            </div>

            <div className="login-card-rise overflow-hidden rounded-2xl border border-border/80 bg-card/80 shadow-[0_24px_70px_-24px_rgba(0,0,0,0.75)] backdrop-blur-sm">
              <div className="border-b border-border/60 px-6 pb-4 pt-5">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-base font-semibold tracking-tight">
                      {success ? "Activation email sent" : "Create your account"}
                    </div>
                    <div className="mt-0.5 text-xs text-muted-foreground">
                      {success
                        ? "One last step to get you in."
                        : "Open to @zohocorp.com addresses."}
                    </div>
                  </div>
                  <span className="login-badge-glow hidden sm:inline-grid h-9 w-9 place-items-center rounded-full border border-border/60 bg-background/60 text-primary">
                    {success ? (
                      <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                    ) : (
                      <UserPlus className="h-4 w-4" />
                    )}
                  </span>
                </div>
              </div>

              <div className="px-6 py-5">
                {success ? (
                  <div className="space-y-4 text-sm">
                    <p className="text-foreground/90">
                      We've sent an activation link to{" "}
                      <span className="font-medium text-foreground">{success.email}</span>.
                      Click the link in that email to set your password and
                      finish signing in.
                    </p>
                    <p className="text-xs text-muted-foreground">
                      The email comes from Zoho Catalyst. Check your spam
                      folder if you don't see it within a couple of minutes.
                    </p>
                    <Button type="button" className="w-full" onClick={goToSignIn}>
                      Back to sign in
                    </Button>
                  </div>
                ) : (
                  <Form {...form}>
                    <form
                      onSubmit={form.handleSubmit(onSubmit)}
                      className="space-y-4"
                      noValidate
                    >
                      <div className="grid grid-cols-2 gap-3">
                        <FormField
                          name="first_name"
                          control={form.control}
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel htmlFor="su-first-name">First name</FormLabel>
                              <FormControl>
                                <Input
                                  id="su-first-name"
                                  autoComplete="given-name"
                                  autoFocus
                                  placeholder="John"
                                  {...field}
                                />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                        <FormField
                          name="last_name"
                          control={form.control}
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel htmlFor="su-last-name">
                                Last name{" "}
                                <span className="text-muted-foreground font-normal">
                                  (optional)
                                </span>
                              </FormLabel>
                              <FormControl>
                                <Input
                                  id="su-last-name"
                                  autoComplete="family-name"
                                  placeholder="Doe"
                                  {...field}
                                />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                      </div>
                      <FormField
                        name="email_id"
                        control={form.control}
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel htmlFor="su-email">Work email</FormLabel>
                            <FormControl>
                              <Input
                                id="su-email"
                                type="email"
                                autoComplete="email"
                                inputMode="email"
                                placeholder="john.doe@zohocorp.com"
                                {...field}
                              />
                            </FormControl>
                            <FormDescription className="text-xs">
                              Only @zohocorp.com domain can self-signup.
                            </FormDescription>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      {serverError && (
                        <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
                          {serverError}
                        </div>
                      )}

                      <Button type="submit" className="w-full" disabled={busy}>
                        {busy && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                        Create account
                      </Button>

                      <div className="pt-1 text-center text-xs text-muted-foreground">
                        Already have an account?{" "}
                        <button
                          type="button"
                          onClick={goToSignIn}
                          className="font-medium text-primary hover:underline"
                        >
                          Sign in
                        </button>
                      </div>
                    </form>
                  </Form>
                )}
              </div>

              <div className="flex items-center justify-between border-t border-border/60 bg-background/30 px-6 py-3 text-[10px] uppercase tracking-[0.18em] text-muted-foreground/80">
                <span className="flex items-center gap-1.5">
                  <Lock className="h-3 w-3 text-primary/70" />
                  ManageEngine · Confidential
                </span>
                <span>Internal use only</span>
              </div>
            </div>

            <p className="mt-5 text-center text-[11px] text-muted-foreground/70">
              By creating an account you agree to the workspace acceptable-use policy.
            </p>
          </div>
        </main>
      </div>
    </div>
  );
}
