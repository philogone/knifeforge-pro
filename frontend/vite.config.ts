import { fileURLToPath, URL } from "node:url";

import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
      // paper-full bundles acorn for PaperScript (unused), which calls `new Function` at load:
      // the Content-Security-Policy forbids eval, so the editor would not start. Same API, no parser.
      paper: "paper/dist/paper-core.js",
    },
  },
  server: {
    host: true,
    port: 5173,
    // dev only: in production nginx forwards /api to the backend
    proxy: { "/api": { target: process.env.VITE_PROXY_TARGET ?? "http://localhost:8000", changeOrigin: true } },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/editor/__tests__/setup.ts"],
    include: ["src/**/*.test.ts"],
  },
});
