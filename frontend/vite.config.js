// -----------------------------------------------------------------------------
// frontend/vite.config.js
//
// Vite dev server configuration for the ReferrAI frontend. Binds to 0.0.0.0
// so Docker can reach it from outside the container. watch.usePolling is required
// for hot-reload (HMR) to work across Docker bind-mounts on Windows and macOS —
// inotify/FSEvents don't cross the host-container boundary, so Vite must poll.
// The /api proxy forwards API requests to the backend service using the Docker
// Compose hostname, making all requests same-origin from the browser's perspective
// and eliminating CORS issues during development.
// -----------------------------------------------------------------------------

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    // usePolling is required for hot-reload to work on Docker bind-mounts on
    // Windows / macOS where inotify events don't cross the host-container boundary.
    watch: { usePolling: true },
    proxy: {
      '/api': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
    },
  },
})
