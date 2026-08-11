/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Explicit IPv4 bind — some environments resolve "localhost" to ::1
    // only, which then can't be reached via 127.0.0.1 (e.g. plain curl).
    host: '0.0.0.0',
    // Backend runs separately (uvicorn on :8000) — proxy /api so the SPA
    // can call same-origin paths in both dev and production.
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
    css: true,
  },
})
