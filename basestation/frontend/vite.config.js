import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
import { fileURLToPath } from "url";

const rootDir = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/ws": { target: "ws://127.0.0.1:8000", ws: true },
      "/health": "http://127.0.0.1:8000",
    },
  },
  build: {
    outDir: "../server/static",
    emptyOutDir: true,
  },
  resolve: {
    alias: {
      components: path.resolve(rootDir, "src/components"),
      context: path.resolve(rootDir, "src/context"),
      pages: path.resolve(rootDir, "src/pages"),
      assets: path.resolve(rootDir, "src/assets"),
      styles: path.resolve(rootDir, "src/styles"),
      utils: path.resolve(rootDir, "src/utils"),
      hooks: path.resolve(rootDir, "src/hooks"),
    },
  },
});
