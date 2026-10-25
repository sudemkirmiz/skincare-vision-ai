// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Sudem Kırmız
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { readdirSync, readFileSync } from 'node:fs'
import { defineConfig, type Plugin } from 'vite'
import { configDefaults } from 'vitest/config'

// Dev: the React app runs on :5173 and forwards /api to FastAPI on :8000.
// Prod: `npm run build` output (dist/) is served by FastAPI itself, same origin.
// Demo-only files (sample photo, recorded PDF and exports) are emitted to demo/ in the Pages build only,
// so they never ship with the real app.
const demoAssets = (): Plugin => ({
  name: 'demo-assets',
  apply: 'build',
  generateBundle() {
    const dir = 'src/demo/assets'
    for (const file of readdirSync(dir)) this.emitFile({ type: 'asset', fileName: `demo/${file}`, source: readFileSync(`${dir}/${file}`) })
  },
})

// The built page carries its own CSP too, so static hosting without response headers (the Pages demo) is covered.
// Build only: the dev server needs inline scripts for hot reload. frame-ancestors is header-only and set by FastAPI.
const CSP = "default-src 'self'; base-uri 'self'; object-src 'none'; form-action 'self'; script-src 'self'; " +
  "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; " +
  "worker-src 'self'; manifest-src 'self'; media-src 'self' blob:"
const metaCsp = (): Plugin => ({
  name: 'meta-csp',
  apply: 'build',
  transformIndexHtml: (html) => html.replace('<meta charset="UTF-8" />', `<meta charset="UTF-8" />
    <meta http-equiv="Content-Security-Policy" content="${CSP}" />`),
})

export default defineConfig(({ mode }) => ({
  // The GitHub Pages demo lives under /<repo>/ (VITE_BASE); the real app is always served at the root.
  base: process.env.VITE_BASE ?? '/',
  plugins: [react(), tailwindcss(), metaCsp(), ...(mode === 'demo' ? [demoAssets()] : [])],
  server: {
    port: 5173,
    // API_TARGET lets e2e/screenshot runs use a throwaway backend instead of the real database.
    proxy: { '/api': process.env.API_TARGET ?? 'http://127.0.0.1:8000' },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
    exclude: [...configDefaults.exclude, 'e2e/**'],
    css: false,
  },
}))
