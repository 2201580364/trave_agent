import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': 'http://127.0.0.1:8001',
      '/health': 'http://127.0.0.1:8001',
    },
  },
  preview: {
    port: 4173,
    strictPort: true,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    restoreMocks: true,
    setupFiles: ['./src/test/setup.ts'],
    // Windows 本机 jsdom + AntD 组件测试在多 worker 并行下资源争抢，
    // 5s 超时偶发误报（每轮失败用例不同，单线程重跑全过）。
    // 调大单用例超时并限制文件并发，代价是总时长略增，稳定性优先。
    testTimeout: 15_000,
    hookTimeout: 15_000,
    fileParallelism: 2,
  },
})
