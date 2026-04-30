import { createFileRoute } from "@tanstack/react-router";
import { AuthGate } from "@/components/AuthGate";
import { AppShell } from "@/components/AppShell";
import { LeadDetailPage } from "@/components/LeadDetailPage";

export const Route = createFileRoute("/leads/$leadId")({
  component: RouteComponent,
});

function RouteComponent() {
  const { leadId } = Route.useParams();
  return (
    <AuthGate>
      <AppShell>
        <LeadDetailPage id={leadId} />
      </AppShell>
    </AuthGate>
  );
}