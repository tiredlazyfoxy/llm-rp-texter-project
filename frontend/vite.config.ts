import fs from "fs";
import { resolve } from "path";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

/**
 * Rewrite sub-routes of multi-page SPAs to their respective index.html.
 * Without this, Vite dev server returns 404 for paths like /admin/llm-servers
 * because there is no matching file on disk.
 */
function spaFallback(): Plugin {
  return {
    name: "spa-fallback",
    configureServer(server) {
      server.middlewares.use((req, _res, next) => {
        const url = req.url ?? "";
        // Skip API, source files, and asset requests
        if (url.startsWith("/api") || url.startsWith("/src") || url.startsWith("/@") || url.startsWith("/node_modules") || url.includes(".")) {
          return next();
        }
        // Route to the correct SPA entry point
        if (url.startsWith("/admin")) {
          req.url = "/admin/index.html";
        } else if (url.startsWith("/login")) {
          req.url = "/login/index.html";
        } else {
          req.url = "/index.html";
        }
        next();
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), spaFallback()],
  appType: "mpa",
  server: {
    port: 8094,
    proxy: {
      "/api": "http://localhost:8085",
    },
  },
  build: {
    rollupOptions: {
      input: {
        user: resolve(__dirname, "index.html"),
        admin: resolve(__dirname, "admin/index.html"),
        login: resolve(__dirname, "login/index.html"),
      },
    },
  },
});
