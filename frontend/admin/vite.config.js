import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3003,
    proxy: {
      '/api/v1/admin': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      }
    }
  }
})
