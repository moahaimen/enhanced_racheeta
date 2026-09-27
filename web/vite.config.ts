/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const BACKEND = process.env.VITE_DEV_PROXY_TARGET ?? 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Share the single repository-root .env with the backend.
  envDir: '..',
  server: {
    port: 5173,
    // Same-origin API calls in development; no CORS needed when
    // VITE_API_BASE_URL is empty.
    proxy: {
      '/api': BACKEND,
      '/health': BACKEND,
    },
  },
  build: {
    sourcemap: false,
    outDir: 'dist',
  },
  test: {
    environment: 'jsdom',
    // Tests must not depend on the developer's .env.
    env: { VITE_API_BASE_URL: '' },
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    // Full-page tests render 20-row lists in jsdom; the default 5s trips on a loaded
    // machine with one worker per core. A timeout is not an assertion.
    testTimeout: 20000,
  },
})
