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
    setupFiles: ['./src/test-setup.ts'],
    // Reported, not enforced. A threshold here would say a number was agreed; what COVERAGE.md
    // needs is a number somebody can reproduce, next to an honest account of what it misses.
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}'],
      // A test file covering itself, and the setup that only exists to make the others run.
      exclude: ['src/**/*.test.{ts,tsx}', 'src/test-setup.ts'],
      reporter: ['text'],
    },
  },
});
