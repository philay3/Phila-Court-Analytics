import { defineConfig, devices } from '@playwright/test';
import { WEB_BASE_URL, WEB_PORT } from './support/constants';

/**
 * End-to-end suite (task 15.2; static since task STATIC-2b). One chromium
 * project walks every public flow against the STATIC EXPORT — built from a
 * seeded database by `pnpm build:static -- --mode ci` — served locally with
 * Cloudflare Pages semantics by `wrangler pages dev` (so `_headers`,
 * `_redirects`, `name.html` resolution, and the root 404 behave as in
 * production). No API server and no `next start` run during the suite: the
 * build script already consumed the API in-process. Firefox/WebKit are
 * intentionally omitted to protect the CI time budget.
 *
 * The suite does NOT provision the database or build the export. Prerequisites
 * (documented in e2e/README.md): a seeded test database reachable via
 * DATABASE_URL, and the export at apps/web/out (the root `pnpm test:e2e`
 * script builds it first; the CI workflow has explicit steps).
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
  webServer: {
    // Pages semantics for the export (STATIC-2b pin 14), served from this
    // directory's sibling apps/web/out. The port comes from E2E_WEB_PORT
    // (default 3000) through the shared constants. Log level warn: the
    // per-request info lines would otherwise interleave with the reporter.
    command: `pnpm exec wrangler pages dev ../apps/web/out --ip 127.0.0.1 --port ${WEB_PORT} --compatibility-date=2026-01-01 --log-level=warn`,
    url: WEB_BASE_URL,
    env: { WRANGLER_SEND_METRICS: 'false' },
    reuseExistingServer: !isCI,
    timeout: 120_000,
    stdout: 'pipe',
    stderr: 'pipe',
  },
});
