/**
 * Structural mirror of the API's OpsNumbers payload
 * (apps/api/src/services/ops-numbers.ts) for the operator dashboard. The two
 * apps deliberately share no build dependency, so this is a render-side type:
 * a drifted field renders as a gap on the operator page, never a public
 * defect. Update alongside the API shape.
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
