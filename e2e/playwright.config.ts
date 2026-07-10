import { defineConfig, devices } from '@playwright/test';
import { API_HEALTH_URL, API_PORT, WEB_BASE_URL, WEB_PORT } from './support/constants';

/**
 * Sprint 3 end-to-end suite (task 15.2). One chromium project walks every
 * public flow against a REAL seeded database, the API booted from built output
 * under plain node, and the web app booted from a production build — the same
 * shapes that run in production. Firefox/WebKit are intentionally omitted
 * (task Out-of-scope) to protect the CI time budget.
 *
 * The suite does NOT provision the database. Prerequisites (documented in
 * e2e/README.md and the root README): a Postgres reachable via DATABASE_URL,
 * migrations applied, and a real `pnpm db:seed` run. `webServer` only STARTS
 * the already-built API and web servers; the build steps happen first (the
 * root `pnpm test:e2e` script locally, explicit CI steps in the workflow).
 */

const isCI = !!process.env.CI;

export default defineConfig({
  testDir: './tests',
  // No hidden .only in CI, and no silent flake-masking retries anywhere: a
  // failed assertion is a real regression, surfaced loudly (10.1 precedent).
  forbidOnly: isCI,
  retries: 0,
  fullyParallel: false,
  reporter: isCI ? [['github'], ['list']] : [['list']],
  use: {
    baseURL: WEB_BASE_URL,
    trace: 'on-first-retry',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      // API from BUILT output under plain node (11.1 `start` path). DATABASE_URL
      // is inherited from the environment (local .env via the start script's
      // --env-file-if-exists, or the CI job env) — no DB port is hardcoded here.
      command: 'pnpm --filter @pca/api run start',
      url: API_HEALTH_URL,
      env: { PORT: String(API_PORT), HOST: '127.0.0.1' },
      reuseExistingServer: !isCI,
      timeout: 120_000,
      stdout: 'pipe',
      stderr: 'pipe',
    },
    {
      // Web from a PRODUCTION build (`next build` then `next start`). API_BASE_URL
      // is set explicitly rather than relying on the 15.1 localhost default, so
      // both the server-side client and the next.config rewrite reach the API.
      command: 'pnpm --filter @pca/web run start',
      url: WEB_BASE_URL,
      env: { PORT: String(WEB_PORT), API_BASE_URL: `http://127.0.0.1:${API_PORT}` },
      reuseExistingServer: !isCI,
      timeout: 120_000,
      stdout: 'pipe',
      stderr: 'pipe',
    },
  ],
});
