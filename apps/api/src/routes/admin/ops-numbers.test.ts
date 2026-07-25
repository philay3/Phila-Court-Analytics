import { afterAll, afterEach, describe, expect, it } from 'vitest';
import { buildApp } from '../../app.js';

/**
 * Phase 36 ops endpoint tests, against the seeded database (DATABASE_URL from
 * vitest.config; suites skip without it).
 *
 * The registration-time gate is the contract under test: with the flag off
 * the path 404s in the standard shape (no admin surface exists at all); with
 * it on, the payload carries every section, the published-run figures match
 * the seeds, and the identity checks pass over the seeded aggregates. The
 * parsed/fact/review layers are empty in this database, so the live sections
 * assert zero-shaped structure — presence and type, not corpus numbers.
 */

const hasDb = Boolean(process.env.DATABASE_URL);
const describeDb = hasDb ? describe : describe.skip;

const OPS_URL = '/api/v1/admin/ops/numbers';

function withEnv(vars: Record<string, string | undefined>, fn: () => void): void {
  const saved = new Map<string, string | undefined>();
  for (const [key, value] of Object.entries(vars)) {
    saved.set(key, process.env[key]);
    if (value === undefined) {
      delete process.env[key];
    } else {
      process.env[key] = value;
    }
  }
  try {
    fn();
  } finally {
    for (const [key, value] of saved) {
      if (value === undefined) {
        delete process.env[key];
      } else {
        process.env[key] = value;
      }
    }
  }
}

describeDb('GET /api/v1/admin/ops/numbers', () => {
  const apps: Array<ReturnType<typeof buildApp>> = [];

  function build(env: Record<string, string | undefined>): ReturnType<typeof buildApp> {
    let app: ReturnType<typeof buildApp> | undefined;
    withEnv(env, () => {
      app = buildApp({ logger: false });
    });
    if (!app) throw new Error('buildApp did not construct');
    apps.push(app);
    return app;
  }

  afterAll(async () => {
    await Promise.all(apps.map((app) => app.close()));
  });

  it('does not exist at all when ADMIN_OPS_ENABLED is unset (the deployed posture)', async () => {
    const app = build({ ADMIN_OPS_ENABLED: undefined, ADMIN_OPS_TOKEN: undefined });
    const res = await app.inject({ method: 'GET', url: OPS_URL });
    expect(res.statusCode).toBe(404);
    expect(res.json().code).toBe('NOT_FOUND');
  });

  it('requires the token when ADMIN_OPS_TOKEN is set', async () => {
    const app = build({ ADMIN_OPS_ENABLED: '1', ADMIN_OPS_TOKEN: 'test-ops-token' });
    const missing = await app.inject({ method: 'GET', url: OPS_URL });
    expect(missing.statusCode).toBe(401);
    const wrong = await app.inject({
      method: 'GET',
      url: OPS_URL,
      headers: { 'x-admin-ops-token': 'nope' },
    });
    expect(wrong.statusCode).toBe(401);
    const right = await app.inject({
      method: 'GET',
      url: OPS_URL,
      headers: { 'x-admin-ops-token': 'test-ops-token' },
    });
    expect(right.statusCode).toBe(200);
  });

  it('serves every section with the seeded published-run figures and passing checks', async () => {
    const app = build({ ADMIN_OPS_ENABLED: '1', ADMIN_OPS_TOKEN: undefined });
    const res = await app.inject({ method: 'GET', url: OPS_URL });
    expect(res.statusCode).toBe(200);
    const body = res.json();

    // Meta + timing surface (the dashboard's own refresh-rate display).
    expect(typeof body.generatedAt).toBe('string');
    expect(typeof body.totalMs).toBe('number');
    expect(Object.keys(body.timings).length).toBeGreaterThanOrEqual(10);

    // Every section is present.
    for (const key of [
      'corpus',
      'sourceDocuments',
      'linkage',
      'factBuilds',
      'aggregateRuns',
      'outcomes',
      'charges',
      'judges',
      'reviewQueue',
      'warnings',
      'checks',
    ]) {
      expect(body[key], key).toBeDefined();
    }

    // Published-run sections match the seeds.
    expect(body.aggregateRuns.activePublishedRunId).toBeTruthy();
    expect(body.aggregateRuns.rowsByTable.charge_volume_aggregates).toBe(6);
    expect(body.charges.withVolumeRows).toBe(6);
    expect(body.charges.volumeTotals).toMatchObject({
      chargesSeen: 3100 + 2050 + 3900 + 2450 + 61 + 37,
      outcomesRecorded: 1200 + 800 + 1500 + 950 + 18 + 0,
    });
    const retail = body.charges.topByVolume.find(
      (row: { slug: string }) => row.slug === 'retail-theft',
    );
    expect(retail).toMatchObject({ chargesSeen: 3100, outcomesRecorded: 1200 });
    expect(body.outcomes.published.totalRecords).toBeGreaterThan(0);
    expect(body.outcomes.published.dismissedOrWithdrawnShare).not.toBeNull();

    // The live layers are empty in this database: structure over magnitude.
    expect(body.corpus.dockets).toBe(0);
    expect(body.reviewQueue.total).toBe(0);

    // Every identity check over the seeded aggregates passes.
    const failing = body.checks.filter((check: { pass: boolean }) => !check.pass);
    expect(failing).toEqual([]);
  });

  afterEach(() => {
    // withEnv restored the environment inside build(); nothing global leaks.
  });
});
