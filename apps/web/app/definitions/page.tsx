import type { Metadata } from 'next';
import { getDefinitions } from '../lib/public-api-client';
import { DefinitionsView, DefinitionsErrorState } from './DefinitionsView';
import { definitionsFailureMessage } from './definitions-failure';
import { DEFINITIONS_COPY } from './definitions-copy';

/**
 * Definitions route (task 14.1). A thin async server component: it fetches the
 * public definitions via the 11.2 client (server-side, absolute base URL — the
 * standing 13.2/13.3 pattern) and dispatches to a presentational view.
 *
 * On failure the error is rendered inline (not via an error.tsx boundary): the
 * client returns `ok: false` with a discriminated failure arm rather than
 * throwing, and the page must select the correct @pca/shared message per arm —
 * something a boundary receiving only a thrown Error cannot do. No internal
 * error detail ever reaches the user.
 *
 * Categories render in served (taxonomy) order; this file does no sorting.
 * Site-wide noindex is inherited from the root layout, unchanged.
 */
export const metadata: Metadata = {
  title: DEFINITIONS_COPY.heading,
};

// Render per request, never at build time (task 15.2 CI finding). These pages
// carry live published-run metadata and the publication model separates deploys
// from data publication; a static prerender would bake a build-time snapshot —
// or, if the API is unreachable during `next build`, the error state — into the
// deploy. force-dynamic makes the server-side fetch run on every request.
export const dynamic = 'force-dynamic';

export default async function DefinitionsPage() {
  const result = await getDefinitions();

  if (!result.ok) {
    return <DefinitionsErrorState message={definitionsFailureMessage(result.error)} />;
  }

  return <DefinitionsView data={result.data} />;
}
