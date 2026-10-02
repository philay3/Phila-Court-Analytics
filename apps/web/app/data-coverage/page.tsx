import type { Metadata } from 'next';
import { getDataCoverage } from '../lib/public-api-client';
import { DataCoverageView, DataCoverageErrorState } from './DataCoverageView';
import { dataCoverageFailureMessage } from './data-coverage-failure';
import { DATA_COVERAGE_COPY } from './data-coverage-copy';

/**
 * Data-coverage route (task 14.2). A thin async server component mirroring the
 * 14.1 definitions page: it fetches the public data coverage via the 11.2
 * client (server-side, absolute base URL — the standing 13.2/13.3 pattern) and
 * dispatches to a presentational view.
 *
 * Two distinct "not-available" cases are handled separately:
 *   - transport/API failure (`ok: false`) → inline error state with a per-arm
 *     @pca/shared message (no internal detail ever reaches the user); and
 *   - the endpoint's own HTTP-200 "unavailable" arm → a successful response the
 *     view renders directly (served `coverage.message`), still showing the
 *     always-present jurisdiction/scope/start and known-limitations.
 *
 * Since task STATIC-2b the page is prerendered at build time by the static
 * build script, which materializes the API and fails on any unserved fetch.
 * Site-wide noindex is inherited from the root layout, unchanged.
 */
export const metadata: Metadata = {
  title: DATA_COVERAGE_COPY.heading,
};

export default async function DataCoveragePage() {
  const result = await getDataCoverage();

  // DP-3: content routes render as a 760px article inside the 1200px shell
  // (bglad §12.1); the shell itself lives in the root layout.
  if (!result.ok) {
    return (
      <div className="mx-auto w-full max-w-article">
        <DataCoverageErrorState message={dataCoverageFailureMessage(result.error)} />
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-article">
      <DataCoverageView data={result.data} />
    </div>
  );
}
