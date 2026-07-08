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

export default defineConfig({});
