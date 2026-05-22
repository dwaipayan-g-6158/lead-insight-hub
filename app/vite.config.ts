import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tsconfigPaths from "vite-tsconfig-paths";
import { TanStackRouterVite } from "@tanstack/router-plugin/vite";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  base: "/app/",
  plugins: [
    TanStackRouterVite({ target: "react", autoCodeSplitting: true }),
    react(),
    tsconfigPaths(),
    tailwindcss(),
  ],
  server: {
    port: 5173,
    proxy: {
      "/server": "http://localhost:3000",
      "/__catalyst": "http://localhost:3000",
    },
  },
  build: {
    target: "es2022",
    outDir: "dist",
    sourcemap: false,
  },
});
