import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";

const backendTarget = process.env.CHATKIT_API_BASE ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 8080,
    host: "0.0.0.0",
    proxy: {
      "/chatkit": {
        target: backendTarget,
        changeOrigin: true,
      },
      "/checkout": {
        target: backendTarget,
        changeOrigin: true,
      },
      "/wallet": {
        target: backendTarget,
        changeOrigin: true,
      },
    },
  },
});
