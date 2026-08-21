import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  // The automatic JSX runtime is set here rather than through a framework plugin: the component
  // tests need nothing else the plugin provides, and one fewer build dependency is one fewer
  // supply-chain surface for a project that handles other people's letters.
  oxc: { jsx: { runtime: 'automatic' } },
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}'],
  },
});
