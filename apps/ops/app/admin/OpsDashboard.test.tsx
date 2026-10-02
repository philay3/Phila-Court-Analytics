import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { OpsDashboard } from './OpsDashboard.js';
import type { OpsNumbers } from './ops-types.js';

function fixture(): OpsNumbers {
  return {
    generatedAt: '2026-07-25T12:00:00.000Z',
    database: 'pca',
    totalMs: 42,
    timings: { corpus: 5, checks: 3 },
    corpus: {
      dockets: 37369,
      docketsByCourt: { CP: 12617, MC: 24752 },
      docketsNullFiledDate: 0,
      filedDateMin: '2023-01-03',
      filedDateMax: '2026-06-30',
      lastLoadedAt: '2026-07-22T22:00:00.000Z',
      charges: 136389,
      chargesInUniverse: 132944,
      chargesPreFloor: 3445,
      chargesSuperseded: 0,
      chargesPending: 51608,
      chargesDisposed: 84781,
      distinctDispositionForms: 60,
      versionPairs: [{ record: 2, envelope: 8, dockets: 37369 }],
      docketsReviewNeeded: 12803,
      cpDocketsWithOriginating: 0,
      chargesWithOrigSeq: 0,
    },
    sourceDocuments: {
      byStatus: { imported: 37369, parse_superseded: 1121 },
      total: 38490,
      totalBytes: 123456789,
      lastImportedAt: '2026-07-22T21:00:00.000Z',
      importedPerDay: [{ day: '2026-07-22', documents: 1121 }],
    },
    linkage: {
      links: 10972,
      resolved: 9552,
      unresolved: 1420,
      byEvidence: { cross_court_dockets: 10972 },
      sourceDockets: 10964,
      supersededPointers: 0,
      unresolvedTargetNumbers: 1400,
    },
    factBuilds: [
      {
        id: 'ddb0fbd9-364d-444f-a342-ac6e6978c309',
        status: 'completed',
        startedAt: '2026-07-22T22:00:00.000Z',
        completedAt: '2026-07-22T22:47:34.000Z',
        counts: { charges_processed: 136389 },
      },
    ],
    aggregateRuns: {
      activePublishedRunId: '9b870800-7ee1-42af-920d-b6ce63b56ab4',
      publishedAt: '2026-07-22T23:00:00.000Z',
      dataRangeStart: '2025-01-01',
      dataRangeEnd: '2026-07-21',
      taxonomyVersion: '1.0.0',
      buildRunId: 'ddb0fbd9-364d-444f-a342-ac6e6978c309',
      recent: [],
      rowsByTable: { charge_volume_aggregates: 78 },
    },
    outcomes: {
      published: {
        totalRecords: 32942,
        byCategory: [
          { category: 'dismissed', count: 13932, share: 42.3 },
          { category: 'guilty_plea', count: 7779, share: 23.6 },
        ],
        dismissedOrWithdrawnShare: 66.4,
      },
      latestBuildPublicFacts: 32942,
      latestBuildByCategory: [{ category: 'dismissed', count: 13932 }],
    },
    charges: {
      rosterActive: 110,
      aliases: 45,
      withOutcomeAggregates: 78,
      withVolumeRows: 78,
      thinOutcomeCharges: 6,
      volumeTotals: {
        chargesSeen: 100000,
        outcomesRecorded: 32942,
        heldForCourt: 12000,
        stillPending: 51608,
        disposedExcluded: 3450,
        heldSuperseded: 29806,
      },
      topByVolume: [
        { slug: 'retail-theft', chargesSeen: 1989, outcomesRecorded: 962, heldSuperseded: 534 },
      ],
      topBySample: [{ slug: 'simple-assault', sampleSize: 3319 }],
    },
    judges: {
      rosterActive: 90,
      aliases: 12,
      withAggregates: 60,
      chargeJudgePairs: 420,
      thinPairs: 300,
      topBySample: [{ slug: 'judge-testina-placeholder', records: 90 }],
    },
    reviewQueue: {
      total: 61751,
      byStatus: { open: 55368, superseded: 6383 },
      openByType: { missing_disposition_date: 50542, unmapped_charge: 2590 },
      openBySeverity: { medium: 55368 },
    },
    warnings: { MISSING_DISPOSITION_DATE: 41798 },
    checks: [
      {
        name: 'one_active_published_run',
        pass: true,
        left: 1,
        right: 1,
        detail: 'exactly one aggregate run is published and active',
      },
      {
        name: 'corpus_unchanged_since_build',
        pass: false,
        left: 137000,
        right: 136389,
        detail: 'live parsed charges vs the latest completed build',
      },
    ],
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('OpsDashboard', () => {
  it('renders every section from a live payload, with pass and fail badges', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify(fixture()), { status: 200 })),
    );
    render(<OpsDashboard />);

    await waitFor(() => expect(screen.getByTestId('refresh-meta')).toBeInTheDocument());

    for (const heading of [
      'Every number accounted for',
      'Corpus',
      'Dedupe & linkage',
      'Source documents & refresh',
      'Fact builds',
      'Aggregate runs',
      'Outcomes & rates',
      'Charges',
      'Judges',
      'Review queue',
      'Parser warnings',
      'Query timings',
    ]) {
      expect(screen.getByRole('heading', { name: heading })).toBeInTheDocument();
    }

    // Numbers render en-US formatted; the dedupe headline is visible.
    expect(screen.getByText('136,389')).toBeInTheDocument();
    expect(screen.getAllByText(/1,989/).length).toBeGreaterThan(0);
    // Check badges are icon + label, never color alone.
    expect(screen.getByText('✓ PASS')).toBeInTheDocument();
    expect(screen.getByText('✕ FAIL')).toBeInTheDocument();
    // The refresh meta line carries the query cost (the dashboard's own rate).
    expect(screen.getByTestId('refresh-meta').textContent).toContain('queries 42 ms');
  });

  it('renders the disabled state on a 404 (flag off / deployed posture)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify({ code: 'NOT_FOUND' }), { status: 404 })),
    );
    render(<OpsDashboard />);
    await waitFor(() => expect(screen.getByText('Ops feed is not enabled.')).toBeInTheDocument());
  });

  it('renders the unreachable state when the proxy cannot reach the API', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () => new Response(JSON.stringify({ error: 'api_unreachable' }), { status: 502 }),
      ),
    );
    render(<OpsDashboard />);
    await waitFor(() => expect(screen.getByText('The API is unreachable.')).toBeInTheDocument());
  });
});
