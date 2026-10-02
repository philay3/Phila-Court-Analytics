import { defineConfig } from 'vitest/config';

/*
 * Ops test config (task STATIC-2a): the single jsdom project the relocated
 * OpsDashboard component test needs, mirroring the web workspace's jsdom
 * project (automatic JSX runtime, jest-dom matchers, per-test cleanup).
 */
export default defineConfig({
  esbuild: { jsx: 'automatic', jsxImportSource: 'react' },
  test: {
    environment: 'jsdom',
    include: ['app/**/*.test.tsx'],
    setupFiles: ['./test/setup.jsdom.ts'],
  },
});
