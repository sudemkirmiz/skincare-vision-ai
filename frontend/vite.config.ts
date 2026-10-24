import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { configDefaults } from 'vitest/config'

// Dev: the React app runs on :5173 and forwards /api to FastAPI on :8000.
// Prod: `npm run build` output (dist/) is served by FastAPI itself, same origin.
export default defineConfig({
  plugins: [react(), tailwindcss()],
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
})
