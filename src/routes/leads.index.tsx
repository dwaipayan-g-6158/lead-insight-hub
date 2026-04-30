import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";
import { AuthGate } from "@/components/AuthGate";
import { AppShell } from "@/components/AppShell";
import { LeadsListPage } from "@/components/LeadsListPage";

const searchSchema = z.object({
  q: z.string().optional(),
  tier: z.enum(["HOT", "WARM", "COLD"]).optional(),
  company: z.string().optional(),
  min: z.number().int().min(0).max(100).optional(),
  max: z.number().int().min(0).max(100).optional(),
  signal: z.string().optional(),
  signal_type: z.string().optional(),
});

export const Route = createFileRoute("/leads/")({
  validateSearch: (input) => searchSchema.parse(input),
  component: () => (
    <AuthGate>
      <AppShell>
        <LeadsListPage />
      </AppShell>
    </AuthGate>
  ),
});