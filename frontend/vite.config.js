import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const BACKEND = 'http://localhost:8000'

// In dev, /api is proxied to the Flask/uvicorn backend. In production set VITE_API_URL at build time.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: BACKEND,
        // When the backend is down, answer with a clear JSON error instead of Vite's empty 500.
        configure: (proxy) => {
          proxy.on('error', (_err, _req, res) => {
            if (res.headersSent || typeof res.writeHead !== 'function') return
            res.writeHead(502, { 'Content-Type': 'application/json' })
            res.end(JSON.stringify({ error: `The backend is not running. Start it with: cd backend; .\\.venv\\Scripts\\python -m uvicorn app.asgi:application --port 8000 (expected at ${BACKEND}).` }))
          })
        },
      },
    },
  },
})
