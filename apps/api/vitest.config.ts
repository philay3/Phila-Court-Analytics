import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

import { defineConfig } from 'vitest/config';

// Mirror the db package's convention: load the root .env (when present) so
// DB-backed tests can reach the local database. Variables already exported in
// the shell take precedence — loadEnvFile never overrides them.
try {
  process.loadEnvFile(path.join(path.dirname(fileURLToPath(import.meta.url)), '..', '..', '.env'));
} catch {
  // No root .env — DATABASE_URL may still come from the environment (e.g. CI).
}

export default defineConfig({
  // Resolve workspace packages (@pca/shared, @pca/db, @pca/taxonomy) to their
  // TypeScript source via the custom `pca-source` export condition rather than
  // built dist/, so tests (and the global setup, which imports @pca/db) run
  // against source with no package build step. The condition is namespaced (not
  // `development`) to avoid colliding with Next.js's dev condition. `inline`
  // forces Vite to process the symlinked workspace deps instead of externalizing
  // them to Node's native resolver (which would ignore this condition).
  resolve: { conditions: ['pca-source'] },
  ssr: { resolve: { conditions: ['pca-source', 'module', 'node'] } },
  test: {
    server: { deps: { inline: [/@pca\//] } },
    // Seeds reference + aggregate data once per run (when DATABASE_URL is
    // set) so DB-backed suites never self-seed — see vitest.global-setup.ts.
    globalSetup: './vitest.global-setup.ts',
  },
});
