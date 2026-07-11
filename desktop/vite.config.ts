import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: { host: '127.0.0.1', port: 5173 },
  build: {
    outDir: 'dist',
    rollupOptions: {
      output: {
        // Rolldown (Vite 8) accepts the function form only. Keep heavyweight
        // libraries out of the lazy-page entry chunk for a stable bundle budget.
        manualChunks(id) {
          if (id.includes('/node_modules/echarts/')) return 'echarts-vendor'
          if (id.includes('/node_modules/lucide-vue-next/')) return 'icon-vendor'
          if (id.includes('/node_modules/vue/') || id.includes('/node_modules/vue-router/') || id.includes('/node_modules/pinia/')) return 'vue-vendor'
          return undefined
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.ts'],
    restoreMocks: true,
    clearMocks: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'lcov'],
      reportsDirectory: './coverage',
      include: [
        'src/api/websocket.ts',
        'src/stores/can.ts',
        'src/stores/signals.ts',
        'src/components/charts/*.vue',
      ],
      thresholds: {
        // Enforced phase-five baseline. This is raised as page suites are
        // expanded, but regressions below the exercised runtime surface fail.
        lines: 45,
        functions: 45,
        branches: 45,
        statements: 45,
      },
    },
  },
})
