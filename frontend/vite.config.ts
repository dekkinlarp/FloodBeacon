import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const proxy = {
    '/intake': {
      target: env.INTAKE_API_URL || 'http://127.0.0.1:8000',
      changeOrigin: false,
      rewrite: (path: string) => path.replace(/^\/intake/, ''),
    },
    '/api': { target: 'http://localhost:8787', changeOrigin: false },
  };
  return {
    plugins: [react()],
    worker: { format: 'es' },
    server: { proxy },
    preview: { proxy },
  };
});
