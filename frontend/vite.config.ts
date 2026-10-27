import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Máy thứ hai có thể chạy Vite riêng và trỏ API về máy chủ backend:
//   $env:VITE_PROXY_TARGET = "http://192.168.8.104:8000"; npm run dev
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const proxyTarget = env.VITE_PROXY_TARGET || 'http://localhost:8000'
  const port = Number(env.VITE_PORT || 5173)

  return {
    plugins: [react(), tailwindcss()],
    server: {
      // host: true -> máy khác trong LAN mở được http://<ip-lan>:5173
      host: true,
      port,
      strictPort: true,
      proxy: {
        // Nhờ proxy này, frontend luôn gọi đường dẫn tương đối /api/... và
        // hoạt động dù mở bằng localhost hay bằng IP LAN.
        '/api': { target: proxyTarget, changeOrigin: true },
      },
    },
  }
})
