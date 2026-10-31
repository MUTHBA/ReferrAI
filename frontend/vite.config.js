// -----------------------------------------------------------------------------
// frontend/vite.config.js
//
// Vite config for the ReferrAI frontend: React + Tailwind CSS v4 (via the
// @tailwindcss/vite plugin) and the "@/..." import alias for src/.
// The dev server binds to 0.0.0.0:3000 for Docker; usePolling keeps hot reload
// working across Windows/macOS bind-mounts. /api and /r are proxied to the
// backend so the browser sees one origin (no CORS). The proxy target defaults
// to the Docker Compose service name; set VITE_PROXY_TARGET=http://localhost:8000
// when running the backend outside Docker.
// -----------------------------------------------------------------------------

import path from 'node:path'
import { fileURLToPath } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import process from 'node:process'

import { defineConfig, loadEnv } from 'vite'

const dirname = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const target = env.VITE_PROXY_TARGET || 'http://backend:8000'
  return {
    plugins: [react(), tailwindcss()],
    resolve: { alias: { '@': path.resolve(dirname, 'src') } },
    server: {
      host: '0.0.0.0',
      port: 3000,
      watch: { usePolling: true },
      // Reached through the nginx container (Host: frontend / your domain) in Docker.
      allowedHosts: true,
      proxy: {
        '/api': { target, changeOrigin: true },
        '/r/': { target, changeOrigin: true },
      },
    },
  }
})
