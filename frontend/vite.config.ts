import { resolve } from "path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
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
      },
    },
  },
});
