import { defineConfig } from 'vite';

// Builds the API server and seed script for Node (see server/). The browser app
// uses vite.config.ts.
export default defineConfig({
  build: {
    ssr: true,
    target: 'node22',
    outDir: 'build/server',
    emptyOutDir: true,
    rolldownOptions: {
      input: { index: 'server/index.ts', seed: 'server/seed.ts' },
      output: { entryFileNames: '[name].js' },
    },
  },
});
