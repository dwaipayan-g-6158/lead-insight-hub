import { createFileRoute } from "@tanstack/react-router";
import { SignUpPage } from "@/components/SignUpPage";

// /signup is rendered OUTSIDE the AuthGate — see app/src/components/AuthGate.tsx
// for the pathname-based bypass that swaps LoginScreen → SignUpPage.
// This route file still has to exist so TanStack's file-based router
// resolves `/signup` to a real route entry (otherwise it 404s before the
// gate gets a chance to handle it).
export const Route = createFileRoute("/signup")({
  component: SignUpPage,
});
