import { Kysely, PostgresDialect } from 'kysely';
import pg from 'pg';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import {
  CHARGE_SENTENCING_UNAVAILABLE_MESSAGE,
  JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE,
  PUBLIC_ERROR_CODES,
} from '@pca/shared';
import type { Database } from '@pca/db';
import { buildApp } from '../../app.js';

const resultUrl = (chargeIdOrSlug: string, judgeIdOrSlug: string) =>
  `/api/v1/public/results/charge/${chargeIdOrSlug}/judge/${judgeIdOrSlug}`;

// Requires the local database: `pnpm db:up`, migrations applied
// (`pnpm db:migrate:latest`), and DATABASE_URL (root .env is auto-loaded via
// vitest.config.ts). Reference and aggregate seeding happens once for the
// whole run in vitest.global-setup.ts.
const hasDb = Boolean(process.env.DATABASE_URL);
if (!hasDb) {
  console.warn(
    'DATABASE_URL not set — skipping judge-result DB tests. ' +
      'Start Postgres (pnpm db:up), apply migrations (pnpm db:migrate:latest), ' +
      'and create the root .env (cp .env.example .env).',
  );
}

// Endpoint-local public-safety guard (the exhaustive suite is task 10.1).
// Same substring list as the 8.1 suite; see there for the '"raw' rationale.
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

const TESTINA_RETAIL_THEFT_OUTCOME_ROWS = [
  { categoryCode: 'dismissed', displayName: 'Dismissed', count: 49, percentage: 35 },
  { categoryCode: 'withdrawn', displayName: 'Withdrawn', count: 21, percentage: 15 },
  { categoryCode: 'guilty_plea', displayName: 'Guilty plea', count: 42, percentage: 30 },
  { categoryCode: 'guilty_verdict', displayName: 'Guilty verdict', count: 7, percentage: 5 },
  { categoryCode: 'acquittal', displayName: 'Acquittal', count: 7, percentage: 5 },
  { categoryCode: 'diversion', displayName: 'Diversion', count: 14, percentage: 10 },
];

const TESTINA_RETAIL_THEFT_SENTENCING_ROWS = [
  { categoryCode: 'probation', displayName: 'Probation', count: 40, percentage: 47.06 },
  { categoryCode: 'incarceration', displayName: 'Incarceration', count: 4, percentage: 4.71 },
  { categoryCode: 'fine', displayName: 'Fine', count: 12, percentage: 14.12 },
  { categoryCode: 'restitution', displayName: 'Restitution', count: 3, percentage: 3.53 },
  {
    categoryCode: 'community_service',
    displayName: 'Community service',
    count: 17,
    percentage: 20,
  },
  { categoryCode: 'costs_fees', displayName: 'Costs and fees', count: 9, percentage: 10.59 },
];

const BASELINE_RETAIL_THEFT_OUTCOME_ROWS = [
  { categoryCode: 'dismissed', displayName: 'Dismissed', count: 264, percentage: 22 },
  { categoryCode: 'withdrawn', displayName: 'Withdrawn', count: 156, percentage: 13 },
  { categoryCode: 'guilty_plea', displayName: 'Guilty plea', count: 540, percentage: 45 },
  { categoryCode: 'guilty_verdict', displayName: 'Guilty verdict', count: 60, percentage: 5 },
  { categoryCode: 'acquittal', displayName: 'Acquittal', count: 36, percentage: 3 },
  { categoryCode: 'ard', displayName: 'ARD', count: 24, percentage: 2 },
  { categoryCode: 'diversion', displayName: 'Diversion', count: 108, percentage: 9 },
  { categoryCode: 'other', displayName: 'Other', count: 12, percentage: 1 },
];

describe.skipIf(!hasDb)(
  'GET /results/charge/:chargeIdOrSlug/judge/:judgeIdOrSlug against the seeded database',
  () => {
    // Distinct prefix from the other DB suites ('zz-test-', 'zz-result-'):
    // test files run in parallel against the same database, and cleanup must
    // never delete another suite's temp rows.
    const TEMP_SLUG_PREFIX = 'zz-judge-result-';
    // Fallthrough probe for the JUDGE param: an ACTIVE judge whose slug is
    // UUID-shaped, with zero aggregate rows. Requesting it must take the id
    // path and 404 with JUDGE_NOT_FOUND; slug fallthrough would resolve the
    // judge and produce the 200 unavailable arm instead (retail-theft has a
    // baseline). Tracked explicitly in cleanup — the prefix delete cannot
    // see it.
    const UUID_SHAPED_JUDGE_SLUG = '22222222-3333-4333-8444-555555555555';
    const TEMP_JUDGES = [
      { slug: UUID_SHAPED_JUDGE_SLUG, display_name: 'ZZ Judge Fallthrough Probe', is_active: true },
      {
        slug: 'zz-judge-result-inactive',
        display_name: 'ZZ Judge Inactive Probe',
        is_active: false,
      },
    ];

    let setupDb: Kysely<Database>;
    let app: ReturnType<typeof buildApp>;
    let retailTheftId: string;
    let simpleAssaultId: string;
    let testinaId: string;
    let fakenameId: string;
    let publishedRunId: string;

    // Neither temp judge has aliases or aggregate rows, so plain deletes are
    // FK-safe.
    async function deleteTempRows() {
      await setupDb
        .deleteFrom('ref.normalized_judges')
        .where((eb) =>
          eb.or([
            eb('slug', 'like', `${TEMP_SLUG_PREFIX}%`),
            eb('slug', '=', UUID_SHAPED_JUDGE_SLUG),
          ]),
        )
        .execute();
    }

    async function idBySlug(
      table: 'ref.normalized_charges' | 'ref.normalized_judges',
      slug: string,
    ) {
      return (
        await setupDb
          .selectFrom(table)
          .select('id')
          .where('slug', '=', slug)
          .executeTakeFirstOrThrow()
      ).id;
    }

    beforeAll(async () => {
      setupDb = new Kysely<Database>({
        dialect: new PostgresDialect({
          pool: new pg.Pool({ connectionString: process.env.DATABASE_URL }),
        }),
      });
      await deleteTempRows();
      await setupDb
        .insertInto('ref.normalized_judges')
        .values([...TEMP_JUDGES])
        .execute();

      retailTheftId = await idBySlug('ref.normalized_charges', 'retail-theft');
      simpleAssaultId = await idBySlug('ref.normalized_charges', 'simple-assault');
      testinaId = await idBySlug('ref.normalized_judges', 'judge-testina-placeholder');
      fakenameId = await idBySlug('ref.normalized_judges', 'judge-fakename-example');
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
    async function getResult(chargeIdOrSlug: string, judgeIdOrSlug: string) {
      const res = await app.inject({
        method: 'GET',
        url: resultUrl(chargeIdOrSlug, judgeIdOrSlug),
      });
      expectPublicSafeBody(res);
      return res;
    }

    it('returns the full judge-specific result by slugs: metadata, both scopes, four independent sample sizes', async () => {
      const res = await getResult('retail-theft', 'judge-testina-placeholder');
      expect(res.statusCode).toBe(200);
      const body = res.json();

      expect(body.resultType).toBe('judge_specific');
      expect(body.charge).toEqual({
        id: retailTheftId,
        slug: 'retail-theft',
        displayName: 'Retail Theft',
        statuteCode: '18 § 3929',
        // grade is null in the reference seeds → omitted, per the shared convention.
      });
      expect(body.judge).toEqual({
        id: testinaId,
        slug: 'judge-testina-placeholder',
        displayName: 'Judge Testina Placeholder',
      });
      expect(body.geography).toBe('philadelphia');
      expect(body.dateRange).toEqual({ start: '2025-01-01', end: '2026-06-30' });
      expect(body.lastRefreshed).toBe('2026-07-01T02:00:00.000Z');
      expect(body.taxonomyVersion).toBe('1.0.0');
      expect(body.aggregateRunId).toBe(publishedRunId);
      expect(body.links).toEqual({ methodology: '/methodology', definitions: '/definitions' });

      // Judge-specific scope, rows in taxonomy order.
      expect(body.judgeSpecific).toEqual({
        outcomes: { sampleSize: 140, thinData: false, rows: TESTINA_RETAIL_THEFT_OUTCOME_ROWS },
        sentencing: {
          available: true,
          sampleSize: 85,
          thinData: false,
          rows: TESTINA_RETAIL_THEFT_SENTENCING_ROWS,
        },
      });
      // Baseline is REQUIRED and carries the charge-only distributions.
      expect(body.baseline).toEqual({
        outcomes: { sampleSize: 1200, thinData: false, rows: BASELINE_RETAIL_THEFT_OUTCOME_ROWS },
        sentencing: expect.objectContaining({ available: true, sampleSize: 700 }),
      });

      // Four independent sample sizes, asserted against the seeded values.
      const sampleSizes = [
        (body.judgeSpecific as { outcomes: { sampleSize: number } }).outcomes.sampleSize,
        (body.judgeSpecific as { sentencing: { sampleSize: number } }).sentencing.sampleSize,
        (body.baseline as { outcomes: { sampleSize: number } }).outcomes.sampleSize,
        (body.baseline as { sentencing: { sampleSize: number } }).sentencing.sampleSize,
      ];
      expect(sampleSizes).toEqual([140, 85, 1200, 700]);
      expect(new Set(sampleSizes).size).toBe(4);
      // The unpublished decoy run stores retail-theft outcomes as uniform
      // 9999s; none of that may ever surface.
      expect(res.body).not.toContain('9999');
    });

    it('returns an identical body for UUID and mixed param modes', async () => {
      const bySlug = await getResult('retail-theft', 'judge-testina-placeholder');
      expect(bySlug.statusCode).toBe(200);

      const byIds = await getResult(retailTheftId, testinaId);
      expect(byIds.statusCode).toBe(200);
      expect(byIds.json()).toEqual(bySlug.json());

      const slugChargeUuidJudge = await getResult('retail-theft', testinaId);
      expect(slugChargeUuidJudge.statusCode).toBe(200);
      expect(slugChargeUuidJudge.json()).toEqual(bySlug.json());

      const uuidChargeSlugJudge = await getResult(retailTheftId, 'judge-testina-placeholder');
      expect(uuidChargeSlugJudge.statusCode).toBe(200);
      expect(uuidChargeSlugJudge.json()).toEqual(bySlug.json());

      const byUpperIds = await getResult(retailTheftId.toUpperCase(), testinaId.toUpperCase());
      expect(byUpperIds.statusCode).toBe(200);
      expect(byUpperIds.json()).toEqual(bySlug.json());
    });

    it('flags thin data on the judge scope only, with the judge sentencing union independently unavailable', async () => {
      const res = await getResult('simple-assault', 'judge-testina-placeholder');
      expect(res.statusCode).toBe(200);
      const body = res.json();
      expect(body.charge).toMatchObject({ id: simpleAssaultId, slug: 'simple-assault' });
      expect(body.judgeSpecific).toEqual({
        outcomes: expect.objectContaining({ sampleSize: 9, thinData: true }),
        // The seeded pair has outcome rows but no sentencing rows: the
        // judge-scoped union takes the unavailable arm while the baseline
        // union stays available.
        sentencing: { available: false, message: CHARGE_SENTENCING_UNAVAILABLE_MESSAGE },
      });
      expect((body.judgeSpecific as { outcomes: { rows: unknown[] } }).outcomes.rows).toHaveLength(
        5,
      );
      expect(body.baseline).toEqual({
        outcomes: expect.objectContaining({ sampleSize: 800, thinData: false }),
        sentencing: expect.objectContaining({ available: true, sampleSize: 450 }),
      });
    });

    it('returns the HTTP-200 unavailable arm for a valid pair with no judge-specific aggregate', async () => {
      const res = await getResult('retail-theft', 'judge-fakename-example');
      expect(res.statusCode).toBe(200);
      // Exact body: identity, pinned literals, and the fallback — nothing
      // else (no distributions, no sample sizes, no run metadata, no links).
      expect(res.json()).toEqual({
        resultType: 'judge_specific_unavailable',
        code: 'JUDGE_SPECIFIC_RESULT_UNAVAILABLE',
        message: JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE,
        charge: {
          id: retailTheftId,
          slug: 'retail-theft',
          displayName: 'Retail Theft',
          statuteCode: '18 § 3929',
        },
        judge: {
          id: fakenameId,
          slug: 'judge-fakename-example',
          displayName: 'Judge Fakename Example',
        },
        fallback: { chargeOnlyResultPath: '/api/v1/public/results/charge/retail-theft' },
      });
    });

    it('serves the unavailable arm identically by UUIDs', async () => {
      const bySlug = await getResult('retail-theft', 'judge-fakename-example');
      const byIds = await getResult(retailTheftId, fakenameId);
      expect(byIds.statusCode).toBe(200);
      expect(byIds.json()).toEqual(bySlug.json());
    });

    it('returns 404 CHARGE_NOT_FOUND for an unknown charge, resolved before the judge', async () => {
      // Both params unknown: the charge miss must win (resolution order).
      const res = await getResult('no-such-charge', 'no-such-judge');
      expect(res.statusCode).toBe(404);
      const body = res.json();
      expect(body).toMatchObject({ statusCode: 404, code: PUBLIC_ERROR_CODES.CHARGE_NOT_FOUND });
      expectExactErrorShape(body);
    });

    it('returns 404 JUDGE_NOT_FOUND for an unknown judge slug and an unknown judge UUID', async () => {
      for (const judgeParam of ['no-such-judge', '99999999-9999-4999-8999-999999999999']) {
        const res = await getResult('retail-theft', judgeParam);
        expect(res.statusCode).toBe(404);
        const body = res.json();
        expect(body).toMatchObject({ statusCode: 404, code: PUBLIC_ERROR_CODES.JUDGE_NOT_FOUND });
        expectExactErrorShape(body);
      }
    });

    it('never falls through to slug lookup for a UUID-shaped judge param', async () => {
      // The probe judge EXISTS and is active under this slug, and retail-theft
      // has a baseline. Fallthrough would resolve the judge and yield the 200
      // unavailable arm; the pinned id-only rule yields JUDGE_NOT_FOUND.
      const res = await getResult('retail-theft', UUID_SHAPED_JUDGE_SLUG);
      expect(res.statusCode).toBe(404);
      expect(res.json().code).toBe(PUBLIC_ERROR_CODES.JUDGE_NOT_FOUND);
    });

    it('treats an inactive judge as JUDGE_NOT_FOUND', async () => {
      const res = await getResult('retail-theft', 'zz-judge-result-inactive');
      expect(res.statusCode).toBe(404);
      expect(res.json().code).toBe(PUBLIC_ERROR_CODES.JUDGE_NOT_FOUND);
    });

    it('exposes only the public contract keys on both arms', async () => {
      const allowedKeys = new Set([
        'resultType',
        'charge',
        'judge',
        'id',
        'slug',
        'displayName',
        'statuteCode',
        'grade',
        'geography',
        'dateRange',
        'start',
        'end',
        'lastRefreshed',
        'taxonomyVersion',
        'aggregateRunId',
        'judgeSpecific',
        'baseline',
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
        'code',
        'fallback',
        'chargeOnlyResultPath',
        // Task 35.2 sentencing-index section (success arm only, judge
        // grain). Deliberately NOT allowed: 'grades' and
        // 'percentageOfConvictions' — the judge arm carries no grade mix
        // (ruling 2), so those keys appearing here is a contract breach the
        // sweep must catch. Months-named median keys only.
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

      for (const [chargeParam, judgeParam] of [
        ['retail-theft', 'judge-testina-placeholder'],
        ['simple-assault', 'judge-testina-placeholder'],
        ['retail-theft', 'judge-fakename-example'],
      ] as const) {
        const res = await getResult(chargeParam, judgeParam);
        expect(res.statusCode).toBe(200);
        for (const key of collectKeys(res.json(), [])) {
          expect(allowedKeys.has(key), `unexpected response key: ${key}`).toBe(true);
        }
      }
    });

    describe('sentencing index section (task 35.2, judge grain)', () => {
      it('serves the present arm for the seeded cell — summary, categories in months, NO grade mix', async () => {
        const res = await getResult('retail-theft', 'judge-testina-placeholder');
        expect(res.statusCode).toBe(200);
        const body = res.json();
        // Expected values restated by hand from db/seeds/aggregate-data.ts
        // and the pin-3 day→month conversion (stored 60/180 days → 2/6).
        expect(body.sentencingIndex).toEqual({
          available: true,
          summary: {
            convictions: 49,
            sentencedConvictions: 45,
            wedgeCount: 4,
            wedgePercentage: 8.2,
            thinData: false,
            dateRange: { start: '2025-02-01', end: '2026-06-10' },
          },
          categories: [
            {
              categoryCode: 'probation',
              convictionCount: 30,
              percentageOfSentenced: 66.7,
              medianMinMonths: 2,
              medianMaxMonths: 6,
              minAssumedPercentage: 40,
            },
            {
              // Flat median pair (35.3 ruling Q5): stored 90/90 days → 3/3.
              categoryCode: 'incarceration',
              convictionCount: 12,
              percentageOfSentenced: 26.7,
              medianMinMonths: 3,
              medianMaxMonths: 3,
              minAssumedPercentage: 25,
            },
            { categoryCode: 'fine', convictionCount: 20, percentageOfSentenced: 44.4 },
          ],
        });
        // Ruling 2, asserted structurally: no grades key on the judge arm.
        expect('grades' in (body.sentencingIndex as object)).toBe(false);
        expect(res.body).not.toMatch(/days/i);
      });

      it('serves the bare absent arm on a success payload whose cell the index does not cover', async () => {
        // The dui/samuel pair has outcome and sentencing rows but no index
        // rows — the exact shape production enters when the active run
        // predates the index population.
        const res = await getResult('dui-general-impairment', 'judge-samuel-seeddata');
        expect(res.statusCode).toBe(200);
        const body = res.json();
        expect(body.resultType).toBe('judge_specific');
        expect(body.sentencingIndex).toEqual({ available: false });
        expect(body.judgeSpecific).toMatchObject({
          outcomes: expect.objectContaining({ sampleSize: 210 }),
        });
      });
    });
  },
);
