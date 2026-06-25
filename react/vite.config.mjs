import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  base: './',
  plugins: [react()],
  publicDir: 'public',
  build: {
    outDir: 'build',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) {
            return undefined;
          }
          if (id.includes('/d3') || id.includes('d3-')) {
            return 'vendor-d3';
          }
          if (id.includes('@nivo')) {
            return 'vendor-nivo';
          }
          if (id.includes('primereact') || id.includes('primeicons') || id.includes('primeflex')) {
            return 'vendor-prime';
          }
          if (id.includes('react-router')) {
            return 'vendor-router';
          }
          if (id.includes('react-dom') || id.includes('/react/')) {
            return 'vendor-react';
          }
          return 'vendor';
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    css: true,
    setupFiles: './src/setupTests.js',
  },
});
