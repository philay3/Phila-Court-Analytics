import { Kysely, PostgresDialect } from 'kysely';
import pg from 'pg';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { PUBLIC_ERROR_CODES } from '@pca/shared';
import type { Database } from '@pca/db';
import { buildApp } from '../../app.js';

const SEARCH_URL = '/api/v1/public/judges/search';

// Requires the local database: `pnpm db:up`, migrations applied
// (`pnpm db:migrate:latest`), and DATABASE_URL (root .env is auto-loaded via
// vitest.config.ts). DB-backed cases are skipped when DATABASE_URL is unset;
// validation cases run everywhere (the service rejects before touching the DB).
const hasDb = Boolean(process.env.DATABASE_URL);
if (!hasDb) {
  console.warn(
    'DATABASE_URL not set — skipping judge-search DB tests. ' +
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

describe('GET /judges/search validation (no DB required)', () => {
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
      query: { q: 'placeholder', limit },
    });
    expect(res.statusCode).toBe(400);
    const body = res.json();
    expect(body).toMatchObject({ statusCode: 400, code: PUBLIC_ERROR_CODES.INVALID_REQUEST });
    expectExactErrorShape(body);
  });
});

describe.skipIf(!hasDb)('GET /judges/search against the seeded database', () => {
  const TEMP_SLUG_PREFIX = 'zz-test-';
  // Temp rows (cleaned up before insert and in afterAll): a three-tier ranking
  // ladder for q="fakename" alongside the seeded Judge Fakename Example, an
  // inactive decoy, an alias-heavy judge for the matchedAlias rules, a judge
  // whose name and alias both match, and 26 uniform matches to prove the limit
  // default and maximum.
  const TEMP_JUDGES = [
    { slug: 'zz-test-fakename-exact', display_name: 'Fakename', is_active: true },
    { slug: 'zz-test-fakename-prefix', display_name: 'Fakename Court', is_active: true },
    {
      slug: 'zz-test-fakename-inactive',
      display_name: 'Fakename Inactive Probe',
      is_active: false,
    },
    { slug: 'zz-test-aliasful', display_name: 'Zz Test Aliasful Judge', is_active: true },
    { slug: 'zz-test-dedup', display_name: 'Zz Test Dedupjudge', is_active: true },
    ...Array.from({ length: 26 }, (_, i) => {
      const nn = String(i + 1).padStart(2, '0');
      return { slug: `zz-test-limit-${nn}`, display_name: `ZZ Test Judge ${nn}`, is_active: true };
    }),
  ];
  // The aliasful judge's decoy alias sorts alphabetically FIRST across its full
  // alias set but does not match q="querytoken" — if matched_alias ever takes
  // min() over all aliases instead of matching ones, the decoy surfaces and the
  // matchedAlias assertions below fail.
  const TEMP_ALIASES: Record<string, string[]> = {
    'zz-test-aliasful': ['aaa decoy alias', 'bbb querytoken alias', 'ccc querytoken alias'],
    'zz-test-dedup': ['dedupjudge alias'],
  };

  let setupDb: Kysely<Database>;
  let app: ReturnType<typeof buildApp>;

  async function deleteTempRows() {
    // Aliases cascade with their judge (FK ON DELETE CASCADE).
    await setupDb
      .deleteFrom('ref.normalized_judges')
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
    const inserted = await setupDb
      .insertInto('ref.normalized_judges')
      .values(TEMP_JUDGES)
      .returning(['id', 'slug'])
      .execute();
    const idBySlug = new Map(inserted.map((row) => [row.slug, row.id]));
    await setupDb
      .insertInto('ref.judge_aliases')
      .values(
        Object.entries(TEMP_ALIASES).flatMap(([slug, aliases]) => {
          const judgeId = idBySlug.get(slug);
          if (!judgeId) throw new Error(`temp judge "${slug}" was not inserted`);
          return aliases.map((alias) => ({ normalized_judge_id: judgeId, alias_text: alias }));
        }),
      )
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

  it('ranks exact above prefix above substring for q="fakename"', async () => {
    expect(await names({ q: 'fakename' })).toEqual([
      'Fakename',
      'Fakename Court',
      'Judge Fakename Example',
    ]);
  });

  it('returns the judge with matchedAlias for an alias-only match', async () => {
    const res = await search({ q: 'T. Placeholder' });
    expect(res.statusCode).toBe(200);
    const { results } = res.json();
    expect(results).toHaveLength(1);
    expect(results[0]).toMatchObject({
      slug: 'judge-testina-placeholder',
      displayName: 'Judge Testina Placeholder',
      matchedAlias: 'T. Placeholder',
    });
  });

  it('matches by substring of the display name without matchedAlias', async () => {
    const res = await search({ q: 'testina' });
    const { results } = res.json();
    expect(results).toHaveLength(1);
    expect(results[0].displayName).toBe('Judge Testina Placeholder');
    expect(results[0]).not.toHaveProperty('matchedAlias');
  });

  it('is case-insensitive for names and aliases', async () => {
    const lower = await search({ q: 'judge fakename' });
    const upper = await search({ q: 'JUDGE FAKENAME' });
    const mixed = await search({ q: 'JuDgE fAkEnAmE' });
    expect(lower.json()).toEqual(upper.json());
    expect(lower.json()).toEqual(mixed.json());
    expect(lower.json().results[0].displayName).toBe('Judge Fakename Example');

    const alias = await search({ q: 'T. PLACEHOLDER' });
    expect(alias.json().results[0].matchedAlias).toBe('T. Placeholder');
  });

  it('dedups a judge whose name and alias both match, without matchedAlias', async () => {
    // "dedupjudge" matches Zz Test Dedupjudge's display name AND its alias
    // "dedupjudge alias" — one row, and the name match suppresses matchedAlias.
    const res = await search({ q: 'dedupjudge' });
    const { results } = res.json();
    expect(results).toHaveLength(1);
    expect(results[0].displayName).toBe('Zz Test Dedupjudge');
    expect(results[0]).not.toHaveProperty('matchedAlias');
  });

  it('populates matchedAlias with the alphabetically first MATCHING alias', async () => {
    // Two aliases match "querytoken"; the alphabetically-first-overall alias
    // ("aaa decoy alias") does not. min() over the full alias set would return
    // the decoy — the endpoint must return the first matching one.
    const res = await search({ q: 'querytoken' });
    const { results } = res.json();
    expect(results).toHaveLength(1);
    expect(results[0].displayName).toBe('Zz Test Aliasful Judge');
    expect(results[0].matchedAlias).toBe('bbb querytoken alias');
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
    const result = await names({ q: 'zz test judge' });
    expect(result).toEqual(
      Array.from({ length: 10 }, (_, i) => `ZZ Test Judge ${String(i + 1).padStart(2, '0')}`),
    );
  });

  it('honors limit up to the maximum of 25', async () => {
    expect(await names({ q: 'zz test judge', limit: '25' })).toHaveLength(25);
    expect(await names({ q: 'zz test judge', limit: '1' })).toEqual(['ZZ Test Judge 01']);
  });

  it('never returns inactive judges', async () => {
    // Direct probe: only the inactive decoy's name contains this phrase.
    expect(await search({ q: 'inactive probe' }).then((r) => r.json())).toEqual({ results: [] });
    // And it must not ride along on the shared "fakename" query either.
    const res = await search({ q: 'fakename' });
    const slugs = res.json().results.map((r: { slug: string }) => r.slug);
    expect(slugs).not.toContain('zz-test-fakename-inactive');
  });

  it('returns exactly the contract keys on a name-match row', async () => {
    const res = await search({ q: 'testina' });
    const { results } = res.json();
    expect(results).toHaveLength(1);
    expect(Object.keys(results[0]).sort()).toEqual(['displayName', 'id', 'slug']);
  });

  it('returns exactly the contract keys on an alias-match row', async () => {
    const res = await search({ q: 'T. Placeholder' });
    const { results } = res.json();
    expect(results).toHaveLength(1);
    expect(Object.keys(results[0]).sort()).toEqual(['displayName', 'id', 'matchedAlias', 'slug']);
  });

  it('exposes only the public contract fields — no statistics or judge metadata', async () => {
    const res = await search({ q: 'T. Placeholder' });
    expect(res.statusCode).toBe(200);
    const body = res.json();
    expect(body.results.length).toBeGreaterThan(0);

    const allowedKeys = new Set(['results', 'id', 'slug', 'displayName', 'matchedAlias']);
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
      'caseCount',
      'resultCount',
      'sampleSize',
      'count',
      'score',
      'rank',
      'percentage',
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
