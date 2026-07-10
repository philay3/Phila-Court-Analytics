import type { Metadata } from 'next';
import { getMethodology } from '../lib/public-api-client';
import { MethodologyView, MethodologyErrorState } from './MethodologyView';
import { methodologyFailureMessage } from './methodology-failure';
import { METHODOLOGY_COPY } from './methodology-copy';

/**
 * Methodology route (task 14.2). A thin async server component mirroring the
 * 14.1 definitions page: it fetches the public methodology via the 11.2 client
 * (server-side, absolute base URL — the standing 13.2/13.3 pattern) and
 * dispatches to a presentational view.
 *
 * On failure the error is rendered inline (not via an error.tsx boundary): the
 * client returns `ok: false` with a discriminated failure arm rather than
 * throwing, and the page selects the correct @pca/shared message per arm —
 * something a boundary receiving only a thrown Error cannot do. No internal
 * error detail ever reaches the user.
 *
 * Caching matches 14.1: no route-segment `dynamic`/`revalidate` override; the
 * 11.2 client's plain `fetch` governs caching identically to the definitions
 * page. Site-wide noindex is inherited from the root layout, unchanged.
 */
export const metadata: Metadata = {
  title: METHODOLOGY_COPY.heading,
};

export default async function MethodologyPage() {
  const result = await getMethodology();

  if (!result.ok) {
    return <MethodologyErrorState message={methodologyFailureMessage(result.error)} />;
  }

  return <MethodologyView data={result.data} />;
}
