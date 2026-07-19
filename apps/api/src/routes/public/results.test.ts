import { Kysely, PostgresDialect } from 'kysely';
import pg from 'pg';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import {
  CHARGE_RESULT_UNAVAILABLE_MESSAGE,
  CHARGE_SENTENCING_UNAVAILABLE_MESSAGE,
  PUBLIC_ERROR_CODES,
} from '@pca/shared';
import type { Database } from '@pca/db';
import { buildApp } from '../../app.js';

const resultUrl = (chargeIdOrSlug: string) => `/api/v1/public/results/charge/${chargeIdOrSlug}`;

// Requires the local database: `pnpm db:up`, migrations applied
// (`pnpm db:migrate:latest`), and DATABASE_URL (root .env is auto-loaded via
// vitest.config.ts). Reference and aggregate seeding happens once for the
// whole run in vitest.global-setup.ts.
const hasDb = Boolean(process.env.DATABASE_URL);
if (!hasDb) {
  console.warn(
    'DATABASE_URL not set — skipping charge-result DB tests. ' +
      'Start Postgres (pnpm db:up), apply migrations (pnpm db:migrate:latest), ' +
      'and create the root .env (cp .env.example .env).',
  );
}

// Endpoint-local public-safety guard (the exhaustive suite is task 10.1).
// Substrings chosen to be impossible in legitimate response content: bare
// 'raw' would false-positive on "withdrawn", so raw* is caught as a JSON
// key/value prefix ('"raw') and by the allowed-key sweep.
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
];

interface InjectedResponse {
  statusCode: number;
  body: string;
  json: () => Record<string, unknown>;
}

function expectPublicSafeBody(res: InjectedResponse) {
  const lowered = res.body.toLowerCase();
  for (const forbidden of FORBIDDEN_SUBSTRINGS) {
    expect(lowered, `forbidden content: ${forbidden}`).not.toContain(forbidden);
  }
}

function expectExactErrorShape(body: Record<string, unknown>) {
  expect(Object.keys(body).sort()).toEqual(['code', 'error', 'message', 'requestId', 'statusCode']);
}

// Expected values are restated by hand from db/seeds/aggregate-data.ts and
// the taxonomy artifacts, in taxonomy sort order — an independent copy, so a
// drift in either side fails here.
const RETAIL_THEFT_OUTCOME_ROWS = [
  { categoryCode: 'dismissed', displayName: 'Dismissed', count: 264, percentage: 22 },
  { categoryCode: 'withdrawn', displayName: 'Withdrawn', count: 156, percentage: 13 },
  { categoryCode: 'guilty_plea', displayName: 'Guilty plea', count: 540, percentage: 45 },
  { categoryCode: 'guilty_verdict', displayName: 'Guilty verdict', count: 60, percentage: 5 },
  { categoryCode: 'acquittal', displayName: 'Acquittal', count: 36, percentage: 3 },
  { categoryCode: 'ard', displayName: 'ARD', count: 24, percentage: 2 },
  { categoryCode: 'diversion', displayName: 'Diversion', count: 108, percentage: 9 },
  { categoryCode: 'other', displayName: 'Other', count: 12, percentage: 1 },
];

const RETAIL_THEFT_SENTENCING_ROWS = [
  { categoryCode: 'probation', displayName: 'Probation', count: 245, percentage: 35 },
  { categoryCode: 'incarceration', displayName: 'Incarceration', count: 70, percentage: 10 },
  { categoryCode: 'fine', displayName: 'Fine', count: 161, percentage: 23 },
  { categoryCode: 'restitution', displayName: 'Restitution', count: 35, percentage: 5 },
  {
    categoryCode: 'community_service',
    displayName: 'Community service',
    count: 56,
    percentage: 8,
  },
  {
    categoryCode: 'no_further_penalty',
    displayName: 'No further penalty',
    count: 14,
    percentage: 2,
  },
  { categoryCode: 'costs_fees', displayName: 'Costs and fees', count: 119, percentage: 17 },
];

describe.skipIf(!hasDb)('GET /results/charge/:chargeIdOrSlug against the seeded database', () => {
  // Distinct prefix from the search suites ('zz-test-'): test files run in
  // parallel against the same database, and cleanup must never delete another
  // suite's temp rows.
  const TEMP_SLUG_PREFIX = 'zz-result-';
  // Fallthrough probe: an ACTIVE charge whose slug is UUID-shaped, with zero
  // aggregate rows. Requesting it must take the id path and 404 with
  // CHARGE_NOT_FOUND; slug fallthrough would resolve the charge and produce
  // CHARGE_RESULT_UNAVAILABLE instead. Tracked explicitly in cleanup — the
  // prefix delete cannot see it.
  const UUID_SHAPED_SLUG = '11111111-2222-4333-8444-555555555555';
  const TEMP_CHARGES = [
    { slug: UUID_SHAPED_SLUG, display_name: 'ZZ Result Fallthrough Probe', is_active: true },
    { slug: 'zz-result-inactive', display_name: 'ZZ Result Inactive Probe', is_active: false },
  ];

  let setupDb: Kysely<Database>;
  let app: ReturnType<typeof buildApp>;
  let retailTheftId: string;
  let harassmentId: string;
  let publishedRunId: string;

  // Neither temp charge has aggregate rows, so plain deletes are FK-safe.
  async function deleteTempRows() {
    await setupDb
      .deleteFrom('ref.normalized_charges')
      .where((eb) =>
        eb.or([eb('slug', 'like', `${TEMP_SLUG_PREFIX}%`), eb('slug', '=', UUID_SHAPED_SLUG)]),
      )
      .execute();
  }

  beforeAll(async () => {
    setupDb = new Kysely<Database>({
      dialect: new PostgresDialect({
        pool: new pg.Pool({ connectionString: process.env.DATABASE_URL }),
      }),
    });
    await deleteTempRows();
    await setupDb
      .insertInto('ref.normalized_charges')
      .values(TEMP_CHARGES.map((c) => ({ ...c, statute_code: null, grade: null })))
      .execute();

    retailTheftId = (
      await setupDb
        .selectFrom('ref.normalized_charges')
        .select('id')
        .where('slug', '=', 'retail-theft')
        .executeTakeFirstOrThrow()
    ).id;
    // Seeded charge-unavailable fixture (task 13.2a): active, real statute,
    // deliberately absent from every aggregate distribution.
    harassmentId = (
      await setupDb
        .selectFrom('ref.normalized_charges')
        .select('id')
        .where('slug', '=', 'harassment')
        .executeTakeFirstOrThrow()
    ).id;
    // The endpoint must serve exactly this run — resolved here by the same
    // active-published predicate, independently of the seed constants.
    publishedRunId = (
      await setupDb
        .selectFrom('analytics.aggregate_runs')
        .select('id')
        .where('published_at', 'is not', null)
        .where('invalidated_at', 'is', null)
        .executeTakeFirstOrThrow()
    ).id;

    app = buildApp({ logger: false });
    await app.ready();
  });

  afterAll(async () => {
    await app?.close();
    if (setupDb) {
      await deleteTempRows();
      await setupDb.destroy();
    }
  });

  // Every request in this suite goes through the public-safety guard.
  async function getResult(chargeIdOrSlug: string) {
    const res = await app.inject({ method: 'GET', url: resultUrl(chargeIdOrSlug) });
    expectPublicSafeBody(res);
    return res;
  }

  it('returns the full charge-only result by slug with all public metadata', async () => {
    const res = await getResult('retail-theft');
    expect(res.statusCode).toBe(200);
    const body = res.json();

    expect(body.charge).toEqual({
      id: retailTheftId,
      slug: 'retail-theft',
      displayName: 'Retail Theft',
      statuteCode: '18 § 3929',
      // grade is null in the reference seeds → omitted, per the shared convention.
    });
    expect(body.resultType).toBe('charge_only');
    expect(body.geography).toBe('philadelphia');
    expect(body.dateRange).toEqual({ start: '2025-01-01', end: '2026-06-30' });
    expect(String(body.dateRange.start) >= '2025-01-01').toBe(true);
    expect(body.lastRefreshed).toBe('2026-07-01T02:00:00.000Z');
    expect(body.taxonomyVersion).toBe('1.0.0');
    expect(body.aggregateRunId).toBe(publishedRunId);
    expect(body.links).toEqual({ methodology: '/methodology', definitions: '/definitions' });
  });

  it('serves seeded counts/percentages in taxonomy sort order, from the published run only', async () => {
    const res = await getResult('retail-theft');
    expect(res.statusCode).toBe(200);
    const body = res.json();

    expect(body.outcomes).toEqual({
      sampleSize: 1200,
      thinData: false,
      rows: RETAIL_THEFT_OUTCOME_ROWS,
    });
    expect(body.sentencing).toEqual({
      available: true,
      sampleSize: 700,
      thinData: false,
      rows: RETAIL_THEFT_SENTENCING_ROWS,
    });
    // Sentencing sample size is independent of (and here below) the outcome n.
    expect(body.sentencing.sampleSize).not.toBe(body.outcomes.sampleSize);
    // The unpublished decoy run stores retail-theft outcomes as uniform 9999s;
    // none of that may ever surface.
    expect(res.body).not.toContain('9999');
  });

  it('returns an identical body when the same charge is requested by UUID', async () => {
    const bySlug = await getResult('retail-theft');
    const byId = await getResult(retailTheftId);
    expect(byId.statusCode).toBe(200);
    expect(byId.json()).toEqual(bySlug.json());

    const byUpperId = await getResult(retailTheftId.toUpperCase());
    expect(byUpperId.statusCode).toBe(200);
    expect(byUpperId.json()).toEqual(bySlug.json());
  });

  it('flags the thin-data charge on the outcome distribution', async () => {
    const res = await getResult('criminal-trespass');
    expect(res.statusCode).toBe(200);
    const body = res.json();
    expect(body.outcomes).toMatchObject({ sampleSize: 18, thinData: true });
    expect((body.outcomes as { rows: unknown[] }).rows).toHaveLength(5);
  });

  it('returns the unavailable arm with the pinned message when sentencing is absent, outcomes intact', async () => {
    const res = await getResult('possession-controlled-substance');
    expect(res.statusCode).toBe(200);
    const body = res.json();
    expect(body.sentencing).toEqual({
      available: false,
      message: CHARGE_SENTENCING_UNAVAILABLE_MESSAGE,
    });
    expect(body.outcomes).toMatchObject({ sampleSize: 950, thinData: false });
    expect((body.outcomes as { rows: unknown[] }).rows).toHaveLength(7);
  });

  it('returns the HTTP-200 unavailable arm for a resolvable charge with zero aggregate rows', async () => {
    const res = await getResult('harassment');
    expect(res.statusCode).toBe(200);
    // Exact body: identity as served, the pinned code/message literals, and the
    // links — no distributions, sample sizes, or run metadata.
    expect(res.json()).toEqual({
      resultType: 'charge_only_unavailable',
      code: PUBLIC_ERROR_CODES.CHARGE_RESULT_UNAVAILABLE,
      message: CHARGE_RESULT_UNAVAILABLE_MESSAGE,
      charge: {
        id: harassmentId,
        slug: 'harassment',
        displayName: 'Harassment',
        statuteCode: '18 § 2709',
        // grade is null in the reference seeds → omitted, per the shared convention.
      },
      links: { methodology: '/methodology', definitions: '/definitions' },
    });
    // The message is the imported shared literal, never a re-typed string.
    expect(res.json().message).toBe(CHARGE_RESULT_UNAVAILABLE_MESSAGE);
  });

  it('serves the unavailable arm identically by UUID', async () => {
    const bySlug = await getResult('harassment');
    const byId = await getResult(harassmentId);
    expect(byId.statusCode).toBe(200);
    expect(byId.json()).toEqual(bySlug.json());
  });

  it('returns 404 CHARGE_NOT_FOUND for an unknown slug, in the flat catalog shape', async () => {
    const res = await getResult('no-such-charge');
    expect(res.statusCode).toBe(404);
    const body = res.json();
    expect(body).toMatchObject({ statusCode: 404, code: PUBLIC_ERROR_CODES.CHARGE_NOT_FOUND });
    expectExactErrorShape(body);
  });

  it('returns 404 CHARGE_NOT_FOUND for a UUID-shaped param not in the database', async () => {
    const res = await getResult('99999999-9999-4999-8999-999999999999');
    expect(res.statusCode).toBe(404);
    const body = res.json();
    expect(body).toMatchObject({ statusCode: 404, code: PUBLIC_ERROR_CODES.CHARGE_NOT_FOUND });
    expectExactErrorShape(body);
  });

  it('never falls through to slug lookup for a UUID-shaped param', async () => {
    // The probe charge EXISTS and is active under this slug. Fallthrough
    // would resolve it and yield CHARGE_RESULT_UNAVAILABLE (it has no
    // aggregate rows); the pinned id-only rule yields CHARGE_NOT_FOUND.
    const res = await getResult(UUID_SHAPED_SLUG);
    expect(res.statusCode).toBe(404);
    expect(res.json().code).toBe(PUBLIC_ERROR_CODES.CHARGE_NOT_FOUND);
  });

  it('treats an inactive charge as CHARGE_NOT_FOUND', async () => {
    const res = await getResult('zz-result-inactive');
    expect(res.statusCode).toBe(404);
    expect(res.json().code).toBe(PUBLIC_ERROR_CODES.CHARGE_NOT_FOUND);
  });

  it('exposes only the public contract keys — no internal or per-row sample-size data', async () => {
    const allowedKeys = new Set([
      'charge',
      'id',
      'slug',
      'displayName',
      'statuteCode',
      'grade',
      'resultType',
      'geography',
      'dateRange',
      'start',
      'end',
      'lastRefreshed',
      'taxonomyVersion',
      'aggregateRunId',
      'outcomes',
      'sentencing',
      'sampleSize',
      'thinData',
      'rows',
      'categoryCode',
      'count',
      'percentage',
      'available',
      'message',
      'links',
      'methodology',
      'definitions',
      // Present on the 13.2a charge-only unavailable arm only.
      'code',
      // Task 35.2 sentencing-index section (success arm only). Months-named
      // median keys only — a day-named key must fail this sweep.
      'sentencingIndex',
      'summary',
      'convictions',
      'sentencedConvictions',
      'wedgeCount',
      'wedgePercentage',
      'categories',
      'convictionCount',
      'percentageOfSentenced',
      'medianMinMonths',
      'medianMaxMonths',
      'minAssumedPercentage',
      'grades',
      'percentageOfConvictions',
    ]);
    const collectKeys = (value: unknown, seen: string[]) => {
      if (Array.isArray(value)) {
        for (const item of value) collectKeys(item, seen);
      } else if (value !== null && typeof value === 'object') {
        for (const [key, nested] of Object.entries(value)) {
          seen.push(key);
          collectKeys(nested, seen);
        }
      }
      return seen;
    };

    for (const slug of ['retail-theft', 'possession-controlled-substance', 'harassment']) {
      const res = await getResult(slug);
      expect(res.statusCode).toBe(200);
      for (const key of collectKeys(res.json(), [])) {
        expect(allowedKeys.has(key), `unexpected response key: ${key}`).toBe(true);
      }
    }
    // Per-row keys never include a sample size — it lives on the block only
    // (asserted structurally by the row toEqual checks above and the key
    // sweep here, since rows contain no sampleSize key).
  });

  describe('sentencing index section (task 35.2)', () => {
    // Expected values restated by hand from db/seeds/aggregate-data.ts, the
    // taxonomy sort order, and the pin-3 day→month conversion (÷30, 1dp,
    // half-up) — an independent copy, so a drift in either side fails here.
    const RETAIL_THEFT_SENTENCING_INDEX = {
      available: true,
      summary: {
        convictions: 600,
        sentencedConvictions: 588,
        wedgeCount: 12,
        wedgePercentage: 2,
        thinData: false,
        dateRange: { start: '2025-01-03', end: '2026-06-27' },
      },
      // Taxonomy sort order; medians served in MONTHS (stored 360/540 and
      // 10.5/90 days — 10.5 is the exact half-up tie → 0.4).
      categories: [
        {
          categoryCode: 'probation',
          convictionCount: 290,
          percentageOfSentenced: 49.3,
          medianMinMonths: 12,
          medianMaxMonths: 18,
          minAssumedPercentage: 10,
        },
        {
          categoryCode: 'incarceration',
          convictionCount: 88,
          percentageOfSentenced: 15,
          medianMinMonths: 0.4,
          medianMaxMonths: 3,
          minAssumedPercentage: 20,
        },
        { categoryCode: 'fine', convictionCount: 200, percentageOfSentenced: 34 },
        { categoryCode: 'community_service', convictionCount: 60, percentageOfSentenced: 10.2 },
        { categoryCode: 'costs_fees', convictionCount: 150, percentageOfSentenced: 25.5 },
      ],
      // Dominant-first: conviction_count DESC, grade ASC tiebreak (M2 before
      // S at 60), the ungraded bucket riding at its count position.
      grades: [
        { grade: 'F3', convictionCount: 300, percentageOfConvictions: 50 },
        { grade: 'M1', convictionCount: 150, percentageOfConvictions: 25 },
        { grade: 'M2', convictionCount: 60, percentageOfConvictions: 10 },
        { grade: 'S', convictionCount: 60, percentageOfConvictions: 10 },
        { grade: 'ungraded', convictionCount: 30, percentageOfConvictions: 5 },
      ],
    };

    it('serves the full present arm beside an unchanged sentencing section', async () => {
      const res = await getResult('retail-theft');
      expect(res.statusCode).toBe(200);
      const body = res.json();
      expect(body.sentencingIndex).toEqual(RETAIL_THEFT_SENTENCING_INDEX);
      // The sibling section is byte-stable: same shape and values as before.
      expect(body.sentencing).toEqual({
        available: true,
        sampleSize: 700,
        thinData: false,
        rows: RETAIL_THEFT_SENTENCING_ROWS,
      });
      // Months only — no day-named keys or values anywhere in the payload.
      expect(res.body).not.toMatch(/days/i);
    });

    it('serves the zero-sentenced summary: wedge 100%, empty categories, grade mix intact', async () => {
      const res = await getResult('possession-controlled-substance');
      expect(res.statusCode).toBe(200);
      const body = res.json();
      expect(body.sentencingIndex).toEqual({
        available: true,
        summary: {
          convictions: 323,
          sentencedConvictions: 0,
          wedgeCount: 323,
          wedgePercentage: 100,
          thinData: true,
          dateRange: { start: '2025-01-15', end: '2026-06-20' },
        },
        categories: [],
        grades: [
          { grade: 'M1', convictionCount: 200, percentageOfConvictions: 61.9 },
          { grade: 'ungraded', convictionCount: 123, percentageOfConvictions: 38.1 },
        ],
      });
      // The component-grain sentencing union stays independently unavailable.
      expect(body.sentencing).toEqual({
        available: false,
        message: CHARGE_SENTENCING_UNAVAILABLE_MESSAGE,
      });
    });

    it('passes the thin flag through on a tiny cell', async () => {
      const res = await getResult('criminal-trespass');
      expect(res.statusCode).toBe(200);
      const body = res.json();
      expect(body.sentencingIndex).toMatchObject({
        available: true,
        summary: { convictions: 6, sentencedConvictions: 5, wedgeCount: 1, thinData: true },
      });
      const index = body.sentencingIndex as {
        categories: { categoryCode: string; medianMinMonths?: number; medianMaxMonths?: number }[];
      };
      expect(index.categories[0]).toMatchObject({
        categoryCode: 'probation',
        medianMinMonths: 1,
        medianMaxMonths: 12,
      });
    });

    it('serves the bare absent arm on a charge the index does not cover, distributions intact', async () => {
      // simple-assault has outcome AND sentencing rows but no index rows —
      // the exact shape production enters when the active run predates the
      // index population.
      const res = await getResult('simple-assault');
      expect(res.statusCode).toBe(200);
      const body = res.json();
      expect(body.resultType).toBe('charge_only');
      expect(body.sentencingIndex).toEqual({ available: false });
      expect(body.outcomes).toMatchObject({ sampleSize: 800, thinData: false });
      expect(body.sentencing).toMatchObject({ available: true, sampleSize: 450 });
    });
  });
});
