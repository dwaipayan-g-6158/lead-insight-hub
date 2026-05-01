// Vite config wrapper for TanStack Start
// Provides: tanstackStart, viteReact, tailwindcss, tsConfigPaths, cloudflare (build-only),
// componentTagger (dev-only), VITE_* env injection, @ path alias, React/TanStack dedupe,
// error logger plugins, and sandbox detection (port/host/strictPort).
import { defineConfig } from "@lovable.dev/vite-tanstack-config";

export default defineConfig();
