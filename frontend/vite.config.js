import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
    plugins: [react()],
    server: {
        port: 5173,
        // Temporary tunnels use a generated public hostname during local demos.
        allowedHosts: true,
        proxy: {
            "/ui/api": {
                target: "http://127.0.0.1:8001",
                changeOrigin: true,
            },
        },
    },
});
