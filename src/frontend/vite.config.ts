import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, import.meta.dirname, "VITE_");
  return {
    plugins: [react()],
    server: {
      port: Number(env.VITE_DEV_PORT ?? 3000),
      strictPort: true,
      // Same origin for the page and /api, as in the Docker setup.
      proxy: { "/api": env.VITE_API_URL ?? "http://localhost:8010" },
    },
  };
});
