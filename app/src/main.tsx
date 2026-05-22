import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider, createRouter, createHashHistory } from "@tanstack/react-router";
import { routeTree } from "./routeTree.gen";
import "./styles.css";

// Hash-based history so direct loads of `/app/index.html#/leads/...` work
// without requiring SPA-fallback config on Catalyst Web Client Hosting.
const router = createRouter({
  routeTree,
  defaultPreloadStaleTime: 0,
  scrollRestoration: true,
  history: createHashHistory(),
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

const rootEl = document.getElementById("root");
if (!rootEl) throw new Error("Root element not found");

createRoot(rootEl).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
