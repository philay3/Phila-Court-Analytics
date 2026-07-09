import { defineConfig } from 'vitest/config';

export default defineConfig({
  // Resolve workspace packages (@pca/*) to their TypeScript source via the
  // custom `pca-source` export condition rather than the built `dist/` output,
  // so tests run against source with no build step. The condition is namespaced
  // (not `development`) so it never collides with the `development` condition
  // Next.js injects in dev — see the exports maps. `inline` forces Vite to
  // process the symlinked workspace deps instead of externalizing them to
  // Node's native resolver (which would ignore this condition and load dist).
  resolve: { conditions: ['pca-source'] },
  ssr: { resolve: { conditions: ['pca-source', 'module', 'node'] } },
  test: {
    setupFiles: ['./src/test-support/setup.ts'],
    server: { deps: { inline: [/@pca\//] } },
  },
});
