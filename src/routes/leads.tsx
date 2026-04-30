import { createFileRoute } from "@tanstack/react-router";
import { AuthGate } from "@/components/AuthGate";
import { AppShell } from "@/components/AppShell";
import { LeadsListPage } from "@/components/LeadsListPage";

export const Route = createFileRoute("/leads")({
  component: () => (
    <AuthGate>
      <AppShell>
        <LeadsListPage />
      </AppShell>
    </AuthGate>
  ),
});