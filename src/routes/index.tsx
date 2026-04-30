import { createFileRoute } from "@tanstack/react-router";
import { AuthGate } from "@/components/AuthGate";
import { AppShell } from "@/components/AppShell";
import { DashboardPage } from "@/components/DashboardPage";

export const Route = createFileRoute("/")({
  component: () => (
    <AuthGate>
      <AppShell>
        <DashboardPage />
      </AppShell>
    </AuthGate>
  ),
});
