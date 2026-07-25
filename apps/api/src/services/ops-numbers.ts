import { sql, type Kysely } from 'kysely';
import type { OpsDatabase } from '../ops-db.js';

/**
 * The ops dashboard's single read (Phase 36): every operational number on the
 * canonical database, in one payload, with per-section query timing so the
 * dashboard can show its own cost. Counts, codes, statuses, slugs, and run
 * ids ONLY — never docket numbers, defendant hashes, captured docket text, or
 * review-queue payload values (`raw_value` / `candidate_context` are never
 * selected). Read-only by construction: SELECTs alone.
 *
 * Live-vs-published discipline: sections that read `parsed.*` / `review.*` /
 * `raw.*` are live snapshots at request time; sections that read `analytics.*`
 * are pinned to the ACTIVE PUBLISHED run; fact sections are pinned to the
 * LATEST COMPLETED build. Each section says which it is via its name — the
 * dashboard labels them accordingly.
 *
 * The `checks` section is the "every number accounted for" panel: each entry
 * re-computes an identity the pipeline relies on (closure, one-active-published,
 * funnel-vs-percentages, sum consistency) and reports pass/fail with both
 * sides of the equation, so a drifted corpus or a broken invariant is visible
 * at a glance instead of buried in a report.
 */

export interface OpsCheck {
  name: string;
  pass: boolean;
  left: number;
  right: number;
  detail: string;
}

export interface OpsNumbers {
  generatedAt: string;
  database: string;
  totalMs: number;
  timings: Record<string, number>;
  corpus: {
    dockets: number;
    docketsByCourt: Record<string, number>;
    docketsNullFiledDate: number;
    filedDateMin: string | null;
    filedDateMax: string | null;
    lastLoadedAt: string | null;
    charges: number;
    chargesInUniverse: number;
    chargesPreFloor: number;
    chargesSuperseded: number;
    chargesPending: number;
    chargesDisposed: number;
    distinctDispositionForms: number;
    versionPairs: Array<{ record: number; envelope: number; dockets: number }>;
    docketsReviewNeeded: number;
    cpDocketsWithOriginating: number;
    chargesWithOrigSeq: number;
  };
  sourceDocuments: {
    byStatus: Record<string, number>;
    total: number;
    totalBytes: number;
    lastImportedAt: string | null;
    importedPerDay: Array<{ day: string; documents: number }>;
  };
  linkage: {
    links: number;
    resolved: number;
    unresolved: number;
    byEvidence: Record<string, number>;
    sourceDockets: number;
    supersededPointers: number;
    unresolvedTargetNumbers: number;
  };
  factBuilds: Array<{
    id: string;
    status: string;
    startedAt: string;
    completedAt: string | null;
    counts: unknown;
  }>;
  aggregateRuns: {
    activePublishedRunId: string | null;
    publishedAt: string | null;
    dataRangeStart: string | null;
    dataRangeEnd: string | null;
    taxonomyVersion: string | null;
    buildRunId: string | null;
    recent: Array<{
      id: string;
      status: string;
      startedAt: string;
      publishedAt: string | null;
      invalidatedAt: string | null;
      buildRunId: string | null;
    }>;
    rowsByTable: Record<string, number>;
  };
  outcomes: {
    published: {
      totalRecords: number;
      byCategory: Array<{ category: string; count: number; share: number }>;
      dismissedOrWithdrawnShare: number | null;
    };
    latestBuildPublicFacts: number;
    latestBuildByCategory: Array<{ category: string; count: number }>;
  };
  charges: {
    rosterActive: number;
    aliases: number;
    withOutcomeAggregates: number;
    withVolumeRows: number;
    thinOutcomeCharges: number;
    volumeTotals: {
      chargesSeen: number;
      outcomesRecorded: number;
      heldForCourt: number;
      stillPending: number;
      disposedExcluded: number;
      heldSuperseded: number;
    } | null;
    topByVolume: Array<{
      slug: string;
      chargesSeen: number;
      outcomesRecorded: number;
      heldSuperseded: number;
    }>;
    topBySample: Array<{ slug: string; sampleSize: number }>;
  };
  judges: {
    rosterActive: number;
    aliases: number;
    withAggregates: number;
    chargeJudgePairs: number;
    thinPairs: number;
    topBySample: Array<{ slug: string; records: number }>;
  };
  reviewQueue: {
    total: number;
    byStatus: Record<string, number>;
    openByType: Record<string, number>;
    openBySeverity: Record<string, number>;
  };
  warnings: Record<string, number>;
  checks: OpsCheck[];
}

type Db = Kysely<OpsDatabase>;

const num = (value: unknown): number => Number(value ?? 0);
const iso = (value: unknown): string | null =>
  value instanceof Date
    ? value.toISOString()
    : value === null || value === undefined
      ? null
      : String(value);

async function timed<T>(
  timings: Record<string, number>,
  name: string,
  fn: () => Promise<T>,
): Promise<T> {
  const start = performance.now();
  try {
    return await fn();
  } finally {
    timings[name] = Math.round(performance.now() - start);
  }
}

export async function getOpsNumbers(db: Db): Promise<OpsNumbers> {
  const overallStart = performance.now();
  const timings: Record<string, number> = {};

  const database = await timed(timings, 'meta', async () => {
    const row = await sql<{ db: string }>`SELECT current_database() AS db`.execute(db);
    return row.rows[0]?.db ?? 'unknown';
  });

  const corpus = await timed(timings, 'corpus', async () => {
    const docketAgg = await db
      .selectFrom('parsed.dockets')
      .select((eb) => [
        eb.fn.countAll().as('dockets'),
        eb.fn
          .count(sql`*`)
          .filterWhere('filed_date', 'is', null)
          .as('null_filed'),
        eb.fn
          .count(sql`*`)
          .filterWhere('review_needed', '=', true)
          .as('review_needed'),
        eb.fn
          .count(sql`*`)
          .filterWhere('originating_docket_no', 'is not', null)
          .as('with_originating'),
        sql<string | null>`min(filed_date)::text`.as('filed_min'),
        sql<string | null>`max(filed_date)::text`.as('filed_max'),
        sql<Date | null>`max(loaded_at)`.as('last_loaded'),
      ])
      .executeTakeFirstOrThrow();
    const byCourtRows = await db
      .selectFrom('parsed.dockets')
      .select(['court_type_derived', (eb) => eb.fn.countAll().as('n')])
      .groupBy('court_type_derived')
      .execute();
    const chargeAgg = await db
      .selectFrom('parsed.charges as c')
      .leftJoin('parsed.dockets as d', 'd.id', 'c.docket_id')
      .select((eb) => [
        eb.fn.countAll().as('charges'),
        eb.fn
          .count(sql`*`)
          .filterWhere(sql<boolean>`d.filed_date IS NOT NULL AND d.filed_date >= '2025-01-01'`)
          .as('in_universe'),
        eb.fn
          .count(sql`*`)
          .filterWhere('c.superseded_by_charge_id', 'is not', null)
          .as('superseded'),
        eb.fn
          .count(sql`*`)
          .filterWhere('c.disposition_raw', 'is', null)
          .as('pending'),
        eb.fn
          .count(sql`*`)
          .filterWhere('c.orig_seq', 'is not', null)
          .as('with_orig_seq'),
        sql<string>`count(DISTINCT c.disposition_raw)`.as('distinct_forms'),
      ])
      .executeTakeFirstOrThrow();
    const versionRows = await db
      .selectFrom('parsed.dockets')
      .select([
        'record_parser_version',
        'envelope_parser_version',
        (eb) => eb.fn.countAll().as('n'),
      ])
      .groupBy(['record_parser_version', 'envelope_parser_version'])
      .orderBy('record_parser_version')
      .orderBy('envelope_parser_version')
      .execute();
    const charges = num(chargeAgg.charges);
    const inUniverse = num(chargeAgg.in_universe);
    return {
      dockets: num(docketAgg.dockets),
      docketsByCourt: Object.fromEntries(
        byCourtRows.map((row) => [row.court_type_derived ?? 'unknown', num(row.n)]),
      ),
      docketsNullFiledDate: num(docketAgg.null_filed),
      filedDateMin: docketAgg.filed_min,
      filedDateMax: docketAgg.filed_max,
      lastLoadedAt: iso(docketAgg.last_loaded),
      charges,
      chargesInUniverse: inUniverse,
      chargesPreFloor: charges - inUniverse,
      chargesSuperseded: num(chargeAgg.superseded),
      chargesPending: num(chargeAgg.pending),
      chargesDisposed: charges - num(chargeAgg.pending),
      distinctDispositionForms: num(chargeAgg.distinct_forms),
      versionPairs: versionRows.map((row) => ({
        record: row.record_parser_version,
        envelope: row.envelope_parser_version,
        dockets: num(row.n),
      })),
      docketsReviewNeeded: num(docketAgg.review_needed),
      cpDocketsWithOriginating: num(docketAgg.with_originating),
      chargesWithOrigSeq: num(chargeAgg.with_orig_seq),
    };
  });

  const sourceDocuments = await timed(timings, 'sourceDocuments', async () => {
    const statusRows = await db
      .selectFrom('raw.source_documents')
      .select([
        'status',
        (eb) => eb.fn.countAll().as('n'),
        sql<string>`sum(file_size_bytes)`.as('bytes'),
      ])
      .groupBy('status')
      .execute();
    const lastRow = await db
      .selectFrom('raw.source_documents')
      .select(sql<Date | null>`max(imported_at)`.as('last'))
      .executeTakeFirst();
    const perDay = await db
      .selectFrom('raw.source_documents')
      .select([
        sql<string>`date_trunc('day', imported_at)::date::text`.as('day'),
        sql<string>`count(*)`.as('n'),
      ])
      .where(sql<boolean>`imported_at >= now() - interval '14 days'`)
      .groupBy(sql`date_trunc('day', imported_at)`)
      .orderBy(sql`date_trunc('day', imported_at)`)
      .execute();
    return {
      byStatus: Object.fromEntries(statusRows.map((row) => [row.status, num(row.n)])),
      total: statusRows.reduce((sum, row) => sum + num(row.n), 0),
      totalBytes: statusRows.reduce((sum, row) => sum + num(row.bytes), 0),
      lastImportedAt: iso(lastRow?.last),
      importedPerDay: perDay.map((row) => ({ day: row.day, documents: num(row.n) })),
    };
  });

  const linkage = await timed(timings, 'linkage', async () => {
    const linkAgg = await db
      .selectFrom('parsed.docket_links')
      .select((eb) => [
        eb.fn.countAll().as('links'),
        eb.fn
          .count(sql`*`)
          .filterWhere('target_docket_id', 'is not', null)
          .as('resolved'),
        sql<string>`count(DISTINCT source_docket_id)`.as('sources'),
        sql<string>`count(DISTINCT target_docket_number) FILTER (WHERE target_docket_id IS NULL)`.as(
          'unresolved_numbers',
        ),
      ])
      .executeTakeFirstOrThrow();
    const evidenceRows = await db
      .selectFrom('parsed.docket_links')
      .select(['evidence_source', (eb) => eb.fn.countAll().as('n')])
      .groupBy('evidence_source')
      .execute();
    const superseded = await db
      .selectFrom('parsed.charges')
      .select((eb) => eb.fn.countAll().as('n'))
      .where('superseded_by_charge_id', 'is not', null)
      .executeTakeFirstOrThrow();
    return {
      links: num(linkAgg.links),
      resolved: num(linkAgg.resolved),
      unresolved: num(linkAgg.links) - num(linkAgg.resolved),
      byEvidence: Object.fromEntries(evidenceRows.map((row) => [row.evidence_source, num(row.n)])),
      sourceDockets: num(linkAgg.sources),
      supersededPointers: num(superseded.n),
      unresolvedTargetNumbers: num(linkAgg.unresolved_numbers),
    };
  });

  const factBuilds = await timed(timings, 'factBuilds', async () => {
    const rows = await db
      .selectFrom('fact.fact_build_runs')
      .select(['id', 'status', 'started_at', 'completed_at', 'counts'])
      .orderBy('started_at', 'desc')
      .limit(5)
      .execute();
    return rows.map((row) => ({
      id: row.id,
      status: row.status,
      startedAt: iso(row.started_at) ?? '',
      completedAt: iso(row.completed_at),
      counts: row.counts,
    }));
  });

  const aggregateRuns = await timed(timings, 'aggregateRuns', async () => {
    const active = await db
      .selectFrom('analytics.aggregate_runs')
      .where('published_at', 'is not', null)
      .where('invalidated_at', 'is', null)
      .select([
        'id',
        'published_at',
        'taxonomy_version',
        'build_run_id',
        sql<string>`data_range_start::text`.as('range_start'),
        sql<string>`data_range_end::text`.as('range_end'),
      ])
      .orderBy('published_at', 'desc')
      .limit(1)
      .executeTakeFirst();
    const recent = await db
      .selectFrom('analytics.aggregate_runs')
      .select(['id', 'status', 'started_at', 'published_at', 'invalidated_at', 'build_run_id'])
      .orderBy('started_at', 'desc')
      .limit(6)
      .execute();

    const rowsByTable: Record<string, number> = {};
    if (active) {
      const tables = [
        'analytics.charge_outcome_aggregates',
        'analytics.charge_sentencing_aggregates',
        'analytics.judge_outcome_aggregates',
        'analytics.judge_sentencing_aggregates',
        'analytics.charge_sentencing_index_summaries',
        'analytics.charge_sentencing_index_aggregates',
        'analytics.charge_conviction_grade_aggregates',
        'analytics.judge_sentencing_index_summaries',
        'analytics.judge_sentencing_index_aggregates',
        'analytics.charge_volume_aggregates',
      ] as const;
      for (const table of new Set(tables)) {
        const row = await db
          .selectFrom(table)
          .select((eb) => eb.fn.countAll().as('n'))
          .where('aggregate_run_id', '=', active.id)
          .executeTakeFirstOrThrow();
        rowsByTable[table.replace('analytics.', '')] = num(row.n);
      }
    }
    return {
      activePublishedRunId: active?.id ?? null,
      publishedAt: iso(active?.published_at),
      dataRangeStart: active?.range_start ?? null,
      dataRangeEnd: active?.range_end ?? null,
      taxonomyVersion: active?.taxonomy_version ?? null,
      buildRunId: active?.build_run_id ?? null,
      recent: recent.map((row) => ({
        id: row.id,
        status: row.status,
        startedAt: iso(row.started_at) ?? '',
        publishedAt: iso(row.published_at),
        invalidatedAt: iso(row.invalidated_at),
        buildRunId: row.build_run_id,
      })),
      rowsByTable,
    };
  });

  const activeRunId = aggregateRuns.activePublishedRunId;

  const outcomes = await timed(timings, 'outcomes', async () => {
    let byCategory: Array<{ category: string; count: number; share: number }> = [];
    let totalRecords = 0;
    let dismissedOrWithdrawnShare: number | null = null;
    if (activeRunId) {
      const categoryRows = await db
        .selectFrom('analytics.charge_outcome_aggregates')
        .select(['category_code', sql<string>`sum(count)`.as('n')])
        .where('aggregate_run_id', '=', activeRunId)
        .groupBy('category_code')
        .orderBy(sql`sum(count)`, 'desc')
        .execute();
      totalRecords = categoryRows.reduce((sum, row) => sum + num(row.n), 0);
      byCategory = categoryRows.map((row) => ({
        category: row.category_code,
        count: num(row.n),
        share: totalRecords > 0 ? Math.round((num(row.n) / totalRecords) * 1000) / 10 : 0,
      }));
      const dw = byCategory
        .filter((row) => row.category === 'dismissed' || row.category === 'withdrawn')
        .reduce((sum, row) => sum + row.count, 0);
      dismissedOrWithdrawnShare =
        totalRecords > 0 ? Math.round((dw / totalRecords) * 1000) / 10 : null;
    }

    const latestBuild = await db
      .selectFrom('fact.fact_build_runs')
      .select('id')
      .where('status', '=', 'completed')
      .orderBy('completed_at', 'desc')
      .limit(1)
      .executeTakeFirst();
    let latestBuildByCategory: Array<{ category: string; count: number }> = [];
    let latestBuildPublicFacts = 0;
    if (latestBuild) {
      const factRows = await db
        .selectFrom('fact.charge_outcomes')
        .select(['outcome_category_code', sql<string>`count(*)`.as('n')])
        .where('build_run_id', '=', latestBuild.id)
        .where('public_eligible', '=', true)
        .groupBy('outcome_category_code')
        .orderBy(sql`count(*)`, 'desc')
        .execute();
      latestBuildByCategory = factRows.map((row) => ({
        category: row.outcome_category_code,
        count: num(row.n),
      }));
      latestBuildPublicFacts = latestBuildByCategory.reduce((sum, row) => sum + row.count, 0);
    }
    return {
      published: { totalRecords, byCategory, dismissedOrWithdrawnShare },
      latestBuildPublicFacts,
      latestBuildByCategory,
    };
  });

  const charges = await timed(timings, 'charges', async () => {
    const roster = await db
      .selectFrom('ref.normalized_charges')
      .select((eb) => [eb.fn.countAll().filterWhere('is_active', '=', true).as('active')])
      .executeTakeFirstOrThrow();
    const aliases = await db
      .selectFrom('ref.charge_aliases')
      .select((eb) => eb.fn.countAll().as('n'))
      .executeTakeFirstOrThrow();

    let withOutcomeAggregates = 0;
    let withVolumeRows = 0;
    let thinOutcomeCharges = 0;
    let volumeTotals: OpsNumbers['charges']['volumeTotals'] = null;
    let topByVolume: OpsNumbers['charges']['topByVolume'] = [];
    let topBySample: OpsNumbers['charges']['topBySample'] = [];
    if (activeRunId) {
      const agg = await db
        .selectFrom('analytics.charge_outcome_aggregates')
        .select([
          sql<string>`count(DISTINCT charge_id)`.as('charges'),
          sql<string>`count(DISTINCT charge_id) FILTER (WHERE is_thin_data)`.as('thin'),
        ])
        .where('aggregate_run_id', '=', activeRunId)
        .executeTakeFirstOrThrow();
      withOutcomeAggregates = num(agg.charges);
      thinOutcomeCharges = num(agg.thin);

      const volumeAgg = await db
        .selectFrom('analytics.charge_volume_aggregates')
        .select([
          sql<string>`count(*)`.as('rows'),
          sql<string>`coalesce(sum(charges_seen), 0)`.as('seen'),
          sql<string>`coalesce(sum(outcomes_recorded), 0)`.as('outcomes'),
          sql<string>`coalesce(sum(held_for_court), 0)`.as('held'),
          sql<string>`coalesce(sum(still_pending), 0)`.as('pending'),
          sql<string>`coalesce(sum(disposed_excluded), 0)`.as('excluded'),
          sql<string>`coalesce(sum(held_superseded), 0)`.as('superseded'),
        ])
        .where('aggregate_run_id', '=', activeRunId)
        .executeTakeFirstOrThrow();
      withVolumeRows = num(volumeAgg.rows);
      if (withVolumeRows > 0) {
        volumeTotals = {
          chargesSeen: num(volumeAgg.seen),
          outcomesRecorded: num(volumeAgg.outcomes),
          heldForCourt: num(volumeAgg.held),
          stillPending: num(volumeAgg.pending),
          disposedExcluded: num(volumeAgg.excluded),
          heldSuperseded: num(volumeAgg.superseded),
        };
      }
      topByVolume = (
        await db
          .selectFrom('analytics.charge_volume_aggregates as v')
          .innerJoin('ref.normalized_charges as c', 'c.id', 'v.charge_id')
          .select(['c.slug', 'v.charges_seen', 'v.outcomes_recorded', 'v.held_superseded'])
          .where('v.aggregate_run_id', '=', activeRunId)
          .orderBy('v.charges_seen', 'desc')
          .limit(12)
          .execute()
      ).map((row) => ({
        slug: row.slug,
        chargesSeen: row.charges_seen,
        outcomesRecorded: row.outcomes_recorded,
        heldSuperseded: row.held_superseded,
      }));
      topBySample = (
        await db
          .selectFrom('analytics.charge_outcome_aggregates as a')
          .innerJoin('ref.normalized_charges as c', 'c.id', 'a.charge_id')
          .select(['c.slug', sql<string>`max(a.sample_size)`.as('sample')])
          .where('a.aggregate_run_id', '=', activeRunId)
          .groupBy('c.slug')
          .orderBy(sql`max(a.sample_size)`, 'desc')
          .limit(12)
          .execute()
      ).map((row) => ({ slug: row.slug, sampleSize: num(row.sample) }));
    }
    return {
      rosterActive: num(roster.active),
      aliases: num(aliases.n),
      withOutcomeAggregates,
      withVolumeRows,
      thinOutcomeCharges,
      volumeTotals,
      topByVolume,
      topBySample,
    };
  });

  const judges = await timed(timings, 'judges', async () => {
    const roster = await db
      .selectFrom('ref.normalized_judges')
      .select((eb) => [eb.fn.countAll().filterWhere('is_active', '=', true).as('active')])
      .executeTakeFirstOrThrow();
    const aliases = await db
      .selectFrom('ref.judge_aliases')
      .select((eb) => eb.fn.countAll().as('n'))
      .executeTakeFirstOrThrow();
    let withAggregates = 0;
    let chargeJudgePairs = 0;
    let thinPairs = 0;
    let topBySample: OpsNumbers['judges']['topBySample'] = [];
    if (activeRunId) {
      const agg = await db
        .selectFrom('analytics.judge_outcome_aggregates')
        .select([
          sql<string>`count(DISTINCT judge_id)`.as('judges'),
          sql<string>`count(DISTINCT (charge_id, judge_id))`.as('pairs'),
          sql<string>`count(DISTINCT (charge_id, judge_id)) FILTER (WHERE is_thin_data)`.as('thin'),
        ])
        .where('aggregate_run_id', '=', activeRunId)
        .executeTakeFirstOrThrow();
      withAggregates = num(agg.judges);
      chargeJudgePairs = num(agg.pairs);
      thinPairs = num(agg.thin);
      topBySample = (
        await db
          .selectFrom('analytics.judge_outcome_aggregates as a')
          .innerJoin('ref.normalized_judges as j', 'j.id', 'a.judge_id')
          .select(['j.slug', sql<string>`sum(a.count)`.as('records')])
          .where('a.aggregate_run_id', '=', activeRunId)
          .groupBy('j.slug')
          .orderBy(sql`sum(a.count)`, 'desc')
          .limit(10)
          .execute()
      ).map((row) => ({ slug: row.slug, records: num(row.records) }));
    }
    return {
      rosterActive: num(roster.active),
      aliases: num(aliases.n),
      withAggregates,
      chargeJudgePairs,
      thinPairs,
      topBySample,
    };
  });

  const reviewQueue = await timed(timings, 'reviewQueue', async () => {
    const statusRows = await db
      .selectFrom('review.queue_items')
      .select(['status', (eb) => eb.fn.countAll().as('n')])
      .groupBy('status')
      .execute();
    const typeRows = await db
      .selectFrom('review.queue_items')
      .select(['item_type', (eb) => eb.fn.countAll().as('n')])
      .where('status', '=', 'open')
      .groupBy('item_type')
      .orderBy(sql`count(*)`, 'desc')
      .execute();
    const severityRows = await db
      .selectFrom('review.queue_items')
      .select(['severity', (eb) => eb.fn.countAll().as('n')])
      .where('status', '=', 'open')
      .groupBy('severity')
      .execute();
    return {
      total: statusRows.reduce((sum, row) => sum + num(row.n), 0),
      byStatus: Object.fromEntries(statusRows.map((row) => [row.status, num(row.n)])),
      openByType: Object.fromEntries(typeRows.map((row) => [row.item_type, num(row.n)])),
      openBySeverity: Object.fromEntries(severityRows.map((row) => [row.severity, num(row.n)])),
    };
  });

  const warnings = await timed(timings, 'warnings', async () => {
    const rows = await db
      .selectFrom('parsed.warnings')
      .select(['code', (eb) => eb.fn.countAll().as('n')])
      .groupBy('code')
      .orderBy(sql`count(*)`, 'desc')
      .execute();
    return Object.fromEntries(rows.map((row) => [row.code, num(row.n)]));
  });

  const checks = await timed(timings, 'checks', async () => {
    const results: OpsCheck[] = [];

    const activeCount = await db
      .selectFrom('analytics.aggregate_runs')
      .select((eb) => eb.fn.countAll().as('n'))
      .where('published_at', 'is not', null)
      .where('invalidated_at', 'is', null)
      .executeTakeFirstOrThrow();
    results.push({
      name: 'one_active_published_run',
      pass: num(activeCount.n) === 1,
      left: num(activeCount.n),
      right: 1,
      detail: 'exactly one aggregate run is published and active',
    });

    if (activeRunId) {
      const closure = await db
        .selectFrom('analytics.charge_volume_aggregates')
        .select((eb) => eb.fn.countAll().as('n'))
        .where('aggregate_run_id', '=', activeRunId)
        .where(
          sql<boolean>`outcomes_recorded + held_for_court + still_pending + disposed_excluded <> charges_seen`,
        )
        .executeTakeFirstOrThrow();
      results.push({
        name: 'volume_closure',
        pass: num(closure.n) === 0,
        left: num(closure.n),
        right: 0,
        detail: 'volume rows whose stages do not sum to charges_seen',
      });

      const volumeMismatch = await db
        .selectFrom('analytics.charge_volume_aggregates as v')
        .leftJoin(
          (eb) =>
            eb
              .selectFrom('analytics.charge_outcome_aggregates')
              .select(['charge_id', sql<string>`max(sample_size)`.as('sample')])
              .where('aggregate_run_id', '=', activeRunId)
              .groupBy('charge_id')
              .as('o'),
          (join) => join.onRef('o.charge_id', '=', 'v.charge_id'),
        )
        .select((eb) => eb.fn.countAll().as('n'))
        .where('v.aggregate_run_id', '=', activeRunId)
        .where(sql<boolean>`v.outcomes_recorded <> coalesce(o.sample::int, 0)`)
        .executeTakeFirstOrThrow();
      results.push({
        name: 'volume_matches_percentages',
        pass: num(volumeMismatch.n) === 0,
        left: num(volumeMismatch.n),
        right: 0,
        detail: 'volume rows disagreeing with the outcome sample size',
      });

      const sampleMismatch = await db
        .selectFrom((eb) =>
          eb
            .selectFrom('analytics.charge_outcome_aggregates')
            .select([
              'charge_id',
              sql<string>`sum(count)`.as('total'),
              sql<string>`max(sample_size)`.as('sample'),
            ])
            .where('aggregate_run_id', '=', activeRunId)
            .groupBy('charge_id')
            .as('g'),
        )
        .select((eb) => eb.fn.countAll().as('n'))
        .where(sql<boolean>`g.total <> g.sample`)
        .executeTakeFirstOrThrow();
      results.push({
        name: 'outcome_counts_sum_to_sample',
        pass: num(sampleMismatch.n) === 0,
        left: num(sampleMismatch.n),
        right: 0,
        detail: 'charges whose outcome counts do not sum to their sample size',
      });

      const wedge = await db
        .selectFrom('analytics.charge_sentencing_index_summaries')
        .select((eb) => eb.fn.countAll().as('n'))
        .where('aggregate_run_id', '=', activeRunId)
        .where(sql<boolean>`sentenced_convictions + wedge_count <> convictions`)
        .executeTakeFirstOrThrow();
      results.push({
        name: 'wedge_identity',
        pass: num(wedge.n) === 0,
        left: num(wedge.n),
        right: 0,
        detail: 'index summaries violating sentenced + wedge = convictions',
      });
    }

    const latestBuild = factBuilds.find((run) => run.status === 'completed');
    if (latestBuild && typeof latestBuild.counts === 'object' && latestBuild.counts !== null) {
      const counts = latestBuild.counts as Record<string, unknown>;
      const processed = num(counts.charges_processed);
      if (processed > 0) {
        results.push({
          name: 'corpus_unchanged_since_build',
          pass: corpus.charges === processed,
          left: corpus.charges,
          right: processed,
          detail:
            'live parsed charges vs the latest completed build (a mismatch means the corpus moved; rebuild before generating)',
        });
      }
    }

    const selfPointer = await db
      .selectFrom('parsed.charges')
      .select((eb) => eb.fn.countAll().as('n'))
      .where(sql<boolean>`superseded_by_charge_id = id`)
      .executeTakeFirstOrThrow();
    results.push({
      name: 'no_self_supersession',
      pass: num(selfPointer.n) === 0,
      left: num(selfPointer.n),
      right: 0,
      detail: 'charges pointing at themselves as their own continuation',
    });

    return results;
  });

  return {
    generatedAt: new Date().toISOString(),
    database,
    totalMs: Math.round(performance.now() - overallStart),
    timings,
    corpus,
    sourceDocuments,
    linkage,
    factBuilds,
    aggregateRuns,
    outcomes,
    charges,
    judges,
    reviewQueue,
    warnings,
    checks,
  };
}
