import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In development, /api/* is forwarded to the FastAPI app on localhost:8000
// (uvicorn locally, or `kubectl port-forward svc/csv-records-api 8000:80`).
// In Kubernetes, nginx does the same job (see nginx/default.conf.template).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.API_TARGET || 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  test: {
    environment: 'node',
  },
})
