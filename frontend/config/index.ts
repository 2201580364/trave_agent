import { defineConfig } from '@tarojs/cli'
import path from 'node:path'

export default defineConfig({
  projectName: 'travel-agent',
  date: '2026-08-25',
  designWidth: 375,
  deviceRatio: {
    375: 2,
    750: 1
  },
  sourceRoot: 'src',
  outputRoot: 'dist',
  framework: 'react',
  compiler: 'webpack5',
  alias: {
    '@': path.resolve(__dirname, '..', 'src')
  },
  cache: { enable: true },
  plugins: [],
  mini: {},
  h5: {
    publicPath: '/',
    staticDirectory: 'static',
    devServer: {
      port: 10086,
      proxy: {
        '/api': 'http://127.0.0.1:8000',
        '/health': 'http://127.0.0.1:8000'
      }
    }
  }
})
