import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { SettingsPage } from "@/components/SettingsPage";
import { useAuth } from "@/lib/auth";
import { ShieldAlert } from "lucide-react";
import { Spinner } from "@/components/Spinner";
import { Card } from "@/components/ui/card";

// Mirrors AdminGuard (routes/admin.tsx), but gates on isSuperAdmin — the
// single project-owner account (SUPER_ADMIN_EMAIL). The server re-checks via
// requireSuperAdmin on /admin/settings, so this is a UX gate only.
function SuperAdminGuard() {
  const { isSuperAdmin, roleLoading, user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!roleLoading && user && !isSuperAdmin) {
      const t = setTimeout(() => navigate({ to: "/" }), 1500);
      return () => clearTimeout(t);
    }
  }, [roleLoading, user, isSuperAdmin, navigate]);

  if (roleLoading) {
    return (
      <div className="grid min-h-[40vh] place-items-center text-muted-foreground">
        <Spinner className="h-6 w-6" />
      </div>
    );
  }
  if (!isSuperAdmin) {
    return (
      <Card className="p-6 max-w-lg mx-auto mt-10 text-center">
        <ShieldAlert className="h-8 w-8 text-destructive mx-auto" />
        <h2 className="mt-3 text-lg font-semibold">Super-admin access required</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Only the project owner can change global generation settings. Redirecting…
        </p>
      </Card>
    );
  }
  return <SettingsPage />;
}

export const Route = createFileRoute("/settings")({
  component: SuperAdminGuard,
});
