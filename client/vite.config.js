import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"

// Same shape as the other Claude Code lab exercises so this runs in the
// workshop sandbox unchanged: port 3000, served under /dashboard/, and every
// backend call goes through the /api proxy (the browser cannot reach 8001).
export default defineConfig({
  plugins: [vue()],
  base: "/dashboard/",
  server: {
    port: 3000,
    allowedHosts: true,
    proxy: {
      "/api": {
        target: "http://localhost:8001",
        changeOrigin: true
      }
    }
  }
})
