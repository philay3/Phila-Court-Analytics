import { Kysely, PostgresDialect } from 'kysely';
import pg from 'pg';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import {
  CHARGE_DIRECTORY_UNAVAILABLE_MESSAGE,
  PUBLIC_ERROR_CODES,
  type ChargeDirectoryResponse,
  type DataCoverageResponse,
} from '@pca/shared';
import type { Database } from '@pca/db';
import { buildApp } from '../../app.js';
import type { PublicApiDatabase } from '../../db.js';
import { escapeLike } from '../../repositories/charge-search.js';

const SEARCH_URL = '/api/v1/public/charges/search';
const DIRECTORY_URL = '/api/v1/public/charges';

// Requires the local database: `pnpm db:up`, migrations applied
// (`pnpm db:migrate:latest`), and DATABASE_URL (root .env is auto-loaded via
// vitest.config.ts). DB-backed cases are skipped when DATABASE_URL is unset;
// validation cases run everywhere (the service rejects before touching the DB).
const hasDb = Boolean(process.env.DATABASE_URL);
if (!hasDb) {
  console.warn(
    'DATABASE_URL not set — skipping charge-search DB tests. ' +
      'Start Postgres (pnpm db:up), apply migrations (pnpm db:migrate:latest), ' +
      'and create the root .env (cp .env.example .env).',
  );
}

function testApp() {
  return buildApp({ logger: false });
}

function expectExactErrorShape(body: Record<string, unknown>) {
  expect(Object.keys(body).sort()).toEqual(['code', 'error', 'message', 'requestId', 'statusCode']);
}

describe('escapeLike', () => {
  it('escapes %, _, and the escape character itself', () => {
    expect(escapeLike('50%_\\')).toBe('50\\%\\_\\\\');
    expect(escapeLike('%%')).toBe('\\%\\%');
  });

  it('leaves plain text untouched', () => {
    expect(escapeLike('retail theft')).toBe('retail theft');
    expect(escapeLike('18 § 3929')).toBe('18 § 3929');
  });
});

describe('GET /charges/search validation (no DB required)', () => {
  it('rejects a missing q with 400 INVALID_REQUEST in the catalog shape', async () => {
    const res = await testApp().inject({ method: 'GET', url: SEARCH_URL });
    expect(res.statusCode).toBe(400);
    const body = res.json();
    expect(body).toMatchObject({ statusCode: 400, code: PUBLIC_ERROR_CODES.INVALID_REQUEST });
    expectExactErrorShape(body);
  });

  it('rejects a whitespace-only q with 400 INVALID_REQUEST in the catalog shape', async () => {
    const res = await testApp().inject({ method: 'GET', url: SEARCH_URL, query: { q: '   ' } });
    expect(res.statusCode).toBe(400);
    const body = res.json();
    expect(body).toMatchObject({ statusCode: 400, code: PUBLIC_ERROR_CODES.INVALID_REQUEST });
    expectExactErrorShape(body);
  });

  it('rejects a q longer than 100 characters after trimming', async () => {
    const res = await testApp().inject({
      method: 'GET',
      url: SEARCH_URL,
      query: { q: 'a'.repeat(101) },
    });
    expect(res.statusCode).toBe(400);
    expect(res.json().code).toBe(PUBLIC_ERROR_CODES.INVALID_REQUEST);
  });

  it.each(['0', '26', '1.5', 'abc'])('rejects limit=%s with 400 INVALID_REQUEST', async (limit) => {
    const res = await testApp().inject({
      method: 'GET',
      url: SEARCH_URL,
      query: { q: 'theft', limit },
    });
    expect(res.statusCode).toBe(400);
    const body = res.json();
    expect(body).toMatchObject({ statusCode: 400, code: PUBLIC_ERROR_CODES.INVALID_REQUEST });
    expectExactErrorShape(body);
  });
});

describe.skipIf(!hasDb)('GET /charges/search against the seeded database', () => {
  const TEMP_SLUG_PREFIX = 'zz-test-';
  // Temp rows (cleaned up before insert and in afterAll): a three-tier ranking
  // ladder for q="theft" alongside the seeded Retail Theft, an inactive decoy,
  // and 26 uniform matches to prove the limit default and maximum.
  const TEMP_CHARGES = [
    { slug: 'zz-test-theft-exact', display_name: 'Theft', is_active: true },
    { slug: 'zz-test-theft-prefix', display_name: 'Theft of Services', is_active: true },
    { slug: 'zz-test-theft-inactive', display_name: 'Theft Inactive Probe', is_active: false },
    ...Array.from({ length: 26 }, (_, i) => {
      const nn = String(i + 1).padStart(2, '0');
      return { slug: `zz-test-limit-${nn}`, display_name: `ZZ Test Charge ${nn}`, is_active: true };
    }),
  ];

  let setupDb: Kysely<Database>;
  let app: ReturnType<typeof buildApp>;

  async function deleteTempRows() {
    await setupDb
      .deleteFrom('ref.normalized_charges')
      .where('slug', 'like', `${TEMP_SLUG_PREFIX}%`)
      .execute();
  }

  beforeAll(async () => {
    setupDb = new Kysely<Database>({
      dialect: new PostgresDialect({
        pool: new pg.Pool({ connectionString: process.env.DATABASE_URL }),
      }),
    });
    // Reference seeding happens once per run in vitest.global-setup.ts.
    await deleteTempRows();
    await setupDb
      .insertInto('ref.normalized_charges')
      .values(TEMP_CHARGES.map((c) => ({ ...c, statute_code: null, grade: null })))
      .execute();
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

  async function search(query: Record<string, string>) {
    const res = await app.inject({ method: 'GET', url: SEARCH_URL, query });
    return res;
  }

  async function names(query: Record<string, string>): Promise<string[]> {
    const res = await search(query);
    expect(res.statusCode).toBe(200);
    const body = res.json() as { results: { displayName: string }[] };
    return body.results.map((r) => r.displayName);
  }

  it('ranks exact above prefix above substring for q="theft"', async () => {
    // Invariant, not a fixed list (the 22.2 roster seed grows the "theft" set):
    // classify each returned display name by tier — 0 exact ("theft"), 1 prefix
    // ("theft…"), 2 substring ("…theft…") — and assert the exact match is first,
    // tiers are non-decreasing down the ranked list, and names are alphabetical
    // within each tier. The temp rows supply the exact ("Theft") and a prefix
    // ("Theft of Services"); the roster supplies prefixes ("Theft by …") and
    // substrings ("Identity Theft", "Retail Theft"). Every current match has
    // "theft" in the NAME, so name-tier tracks the repository's match_rank.
    const tierOf = (name: string): number => {
      const n = name.toLowerCase();
      if (n === 'theft') return 0;
      if (n.startsWith('theft')) return 1;
      if (n.includes('theft')) return 2;
      return 3; // alias/statute-only match (none in the current roster)
    };
    const results = await names({ q: 'theft' });
    expect(results.length).toBeGreaterThan(0);
    expect(results[0]).toBe('Theft'); // the exact match ranks first
    const tiers = results.map(tierOf);
    expect(tiers).toEqual([...tiers].sort((a, b) => a - b)); // non-decreasing tier
    for (const tier of new Set(tiers)) {
      const inTier = results.filter((n) => tierOf(n) === tier);
      expect(inTier).toEqual([...inTier].sort((a, b) => a.localeCompare(b))); // alpha within tier
    }
  });

  it('returns the parent charge with matchedAlias for an alias match', async () => {
    const res = await search({ q: 'shoplifting' });
    expect(res.statusCode).toBe(200);
    const { results } = res.json();
    expect(results).toHaveLength(1);
    expect(results[0]).toMatchObject({
      slug: 'retail-theft',
      displayName: 'Retail Theft',
      statuteCode: '18 § 3929',
      matchedAlias: 'shoplifting',
    });
  });

  it('matches by substring of the display name', async () => {
    const res = await search({ q: 'impairment' });
    const { results } = res.json();
    expect(results).toHaveLength(1);
    expect(results[0].displayName).toBe('DUI: General Impairment');
    expect(results[0]).not.toHaveProperty('matchedAlias');
  });

  it('is case-insensitive for names and aliases', async () => {
    const lower = await search({ q: 'retail theft' });
    const upper = await search({ q: 'RETAIL THEFT' });
    const mixed = await search({ q: 'ReTaIl ThEfT' });
    expect(lower.json()).toEqual(upper.json());
    expect(lower.json()).toEqual(mixed.json());
    expect(lower.json().results[0].displayName).toBe('Retail Theft');

    const alias = await search({ q: 'SHOPLIFTING' });
    expect(alias.json().results[0].matchedAlias).toBe('shoplifting');
  });

  it('dedups a charge whose name and alias both match, without matchedAlias', async () => {
    // "assault" matches Simple Assault's display name AND its alias
    // "assault (simple)". The 22.2 roster adds other "assault" charges, so assert
    // the invariant on the target row only (not the total count): it appears
    // exactly once (no join fan-out), and the name match suppresses matchedAlias.
    const res = await search({ q: 'assault' });
    const { results } = res.json();
    const target = results.filter((r: { slug: string }) => r.slug === 'simple-assault');
    expect(target).toHaveLength(1);
    expect(target[0].displayName).toBe('Simple Assault');
    expect(target[0]).not.toHaveProperty('matchedAlias');
  });

  it('picks the alphabetically first alias when several match', async () => {
    // Target: DUI: General Impairment, whose name has no "dr" (so matchedAlias is
    // populated) and which has SEVERAL aliases matching "dr" ("driving under the
    // influence", "drunk driving"). Derive the expected value from the DB rather
    // than hardcoding it — order the charge's aliases by the same collation the
    // repository's MIN(alias_text) uses — so roster growth cannot re-break this.
    const targetSlug = 'dui-general-impairment';
    const aliasRows = await setupDb
      .selectFrom('ref.charge_aliases as a')
      .innerJoin('ref.normalized_charges as c', 'c.id', 'a.normalized_charge_id')
      .select('a.alias_text')
      .where('c.slug', '=', targetSlug)
      .orderBy('a.alias_text')
      .execute();
    const drAliases = aliasRows
      .map((r) => r.alias_text)
      .filter((alias) => alias.toLowerCase().includes('dr'));
    expect(drAliases.length).toBeGreaterThan(1); // several aliases match "dr"

    const res = await search({ q: 'dr' });
    const { results } = res.json();
    const target = results.find((r: { slug: string }) => r.slug === targetSlug);
    expect(target, 'target charge missing from q="dr" results').toBeDefined();
    expect(target.matchedAlias).toBe(drAliases[0]); // the alphabetically first
  });

  it('matches by statute code without populating matchedAlias', async () => {
    for (const q of ['18 § 3929', '3929']) {
      const res = await search({ q });
      const { results } = res.json();
      expect(results).toHaveLength(1);
      expect(results[0].displayName).toBe('Retail Theft');
      expect(results[0]).not.toHaveProperty('matchedAlias');
    }
  });

  it('returns 200 with an empty result list when nothing matches', async () => {
    const res = await search({ q: 'xyzzy' });
    expect(res.statusCode).toBe(200);
    expect(res.json()).toEqual({ results: [] });
  });

  it('treats LIKE wildcards as literals: q="%" and q="_" match nothing', async () => {
    for (const q of ['%', '_']) {
      const res = await search({ q });
      expect(res.statusCode).toBe(200);
      expect(res.json()).toEqual({ results: [] });
    }
  });

  it('accepts a q that trims down to exactly 100 characters', async () => {
    const res = await search({ q: `  ${'a'.repeat(100)}  ` });
    expect(res.statusCode).toBe(200);
    expect(res.json()).toEqual({ results: [] });
  });

  it('applies the default limit of 10 after ranking', async () => {
    const result = await names({ q: 'zz test charge' });
    expect(result).toEqual(
      Array.from({ length: 10 }, (_, i) => `ZZ Test Charge ${String(i + 1).padStart(2, '0')}`),
    );
  });

  it('honors limit up to the maximum of 25', async () => {
    expect(await names({ q: 'zz test charge', limit: '25' })).toHaveLength(25);
    expect(await names({ q: 'zz test charge', limit: '1' })).toEqual(['ZZ Test Charge 01']);
  });

  it('never returns inactive charges', async () => {
    // Direct probe: only the inactive decoy's name contains this phrase.
    expect(await search({ q: 'inactive probe' }).then((r) => r.json())).toEqual({ results: [] });
    // And it must not ride along on the shared "theft" query either.
    const res = await search({ q: 'theft' });
    const slugs = res.json().results.map((r: { slug: string }) => r.slug);
    expect(slugs).not.toContain('zz-test-theft-inactive');
  });

  it('exposes only the public contract fields — no aggregate or internal data', async () => {
    const res = await search({ q: 'dr' });
    expect(res.statusCode).toBe(200);
    const body = res.json();
    expect(body.results.length).toBeGreaterThan(0);

    const allowedKeys = new Set([
      'results',
      'id',
      'slug',
      'displayName',
      'statuteCode',
      'grade',
      'matchedAlias',
    ]);
    const seenKeys: string[] = [];
    const collect = (value: unknown) => {
      if (Array.isArray(value)) {
        value.forEach(collect);
      } else if (value !== null && typeof value === 'object') {
        for (const [key, nested] of Object.entries(value)) {
          seenKeys.push(key);
          collect(nested);
        }
      }
    };
    collect(body);
    for (const key of seenKeys) {
      expect(allowedKeys.has(key), `unexpected response key: ${key}`).toBe(true);
    }

    for (const forbidden of [
      'count',
      'percentage',
      'sampleSize',
      'sentencing',
      'docket',
      'defendant',
      'source',
      'parser',
      'review',
    ]) {
      expect(res.body).not.toContain(forbidden);
    }
  });
});

// ---------------------------------------------------------------------------
// GET /charges — directory (task DP-4)
// ---------------------------------------------------------------------------
//
// Reachable error-code surface for this no-required-params GET (R3):
//   - INTERNAL_ERROR (500): any unexpected handler/DB throw — exercised below
//     via a poison DB handle.
//   - RATE_LIMITED (429): structurally justified, not exercised — the limiter
//     is registered once around the whole public namespace
//     (routes/public/index.ts) with a shared global bucket; flooding it here
//     would flake every concurrently running public-route suite. Its catalog
//     shaping is the central handler's, identical for every route.
//   - INVALID_REQUEST (400): unreachable — no params or querystring, so Ajv
//     never produces error.validation.
//   - NOT_FOUND (404): only the unknown-route handler emits it; never for
//     this path.
//   - Entity/unavailable codes: N/A — there is no entity to resolve, and "no
//     active published run" is the 200 tagged union's unavailable arm, never
//     an error.

describe('GET /charges error surface (no DB required)', () => {
  it('returns 500 INTERNAL_ERROR in the catalog shape when the database is unavailable', async () => {
    const poison = new Proxy({} as Kysely<PublicApiDatabase>, {
      get(_target, property) {
        throw new Error(`poison db accessed (${String(property)})`);
      },
    });
    const app = buildApp({ logger: false, db: poison });
    try {
      const res = await app.inject({ method: 'GET', url: DIRECTORY_URL });
      expect(res.statusCode).toBe(500);
      const body = res.json();
      expect(body).toMatchObject({ statusCode: 500, code: PUBLIC_ERROR_CODES.INTERNAL_ERROR });
      expectExactErrorShape(body);
      // The central handler hard-codes the 5xx body message — the poison
      // error's text (or any internal detail) must never surface.
      expect(res.body).not.toContain('poison');
    } finally {
      await app.close();
    }
  });
});

describe.skipIf(!hasDb)('GET /charges (directory) against the seeded database', () => {
  let setupDb: Kysely<PublicApiDatabase>;
  let app: ReturnType<typeof buildApp>;

  beforeAll(async () => {
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

  // Every key either arm may ever contain; the recursive sweep fails on
  // anything else. outcomeSampleSize is a pinned payload-only field (DP-4),
  // so it is legitimately present here — unlike the search contract.
  const ALLOWED_KEYS = new Set([
    'available',
    'charges',
    'slug',
    'displayName',
    'statuteCode',
    'hasSentencing',
    'outcomeSampleSize',
    'message',
  ]);

  function expectPublicSafeBody(res: { body: string; json: <T>() => T }) {
    const lowered = res.body.toLowerCase();
    for (const forbidden of [
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
      'percentage',
    ]) {
      expect(lowered, `forbidden content: ${forbidden}`).not.toContain(forbidden);
    }
    const sweep = (value: unknown): void => {
      if (Array.isArray(value)) {
        value.forEach(sweep);
      } else if (value !== null && typeof value === 'object') {
        for (const [key, nested] of Object.entries(value)) {
          expect(ALLOWED_KEYS.has(key), `unexpected response key: ${key}`).toBe(true);
          sweep(nested);
        }
      }
    };
    sweep(res.json<Record<string, unknown>>());
  }

  async function getDirectory() {
    const res = await app.inject({ method: 'GET', url: DIRECTORY_URL });
    expectPublicSafeBody(res);
    expect(res.statusCode).toBe(200);
    return res.json<ChargeDirectoryResponse>();
  }

  async function getAvailableCharges() {
    const body = await getDirectory();
    if (!body.available) {
      throw new Error('expected the available arm');
    }
    return body.charges;
  }

  it('serves every field derived from the active run, independently of seed constants', async () => {
    // Expected values are derived from the database through independent,
    // ungrouped queries (JS-side aggregation restates the repository's SQL
    // grouping rather than mirroring it). Scoping both derivations to the
    // active-published predicate makes decoy-run exclusion part of the same
    // assertion: any leak from the unpublished run would break the per-slug
    // field comparison.
    const activeRun = await setupDb
      .selectFrom('analytics.aggregate_runs')
      .select('id')
      .where('published_at', 'is not', null)
      .where('invalidated_at', 'is', null)
      .executeTakeFirstOrThrow();

    const outcomeRows = await setupDb
      .selectFrom('analytics.charge_outcome_aggregates as coa')
      .innerJoin('ref.normalized_charges as nc', 'nc.id', 'coa.charge_id')
      .where('coa.aggregate_run_id', '=', activeRun.id)
      .select(['nc.slug', 'nc.display_name', 'nc.statute_code', 'coa.sample_size'])
      .execute();
    const sentencingRows = await setupDb
      .selectFrom('analytics.charge_sentencing_aggregates as csa')
      .innerJoin('ref.normalized_charges as nc', 'nc.id', 'csa.charge_id')
      .where('csa.aggregate_run_id', '=', activeRun.id)
      .select(['nc.slug'])
      .execute();

    const sentencingSlugs = new Set(sentencingRows.map((r) => r.slug));
    const expectedBySlug = new Map<
      string,
      { displayName: string; statuteCode: string | null; sampleSize: number }
    >();
    for (const row of outcomeRows) {
      const existing = expectedBySlug.get(row.slug);
      expectedBySlug.set(row.slug, {
        displayName: row.display_name,
        statuteCode: row.statute_code,
        sampleSize: Math.max(existing?.sampleSize ?? 0, row.sample_size),
      });
    }
    expect(expectedBySlug.size).toBeGreaterThan(0);

    const charges = await getAvailableCharges();
    expect(new Set(charges.map((c) => c.slug))).toEqual(new Set(expectedBySlug.keys()));
    for (const charge of charges) {
      const expected = expectedBySlug.get(charge.slug);
      expect(expected, `unexpected directory row: ${charge.slug}`).toBeDefined();
      expect(charge.displayName).toBe(expected?.displayName);
      expect(charge.outcomeSampleSize).toBe(expected?.sampleSize);
      expect(charge.hasSentencing).toBe(sentencingSlugs.has(charge.slug));
      if (expected?.statuteCode === null) {
        expect(charge).not.toHaveProperty('statuteCode');
      } else {
        expect(charge.statuteCode).toBe(expected?.statuteCode);
      }
    }
  });

  it('serves rows sorted by sample size desc, then name asc, then slug asc (DP-5 pin)', async () => {
    const charges = await getAvailableCharges();
    expect(charges.length).toBeGreaterThan(1);
    const sorted = [...charges].sort((a, b) => {
      if (a.outcomeSampleSize !== b.outcomeSampleSize) {
        return b.outcomeSampleSize - a.outcomeSampleSize;
      }
      const nameOrder = a.displayName.toLowerCase().localeCompare(b.displayName.toLowerCase());
      return nameOrder !== 0 ? nameOrder : a.slug.localeCompare(b.slug);
    });
    expect(charges.map((c) => c.slug)).toEqual(sorted.map((c) => c.slug));
    // The served sample sizes are monotonically non-increasing — the ORDER BY
    // key is the same expression that produces outcomeSampleSize.
    const sizes = charges.map((c) => c.outcomeSampleSize);
    expect(sizes).toEqual([...sizes].sort((a, b) => b - a));
  });

  it('carries both availability shapes on named fixtures', async () => {
    const charges = await getAvailableCharges();
    // Targeted probes on seeded fixtures (charge-search precedent): retail
    // theft is a sentencing-bearing fixture; possession is a deliberate
    // sentencing-unavailable fixture.
    const retailTheft = charges.find((c) => c.slug === 'retail-theft');
    expect(retailTheft).toMatchObject({
      displayName: 'Retail Theft',
      statuteCode: '18 § 3929',
      hasSentencing: true,
    });
    const possession = charges.find((c) => c.slug === 'possession-controlled-substance');
    expect(possession).toBeDefined();
    expect(possession?.hasSentencing).toBe(false);
  });

  it('matches data-coverage: directory total equals chargesWithOutcomeAggregates', async () => {
    // AC 3: both endpoints read DISTINCT charge_id over
    // charge_outcome_aggregates scoped by the same active-run resolver, so
    // equality holds by construction — this test proves the construction.
    const charges = await getAvailableCharges();
    const coverageRes = await app.inject({ method: 'GET', url: '/api/v1/public/data-coverage' });
    expect(coverageRes.statusCode).toBe(200);
    const coverage = coverageRes.json<DataCoverageResponse>().coverage;
    if (!coverage.available) {
      throw new Error('expected the available coverage arm');
    }
    expect(charges.length).toBe(coverage.counts.chargesWithOutcomeAggregates);
  });

  it('returns 200 with the unavailable arm when no active published run exists', async () => {
    // Isolation per the suite's standing pattern: the active run is
    // invalidated inside an uncommitted transaction and the app under test is
    // built on that transaction connection; the rollback in finally
    // guarantees the shared seeded state survives even if an assertion
    // throws.
    const trx = await setupDb.startTransaction().execute();
    try {
      await trx
        .updateTable('analytics.aggregate_runs')
        .set({
          invalidated_at: new Date(),
          invalidated_reason: 'task DP-4 unavailable-arm test (rolled back)',
        })
        .where('published_at', 'is not', null)
        .where('invalidated_at', 'is', null)
        .execute();

      const trxApp = buildApp({ logger: false, db: trx });
      try {
        const res = await trxApp.inject({ method: 'GET', url: DIRECTORY_URL });
        expectPublicSafeBody(res);
        expect(res.statusCode).toBe(200);
        expect(res.json()).toEqual({
          available: false,
          message: CHARGE_DIRECTORY_UNAVAILABLE_MESSAGE,
        });
      } finally {
        await trxApp.close();
      }
    } finally {
      await trx.rollback().execute();
    }

    // The shared seeded state is untouched after the rollback.
    const after = await getDirectory();
    expect(after.available).toBe(true);
  });
});
