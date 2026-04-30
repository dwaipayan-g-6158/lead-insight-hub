import { createFileRoute } from "@tanstack/react-router";
import { AuthGate } from "@/components/AuthGate";
import { AppShell } from "@/components/AppShell";
import { UploadPage } from "@/components/UploadPage";

export const Route = createFileRoute("/upload")({
  component: () => (
    <AuthGate>
      <AppShell>
        <UploadPage />
      </AppShell>
    </AuthGate>
  ),
});