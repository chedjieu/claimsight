import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/health": "http://localhost:8000",
      "/claims": "http://localhost:8000",
      "/demo": "http://localhost:8000",
      "/review-queue": "http://localhost:8000",
      "/audit": "http://localhost:8000",
      "/metrics": "http://localhost:8000",
      "/events": "http://localhost:8000",
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
});
