import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

import { defineConfig } from 'vitest/config';

// Mirror the package scripts' `--env-file-if-exists=../.env`: load the root
// .env (when present) so tests can reach the local database. Variables
// already exported in the shell take precedence — loadEnvFile never
// overrides them.
try {
  process.loadEnvFile(path.join(path.dirname(fileURLToPath(import.meta.url)), '..', '.env'));
} catch {
  // No root .env — DATABASE_URL may still come from the environment (e.g. CI).
}

// Resolve workspace packages (@pca/taxonomy) to TypeScript source via the
// custom `pca-source` export condition rather than built dist/, so tests need
// no package build step. The condition is namespaced (not `development`) to
// avoid colliding with Next.js's dev condition. `inline` forces Vite to process
// the symlinked workspace deps instead of externalizing them to Node's resolver.
export default defineConfig({
  resolve: { conditions: ['pca-source'] },
  ssr: { resolve: { conditions: ['pca-source', 'module', 'node'] } },
  test: {
    server: { deps: { inline: [/@pca\//] } },
    // Test-database guard (task 29.2): refuses a non-test DATABASE_URL before
    // any suite runs — see vitest.global-setup.ts.
    globalSetup: './vitest.global-setup.ts',
    // DB-backed suites share one database and create scratch databases on the
    // same server; running test files sequentially is a DELIBERATE race fix
    // (task 29.2, D-A ruling) — never casually revert it. (H-30.0 moved the
    // reference suite's exact-equality assertions into their own scratch
    // database; sequential files remain the standing decision.)
    fileParallelism: false,
  },
});
