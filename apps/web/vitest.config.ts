import { defineConfig } from 'vitest/config';

/*
 * Web test config (task 12.2). Introduces the component-render setup without
 * disturbing the existing node-environment suites, using two Vitest projects
 * in one config:
 *
 *   - node   → the pre-existing tests (test/**, app/lib/**, and any *.test.ts
 *              under app/) run in the Node environment exactly as before, with
 *              no DOM setup.
 *   - jsdom  → component tests (*.test.tsx under app/components/) run in jsdom
 *              with @testing-library/jest-dom matchers and per-test cleanup.
 *
 * Deliberately NO `pca-source` resolve condition (unlike the shared/db/api
 * configs): the web workspace resolves @pca/* through built dist per the 11.1
 * standing decision, so `pnpm run build:packages` remains the prerequisite
 * before running these tests. The cross-package resolution knobs in those
 * other configs are untouched and keep working.
 */
export default defineConfig({
  // Component tests use JSX; compile it with React's automatic runtime so test
  // files need no `import React`. next dev/build use the same automatic runtime.
  esbuild: { jsx: 'automatic', jsxImportSource: 'react' },
  test: {
    projects: [
      {
        extends: true,
        test: {
          name: 'node',
          environment: 'node',
          include: ['test/**/*.test.ts', 'app/**/*.test.ts'],
        },
      },
      {
        extends: true,
        test: {
          name: 'jsdom',
          environment: 'jsdom',
          include: ['app/**/*.test.tsx'],
          setupFiles: ['./test/setup.jsdom.ts'],
        },
      },
    ],
  },
});
