import { Kysely, PostgresDialect } from 'kysely';
import pg from 'pg';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { TAXONOMY_VERSION } from '@pca/taxonomy';
import {
  DATA_COVERAGE_COURT_SCOPE,
  DATA_COVERAGE_JURISDICTION,
  DATA_COVERAGE_PLANNED_DATA_START,
  DATA_COVERAGE_UNAVAILABLE_MESSAGE,
  type DataCoverageResponse,
} from '@pca/shared';
import { buildApp } from '../../app.js';
import type { PublicApiDatabase } from '../../db.js';
import { DATA_COVERAGE_KNOWN_LIMITATIONS } from '../../content/data-coverage.js';

const COVERAGE_URL = '/api/v1/public/data-coverage';

// Requires the local database: `pnpm db:up`, migrations applied
// (`pnpm db:migrate:latest`), and DATABASE_URL (root .env is auto-loaded via
// vitest.config.ts). Reference and aggregate seeding happens once for the
// whole run in vitest.global-setup.ts — this suite must not self-seed.
const hasDb = Boolean(process.env.DATABASE_URL);
if (!hasDb) {
  console.warn(
    'DATABASE_URL not set — skipping data-coverage DB tests. ' +
      'Start Postgres (pnpm db:up), apply migrations (pnpm db:migrate:latest), ' +
      'and create the root .env (cp .env.example .env).',
  );
}

// Endpoint-local public-safety guard (the exhaustive suite is task 10.1).
// Covers the task's MUST NOT list: source documents, dockets, defendants,
// raw/extracted text, storage keys, parser detail, review status, internal
// run states, and invalidation reasons.
const FORBIDDEN_SUBSTRINGS = [
  'defendant',
  'docket',
  'source',
  'storage',
  '"raw',
  'extracted',
  'parsed',
  'fact',
  'review',
  'confidence',
  'parser',
  'invalidat',
];

// Every key either arm may ever contain; the recursive sweep fails on
// anything else (forbidden-field assertion at the structural level).
const ALLOWED_KEYS = new Set([
  'jurisdiction',
  'courtScope',
  'plannedDataStart',
  'knownLimitations',
  'coverage',
  'available',
  'dataStart',
  'dataEnd',
  'lastRefreshed',
  'taxonomyVersion',
  'aggregateRunId',
  'counts',
  'chargesWithOutcomeAggregates',
  'chargesWithSentencingAggregates',
  'judgeChargePairs',
  'message',
]);

// Word-boundary forbidden-term regexes (9.1 pattern). Coverage copy carries
// no guarded disclaimer phrases, so nothing is stripped first.
const FORBIDDEN_TERM_PATTERNS = [
  /\bpredict(?:s|ed|ion|ions|ive)?\b/i,
  /\bodds\b/i,
  /\blikelihood\b/i,
  /\bprobabilit(?:y|ies)\b/i,
  /\bchances?\b/i,
  /\brank(?:s|ed|ing|ings)?\b/i,
  /\bbest\b/i,
  /\bworst\b/i,
  /\brecommend(?:s|ed|ation|ations)?\b/i,
  /\badvice\b/i,
  /\bguarantee(?:s|d)?\b/i,
  /\bwin(?:s|ning)?\b/i,
  /\blos(?:e|es|ing)\b/i,
];

interface InjectedResponse {
  statusCode: number;
  body: string;
  json: <T>() => T;
}

function expectPublicSafeBody(res: InjectedResponse) {
  const lowered = res.body.toLowerCase();
  for (const forbidden of FORBIDDEN_SUBSTRINGS) {
    expect(lowered, `forbidden content: ${forbidden}`).not.toContain(forbidden);
  }
  for (const pattern of FORBIDDEN_TERM_PATTERNS) {
    expect(res.body).not.toMatch(pattern);
  }
  expectOnlyAllowedKeys(res.json<Record<string, unknown>>());
}

function expectOnlyAllowedKeys(value: unknown): void {
  if (Array.isArray(value)) {
    for (const item of value) {
      expectOnlyAllowedKeys(item);
    }
    return;
  }
  if (value !== null && typeof value === 'object') {
    for (const [key, nested] of Object.entries(value)) {
      expect(ALLOWED_KEYS.has(key), `unexpected response key: ${key}`).toBe(true);
      expectOnlyAllowedKeys(nested);
    }
  }
}

function expectCommonFields(body: DataCoverageResponse) {
  expect(Object.keys(body).sort()).toEqual([
    'courtScope',
    'coverage',
    'jurisdiction',
    'knownLimitations',
    'plannedDataStart',
  ]);
  expect(body.jurisdiction).toBe(DATA_COVERAGE_JURISDICTION);
  expect(body.courtScope).toBe(DATA_COVERAGE_COURT_SCOPE);
  expect(body.plannedDataStart).toBe(DATA_COVERAGE_PLANNED_DATA_START);
  expect(body.knownLimitations).toEqual(DATA_COVERAGE_KNOWN_LIMITATIONS);
  // Task 28.2: real aggregates replaced the seeds, so the Sprint 2
  // seeded-demonstration-data disclosure must be GONE — serving it against a
  // published real run would be false.
  expect(body.knownLimitations.join(' ')).not.toMatch(/seeded demonstration data/i);
  expect(body.knownLimitations.join(' ')).not.toMatch(/do not describe real/i);
  // The real-run limitations state that collection is ongoing.
  expect(body.knownLimitations.join(' ')).toMatch(/collection is ongoing/i);
}

// Expected values are restated by hand from db/seeds/aggregate-data.ts — an
// independent copy, so a drift in either side fails here. Counts: 5 charges
// with outcome aggregates (retail-theft, simple-assault,
// dui-general-impairment, possession-controlled-substance,
// criminal-trespass), 3 with sentencing (possession and trespass are the
// deliberate sentencing-unavailable fixtures), 3 judge/charge pairs
// (testina×retail-theft, samuel×dui, testina×simple-assault).
const SEED_PUBLISHED_RUN = {
  id: '5eedda7a-0000-4000-8000-000000000001',
  dataStart: '2025-01-01',
  dataEnd: '2026-06-30',
  publishedAt: '2026-07-01T02:00:00.000Z',
};
const EXPECTED_COUNTS = {
  chargesWithOutcomeAggregates: 5,
  chargesWithSentencingAggregates: 3,
  judgeChargePairs: 3,
};

describe.skipIf(!hasDb)('GET /data-coverage against the seeded database', () => {
  let setupDb: Kysely<PublicApiDatabase>;
  let app: ReturnType<typeof buildApp>;

  beforeAll(async () => {
    // Typed as the public Pick: the only table this suite touches is
    // analytics.aggregate_runs, and the handle doubles as the injected DB
    // for the transaction-isolated test below.
    setupDb = new Kysely<PublicApiDatabase>({
      dialect: new PostgresDialect({
        pool: new pg.Pool({ connectionString: process.env.DATABASE_URL }),
      }),
    });
    app = buildApp({ logger: false });
    await app.ready();
  });

  afterAll(async () => {
    await app?.close();
    await setupDb?.destroy();
  });

  async function getCoverage() {
    const res = await app.inject({ method: 'GET', url: COVERAGE_URL });
    expectPublicSafeBody(res);
    return res;
  }

  it('returns the available arm exactly as seeded', async () => {
    const res = await getCoverage();
    expect(res.statusCode).toBe(200);
    const body = res.json<DataCoverageResponse>();
    expectCommonFields(body);
    expect(body.coverage).toEqual({
      available: true,
      dataStart: SEED_PUBLISHED_RUN.dataStart,
      dataEnd: SEED_PUBLISHED_RUN.dataEnd,
      lastRefreshed: SEED_PUBLISHED_RUN.publishedAt,
      taxonomyVersion: TAXONOMY_VERSION,
      aggregateRunId: SEED_PUBLISHED_RUN.id,
      counts: EXPECTED_COUNTS,
    });
  });

  it('serves the run the active-published predicate resolves, independently of seed constants', async () => {
    const activeRun = await setupDb
      .selectFrom('analytics.aggregate_runs')
      .select('id')
      .where('published_at', 'is not', null)
      .where('invalidated_at', 'is', null)
      .executeTakeFirstOrThrow();
    const body = (await getCoverage()).json<DataCoverageResponse>();
    expect(body.coverage).toMatchObject({ available: true, aggregateRunId: activeRun.id });
  });

  it('returns 200 with the unavailable arm when no active published run exists', async () => {
    // Isolation (task requirement): the active run is invalidated inside an
    // uncommitted transaction, and the app under test is built on that
    // transaction connection. Other connections — and every other suite —
    // never observe the change; the rollback in finally guarantees the
    // shared seeded state survives even if an assertion throws.
    const trx = await setupDb.startTransaction().execute();
    try {
      await trx
        .updateTable('analytics.aggregate_runs')
        .set({
          invalidated_at: new Date(),
          // Both columns must move together (check constraint); never
          // committed, so no invalidation reason ever becomes visible.
          invalidated_reason: 'task 9.2 unavailable-arm test (rolled back)',
        })
        .where('published_at', 'is not', null)
        .where('invalidated_at', 'is', null)
        .execute();

      const trxApp = buildApp({ logger: false, db: trx });
      try {
        const res = await trxApp.inject({ method: 'GET', url: COVERAGE_URL });
        expectPublicSafeBody(res);
        expect(res.statusCode).toBe(200);
        const body = res.json<DataCoverageResponse>();
        expectCommonFields(body);
        expect(body.coverage).toEqual({
          available: false,
          message: DATA_COVERAGE_UNAVAILABLE_MESSAGE,
        });
      } finally {
        await trxApp.close();
      }
    } finally {
      await trx.rollback().execute();
    }

    // The shared seeded state is untouched: the main app still serves the
    // available arm after the rollback.
    const after = (await getCoverage()).json<DataCoverageResponse>();
    expect(after.coverage.available).toBe(true);
  });
});
