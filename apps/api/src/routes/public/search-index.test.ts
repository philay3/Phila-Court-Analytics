import { Kysely, PostgresDialect, sql } from 'kysely';
import pg from 'pg';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import {
  SEARCH_INDEX_UNAVAILABLE_MESSAGE,
  type SearchIndexAvailable,
  type SearchIndexResponse,
} from '@pca/shared';
import { formatViolations, scanForForbidden } from '@pca/shared/forbidden-scan';
import { buildApp } from '../../app.js';
import type { PublicApiDatabase } from '../../db.js';

const INDEX_URL = '/api/v1/public/search-index';

// Requires the local database: `pnpm db:up`, migrations applied
// (`pnpm db:migrate:latest`), and DATABASE_URL (root .env is auto-loaded via
// vitest.config.ts). Reference and aggregate seeding happens once for the
// whole run in vitest.global-setup.ts — this suite must not self-seed.
const hasDb = Boolean(process.env.DATABASE_URL);
if (!hasDb) {
  console.warn(
    'DATABASE_URL not set — skipping search-index DB tests. ' +
      'Start Postgres (pnpm db:up), apply migrations (pnpm db:migrate:latest), ' +
      'and create the root .env (cp .env.example .env).',
  );
}

/** Every key path in a JSON body, for the "no id anywhere" assertion. */
function collectKeys(node: unknown, out: string[] = []): string[] {
  if (Array.isArray(node)) {
    for (const item of node) collectKeys(item, out);
  } else if (node !== null && typeof node === 'object') {
    for (const [key, value] of Object.entries(node)) {
      out.push(key);
      collectKeys(value, out);
    }
  }
  return out;
}

/**
 * Contract suite (task STATIC-2a, pin 1). The three set rules are proven by
 * computing each set from the seeded tables with this suite's OWN queries —
 * deliberately formulated differently from the repository (plain selects
 * grouped in JS, no array_agg) — and asserting SET equality with the response
 * (both sides canonicalised by slug). Served ORDER is asserted separately
 * against a SQL query with the stated ORDER BY, because the database collation
 * (en_US.utf8, punctuation-insensitive at the first level) is not JavaScript
 * code-point order. No pinned counts: the roster seeds grow, and the rules
 * must hold regardless.
 *
 * Temp rows (cleaned up before insert and in afterAll): one INACTIVE charge
 * (must be absent — rule 1 says active only) and one ACTIVE charge with an
 * alias and no aggregates (must be present with its alias — rule 1 includes
 * charges without aggregates). The seeds already supply the pair-less active
 * judge (`judge-fakename-example`) and two aggregate-less active charges.
 */
describe.skipIf(!hasDb)('GET /search-index against the seeded database', () => {
  const TEMP_SLUG_PREFIX = 'zz-test-si-';
  const TEMP_INACTIVE = { slug: 'zz-test-si-inactive', display_name: 'ZZ Test SI Inactive' };
  const TEMP_ACTIVE = { slug: 'zz-test-si-active-noagg', display_name: 'ZZ Test SI Active' };
  const TEMP_ALIAS = 'zz test si alias';

  let setupDb: Kysely<PublicApiDatabase>;
  let app: ReturnType<typeof buildApp>;

  async function deleteTempRows() {
    await setupDb.deleteFrom('ref.charge_aliases').where('alias_text', '=', TEMP_ALIAS).execute();
    await setupDb
      .deleteFrom('ref.normalized_charges')
      .where('slug', 'like', `${TEMP_SLUG_PREFIX}%`)
      .execute();
  }

  beforeAll(async () => {
    setupDb = new Kysely<PublicApiDatabase>({
      dialect: new PostgresDialect({
        pool: new pg.Pool({ connectionString: process.env.DATABASE_URL }),
      }),
    });
    await deleteTempRows();
    await setupDb
      .insertInto('ref.normalized_charges')
      .values([
        { ...TEMP_INACTIVE, statute_code: null, grade: null, is_active: false },
        { ...TEMP_ACTIVE, statute_code: null, grade: null, is_active: true },
      ])
      .execute();
    const active = await setupDb
      .selectFrom('ref.normalized_charges')
      .select('id')
      .where('slug', '=', TEMP_ACTIVE.slug)
      .executeTakeFirstOrThrow();
    await setupDb
      .insertInto('ref.charge_aliases')
      .values({ normalized_charge_id: active.id, alias_text: TEMP_ALIAS })
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

  async function getIndex(): Promise<SearchIndexAvailable> {
    const res = await app.inject({ method: 'GET', url: INDEX_URL });
    expect(res.statusCode).toBe(200);
    const body = res.json<SearchIndexResponse>();
    const violations = scanForForbidden(body);
    expect(violations, formatViolations(violations)).toEqual([]);
    if (!body.available) {
      throw new Error('expected the available arm against the seeded database');
    }
    return body;
  }

  async function activeRun() {
    return setupDb
      .selectFrom('analytics.aggregate_runs')
      .select(['id', 'taxonomy_version', 'published_at'])
      .where('published_at', 'is not', null)
      .where('invalidated_at', 'is', null)
      .executeTakeFirstOrThrow();
  }

  // Rule 1 as a query: every active charge, aliases attached in JS.
  async function expectedCharges() {
    const charges = await setupDb
      .selectFrom('ref.normalized_charges')
      .select(['id', 'slug', 'display_name', 'statute_code', 'grade'])
      .where('is_active', '=', true)
      .execute();
    // Alias order is the database's own (ORDER BY alias_text under its
    // collation), preserved by the order-keeping filter below.
    const aliases = await setupDb
      .selectFrom('ref.charge_aliases')
      .select(['normalized_charge_id', 'alias_text'])
      .orderBy('alias_text')
      .execute();
    return charges
      .sort((a, b) => cmp(a.slug, b.slug))
      .map((c) => ({
        slug: c.slug,
        displayName: c.display_name,
        ...(c.statute_code !== null ? { statuteCode: c.statute_code } : {}),
        ...(c.grade !== null ? { grade: c.grade } : {}),
        aliases: aliases.filter((a) => a.normalized_charge_id === c.id).map((a) => a.alias_text),
      }));
  }

  // Rule 3 as a query: distinct (active charge, active judge) with a row.
  async function expectedPairs(runId: string) {
    const rows = await setupDb
      .selectFrom('analytics.judge_outcome_aggregates as joa')
      .innerJoin('ref.normalized_charges as c', 'c.id', 'joa.charge_id')
      .innerJoin('ref.normalized_judges as j', 'j.id', 'joa.judge_id')
      .select(['c.slug as chargeSlug', 'j.slug as judgeSlug'])
      .where('joa.aggregate_run_id', '=', runId)
      .where('c.is_active', '=', true)
      .where('j.is_active', '=', true)
      .execute();
    const distinct = new Map(rows.map((r) => [`${r.chargeSlug}\u0000${r.judgeSlug}`, r]));
    return [...distinct.values()].sort(
      (a, b) => cmp(a.chargeSlug, b.chargeSlug) || cmp(a.judgeSlug, b.judgeSlug),
    );
  }

  // Rule 2 as a query: active judges that appear in the rule-3 pair set.
  async function expectedJudges(runId: string) {
    const pairJudges = new Set((await expectedPairs(runId)).map((p) => p.judgeSlug));
    const judges = await setupDb
      .selectFrom('ref.normalized_judges')
      .select(['id', 'slug', 'display_name'])
      .where('is_active', '=', true)
      .execute();
    const aliases = await setupDb
      .selectFrom('ref.judge_aliases')
      .select(['normalized_judge_id', 'alias_text'])
      .orderBy('alias_text')
      .execute();
    return judges
      .filter((j) => pairJudges.has(j.slug))
      .sort((a, b) => cmp(a.slug, b.slug))
      .map((j) => ({
        slug: j.slug,
        displayName: j.display_name,
        aliases: aliases.filter((a) => a.normalized_judge_id === j.id).map((a) => a.alias_text),
      }));
  }

  it('serves the identity of the run the active-published predicate resolves', async () => {
    const run = await activeRun();
    const body = await getIndex();
    expect(body.aggregateRunId).toBe(run.id);
    expect(body.taxonomyVersion).toBe(run.taxonomy_version);
    expect(body.lastRefreshed).toBe(run.published_at?.toISOString());
  });

  it('rule 1: charges are every active roster charge with aliases, in served order', async () => {
    const body = await getIndex();
    expect([...body.charges].sort((a, b) => cmp(a.slug, b.slug))).toEqual(await expectedCharges());
    // Served order is the database's own: lower(display_name), slug.
    const ordered = await setupDb
      .selectFrom('ref.normalized_charges')
      .select('slug')
      .where('is_active', '=', true)
      .orderBy(sql`lower(display_name)`)
      .orderBy('slug')
      .execute();
    expect(body.charges.map((c) => c.slug)).toEqual(ordered.map((r) => r.slug));

    const slugs = body.charges.map((c) => c.slug);
    // Active charges with NO aggregates are in (volume-only / truly-nothing seeds).
    expect(slugs).toContain('harassment');
    expect(slugs).toContain('open-lewdness');
    expect(slugs).toContain(TEMP_ACTIVE.slug);
    expect(body.charges.find((c) => c.slug === TEMP_ACTIVE.slug)?.aliases).toEqual([TEMP_ALIAS]);
    // Inactive roster rows are out.
    expect(slugs).not.toContain(TEMP_INACTIVE.slug);
    // Seeded alias round-trips on a seeded charge (the roster seeds may add more).
    expect(body.charges.find((c) => c.slug === 'retail-theft')?.aliases).toContain('shoplifting');
  });

  it('rule 2: judges are only those with at least one pair in the active run', async () => {
    const run = await activeRun();
    const body = await getIndex();
    const expected = await expectedJudges(run.id);
    expect([...body.judges].sort((a, b) => cmp(a.slug, b.slug))).toEqual(expected);
    // Served order is the database's own: lower(display_name), slug.
    const ordered = await setupDb
      .selectFrom('ref.normalized_judges')
      .select('slug')
      .where(
        'slug',
        'in',
        expected.map((j) => j.slug),
      )
      .orderBy(sql`lower(display_name)`)
      .orderBy('slug')
      .execute();
    expect(body.judges.map((j) => j.slug)).toEqual(ordered.map((r) => r.slug));

    const slugs = body.judges.map((j) => j.slug);
    // Both ref rows exist, zero aggregate rows: never enumerated.
    expect(slugs).not.toContain('judge-fakename-example');
    expect(slugs).toContain('judge-testina-placeholder');
    // Every listed judge has at least one pair, and every pair's judge is listed.
    const pairJudges = new Set(body.pairs.map((p) => p.judgeSlug));
    expect(new Set(slugs)).toEqual(pairJudges);
  });

  it('rule 3: pairs are the distinct active charge/judge pairs with a judge-specific result', async () => {
    const run = await activeRun();
    const body = await getIndex();
    expect(
      [...body.pairs].sort(
        (a, b) => cmp(a.chargeSlug, b.chargeSlug) || cmp(a.judgeSlug, b.judgeSlug),
      ),
    ).toEqual(await expectedPairs(run.id));
    expect(body.pairs.length).toBeGreaterThan(0);
    // Served order is the database's own: charge slug, then judge slug.
    const ordered = await setupDb
      .selectFrom('analytics.judge_outcome_aggregates as joa')
      .innerJoin('ref.normalized_charges as c', 'c.id', 'joa.charge_id')
      .innerJoin('ref.normalized_judges as j', 'j.id', 'joa.judge_id')
      .select(['c.slug as chargeSlug', 'j.slug as judgeSlug'])
      .distinct()
      .where('joa.aggregate_run_id', '=', run.id)
      .where('c.is_active', '=', true)
      .where('j.is_active', '=', true)
      .orderBy('c.slug')
      .orderBy('j.slug')
      .execute();
    expect(body.pairs).toEqual(ordered);
    // Closure: every pair references an enumerated charge and judge.
    const chargeSlugs = new Set(body.charges.map((c) => c.slug));
    const judgeSlugs = new Set(body.judges.map((j) => j.slug));
    for (const pair of body.pairs) {
      expect(chargeSlugs.has(pair.chargeSlug), `pair charge ${pair.chargeSlug}`).toBe(true);
      expect(judgeSlugs.has(pair.judgeSlug), `pair judge ${pair.judgeSlug}`).toBe(true);
    }
  });

  it('carries no id anywhere in the payload (slugs are the only keys)', async () => {
    const body = await getIndex();
    const keys = collectKeys(body);
    expect(keys.filter((k) => k === 'id' || k.endsWith('Id') || k.endsWith('_id'))).toEqual([
      // The only sanctioned run reference, shared with the result payloads.
      'aggregateRunId',
    ]);
  });

  it('excludes an inactive judge and its pair, and includes it once active (rolled back)', async () => {
    // Isolation: the fixture lives inside an uncommitted transaction and the
    // app under test is built on that connection, so other suites never see
    // a changed pair count; the rollback in finally guarantees it.
    const run = await activeRun();
    const trx = await setupDb.startTransaction().execute();
    try {
      const charge = await trx
        .selectFrom('ref.normalized_charges')
        .select('id')
        .where('slug', '=', 'retail-theft')
        .executeTakeFirstOrThrow();
      const judge = await trx
        .insertInto('ref.normalized_judges')
        .values({ slug: 'zz-test-si-judge', display_name: 'ZZ Test SI Judge', is_active: false })
        .returning('id')
        .executeTakeFirstOrThrow();
      await trx
        .insertInto('analytics.judge_outcome_aggregates')
        .values({
          aggregate_run_id: run.id,
          charge_id: charge.id,
          judge_id: judge.id,
          category_code: 'dismissed',
          count: 1,
          percentage: 100,
          sample_size: 1,
          date_range_start: '2025-01-01',
          date_range_end: '2025-01-31',
          is_thin_data: true,
          taxonomy_version: run.taxonomy_version,
        })
        .execute();

      const trxApp = buildApp({ logger: false, db: trx });
      try {
        const inactive = (
          await trxApp.inject({ method: 'GET', url: INDEX_URL })
        ).json<SearchIndexResponse>();
        if (!inactive.available) throw new Error('expected the available arm');
        expect(inactive.judges.map((j) => j.slug)).not.toContain('zz-test-si-judge');
        expect(inactive.pairs.some((p) => p.judgeSlug === 'zz-test-si-judge')).toBe(false);

        await trx
          .updateTable('ref.normalized_judges')
          .set({ is_active: true })
          .where('id', '=', judge.id)
          .execute();
        const active = (
          await trxApp.inject({ method: 'GET', url: INDEX_URL })
        ).json<SearchIndexResponse>();
        if (!active.available) throw new Error('expected the available arm');
        expect(active.judges.map((j) => j.slug)).toContain('zz-test-si-judge');
        expect(active.pairs).toContainEqual({
          chargeSlug: 'retail-theft',
          judgeSlug: 'zz-test-si-judge',
        });
      } finally {
        await trxApp.close();
      }
    } finally {
      await trx.rollback().execute();
    }
  });

  it('returns 200 with the unavailable arm when no active published run exists (rolled back)', async () => {
    const trx = await setupDb.startTransaction().execute();
    try {
      await trx
        .updateTable('analytics.aggregate_runs')
        .set({
          invalidated_at: new Date(),
          invalidated_reason: 'task STATIC-2a unavailable-arm test (rolled back)',
        })
        .where('published_at', 'is not', null)
        .where('invalidated_at', 'is', null)
        .execute();

      const trxApp = buildApp({ logger: false, db: trx });
      try {
        const res = await trxApp.inject({ method: 'GET', url: INDEX_URL });
        expect(res.statusCode).toBe(200);
        expect(res.json()).toEqual({
          available: false,
          message: SEARCH_INDEX_UNAVAILABLE_MESSAGE,
        });
      } finally {
        await trxApp.close();
      }
    } finally {
      await trx.rollback().execute();
    }

    // The shared seeded state is untouched after the rollback.
    expect((await getIndex()).available).toBe(true);
  });
});

function cmp(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}
