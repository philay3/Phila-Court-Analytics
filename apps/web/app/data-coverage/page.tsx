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
 * Rendering: `dynamic = 'force-dynamic'` (task 15.2 CI finding) so the page
 * renders per request and never at build time — see the export note below.
 * Site-wide noindex is inherited from the root layout, unchanged.
 */
export const metadata: Metadata = {
  title: DATA_COVERAGE_COPY.heading,
};

// Render per request, never at build time (task 15.2 CI finding). These pages
// carry live published-run metadata (lastRefreshed, coverage dates) and the
// publication model separates deploys from data publication; a static prerender
// would bake a build-time snapshot — or, if the API is unreachable during
// `next build`, the error state — into the deploy. force-dynamic makes the
// server-side fetch run on every request.
export const dynamic = 'force-dynamic';

export default async function DataCoveragePage() {
  const result = await getDataCoverage();

  if (!result.ok) {
    return <DataCoverageErrorState message={dataCoverageFailureMessage(result.error)} />;
  }

  return <DataCoverageView data={result.data} />;
}
