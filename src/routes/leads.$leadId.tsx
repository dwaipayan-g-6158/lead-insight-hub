import { createFileRoute } from "@tanstack/react-router";
import { LeadDetailPage } from "@/components/LeadDetailPage";

export const Route = createFileRoute("/leads/$leadId")({
  component: RouteComponent,
});

function RouteComponent() {
  const { leadId } = Route.useParams();
  return <LeadDetailPage id={leadId} />;
}