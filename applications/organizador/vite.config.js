import { defineConfig } from 'vite';
import { fileURLToPath } from 'node:url';
import { notesIntegration } from './scripts/notes-integration.mjs';

const root = fileURLToPath(new URL('.', import.meta.url));
export default defineConfig({
  plugins: [notesIntegration(root)],
  server: { fs: { strict: true } },
  build: { target: 'es2022', sourcemap: false },
});
