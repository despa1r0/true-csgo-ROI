import { fileURLToPath, URL } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig(({ command, mode, isPreview }) => ({
  // A build can never contain diagnostics, regardless of NODE_ENV or .env flags.
  define: { __TRUE_ROI_DIAGNOSTICS__: command === "serve" && !isPreview && mode !== "production" },
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_PROXY_TARGET ?? "http://127.0.0.1:8005",
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: 4173,
  },
}));
