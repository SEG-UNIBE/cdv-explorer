import { execSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const reactDir = fileURLToPath(new URL('.', import.meta.url));
const repoRoot = resolve(reactDir, '..');
const { version } = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8'));

function getShortCommitSha() {
  try {
    return execSync('git rev-parse --short HEAD', {
      cwd: repoRoot,
      stdio: ['ignore', 'pipe', 'ignore'],
    }).toString().trim();
  } catch {
    return 'unknown';
  }
}

function getFullCommitSha() {
  try {
    return execSync('git rev-parse HEAD', {
      cwd: repoRoot,
      stdio: ['ignore', 'pipe', 'ignore'],
    }).toString().trim();
  } catch {
    return 'unknown';
  }
}

export default defineConfig({
  base: './',
  plugins: [react()],
  publicDir: 'public',
  define: {
    'import.meta.env.VITE_APP_VERSION': JSON.stringify(version),
    'import.meta.env.VITE_APP_COMMIT_SHA': JSON.stringify(getShortCommitSha()),
    'import.meta.env.VITE_APP_COMMIT_FULL_SHA': JSON.stringify(getFullCommitSha()),
  },
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
