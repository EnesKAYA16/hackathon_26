import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev sunucusu /api isteklerini FastAPI backend'ine (8000) proxy'ler.
// Böylece CORS derdi olmadan, port'u tek yerden değiştirerek çalışılır.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ''),
      },
    },
  },
})
