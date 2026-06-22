import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { AuditPage } from "@/components/AuditPage";
import { useAuth } from "@/lib/auth";
import { ShieldAlert } from "lucide-react";
import { Spinner } from "@/components/Spinner";
import { Card } from "@/components/ui/card";

// The Audit log is restricted to admins + the super-admin. This is a UI gate;
// the server re-checks via requireAdminOrSuperAdmin on /audit, so a non-admin
// who deep-links here still gets 403s from the API.
function AuditGuard() {
  const { isAdmin, isSuperAdmin, roleLoading, user } = useAuth();
  const navigate = useNavigate();
  const allowed = isAdmin || isSuperAdmin;

  useEffect(() => {
    if (!roleLoading && user && !allowed) {
      const t = setTimeout(() => navigate({ to: "/" }), 1500);
      return () => clearTimeout(t);
    }
  }, [roleLoading, user, allowed, navigate]);

  if (roleLoading) {
    return (
      <div className="grid min-h-[40vh] place-items-center text-muted-foreground">
        <Spinner className="h-6 w-6" />
      </div>
    );
  }
  if (!allowed) {
    return (
      <Card className="p-6 max-w-lg mx-auto mt-10 text-center">
        <ShieldAlert className="h-8 w-8 text-destructive mx-auto" />
        <h2 className="mt-3 text-lg font-semibold">Admin access required</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          The audit log is available to administrators only. Redirecting…
        </p>
      </Card>
    );
  }
  return <AuditPage />;
}

export const Route = createFileRoute("/audit")({
  component: AuditGuard,
});
