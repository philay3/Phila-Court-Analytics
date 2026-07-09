import type { Kysely } from 'kysely';
import {
  DATA_COVERAGE_COURT_SCOPE,
  DATA_COVERAGE_JURISDICTION,
  DATA_COVERAGE_PLANNED_DATA_START,
  DATA_COVERAGE_UNAVAILABLE_MESSAGE,
  type DataCoverageResponse,
} from '@pca/shared';
import type { PublicApiDatabase } from '../db.js';
import { DATA_COVERAGE_KNOWN_LIMITATIONS } from '../content/data-coverage.js';
import { findActivePublishedRun } from '../repositories/charge-result.js';
import { getCoverageCounts } from '../repositories/data-coverage.js';

function commonFields(): Omit<DataCoverageResponse, 'coverage'> {
  return {
    jurisdiction: DATA_COVERAGE_JURISDICTION,
    courtScope: DATA_COVERAGE_COURT_SCOPE,
    plannedDataStart: DATA_COVERAGE_PLANNED_DATA_START,
    knownLimitations: [...DATA_COVERAGE_KNOWN_LIMITATIONS],
  };
}

/**
 * Public data-coverage report. Reuses the 8.1 active-published-run resolver
 * (never a second one); "no active published run" is the unavailable arm of
 * an HTTP-200 tagged union (Phase 8 standing decision), not an error.
 * Unexpected failures fall through to the central handler as INTERNAL_ERROR.
 */
export async function getDataCoverage(
  getDb: () => Kysely<PublicApiDatabase>,
): Promise<DataCoverageResponse> {
  const db = getDb();

  const run = await findActivePublishedRun(db);
  if (!run) {
    return {
      ...commonFields(),
      coverage: { available: false, message: DATA_COVERAGE_UNAVAILABLE_MESSAGE },
    };
  }

  return {
    ...commonFields(),
    coverage: {
      available: true,
      dataStart: run.data_range_start,
      dataEnd: run.data_range_end,
      lastRefreshed: run.published_at.toISOString(),
      taxonomyVersion: run.taxonomy_version,
      aggregateRunId: run.id,
      counts: await getCoverageCounts(db, run.id),
    },
  };
}
