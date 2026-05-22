import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { AdminPage } from "@/components/AdminPage";
import { useAuth } from "@/lib/auth";
import { Loader2, ShieldAlert } from "lucide-react";
import { Card } from "@/components/ui/card";

function AdminGuard() {
  const { isAdmin, roleLoading, user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!roleLoading && user && !isAdmin) {
      // Soft redirect after a short delay so the message is readable
      const t = setTimeout(() => navigate({ to: "/" }), 1500);
      return () => clearTimeout(t);
    }
  }, [roleLoading, user, isAdmin, navigate]);

  if (roleLoading) {
    return (
      <div className="grid min-h-[40vh] place-items-center text-muted-foreground">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    );
  }
  if (!isAdmin) {
    return (
      <Card className="p-6 max-w-lg mx-auto mt-10 text-center">
        <ShieldAlert className="h-8 w-8 text-destructive mx-auto" />
        <h2 className="mt-3 text-lg font-semibold">Admin access required</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Your account does not have permission to view this page. Redirecting…
        </p>
      </Card>
    );
  }
  return <AdminPage />;
}

export const Route = createFileRoute("/admin")({
  component: AdminGuard,
});
