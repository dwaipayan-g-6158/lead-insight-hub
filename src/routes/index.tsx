import { createFileRoute } from "@tanstack/react-router";
import { DashboardPage } from "@/components/DashboardPage";
import { AppShell } from "@/components/AppShell";
import { AuthGate } from "@/components/AuthGate";

function IndexPage() {
  return (
    <AuthGate>
      <AppShell>
        <DashboardPage />
      </AppShell>
    </AuthGate>
  );
}

export const Route = createFileRoute("/")({
  component: IndexPage,
});
