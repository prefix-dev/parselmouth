import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "/parselmouth/",
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api/r2": {
        target: "https://conda-mapping.prefix.dev",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/r2/, ""),
      },
      "/api/gh": {
        target: "https://raw.githubusercontent.com",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/gh/, ""),
      },
    },
  },
});
