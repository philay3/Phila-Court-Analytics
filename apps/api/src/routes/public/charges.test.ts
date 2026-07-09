import { Kysely, PostgresDialect } from 'kysely';
import pg from 'pg';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { PUBLIC_ERROR_CODES } from '@pca/shared';
import { seedReference, type Database } from '@pca/db';
import { buildApp } from '../../app.js';
import { escapeLike } from '../../repositories/charge-search.js';

const SEARCH_URL = '/api/v1/public/charges/search';

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
    // Idempotent reference seeding (single source of truth in @pca/db): makes
    // the suite self-sufficient in CI, where migrations run but db:seed does not.
    await seedReference(setupDb);
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
    expect(await names({ q: 'theft' })).toEqual(['Theft', 'Theft of Services', 'Retail Theft']);
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
    // "assault (simple)" — one row, and the name match suppresses matchedAlias.
    const res = await search({ q: 'assault' });
    const { results } = res.json();
    expect(results).toHaveLength(1);
    expect(results[0].displayName).toBe('Simple Assault');
    expect(results[0]).not.toHaveProperty('matchedAlias');
  });

  it('picks the alphabetically first alias when several match', async () => {
    // "dr" matches both DUI aliases and Possession's "drug possession".
    const res = await search({ q: 'dr' });
    const { results } = res.json();
    expect(results.map((r: { displayName: string }) => r.displayName)).toEqual([
      'DUI: General Impairment',
      'Possession of a Controlled Substance',
    ]);
    expect(results[0].matchedAlias).toBe('driving under the influence');
    expect(results[1].matchedAlias).toBe('drug possession');
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
