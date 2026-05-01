import { createFileRoute } from "@tanstack/react-router";
import AnimatedDashboard from "@/components/dashboard/AnimatedDashboard";

export const Route = createFileRoute("/")({
  component: AnimatedDashboard,
});
