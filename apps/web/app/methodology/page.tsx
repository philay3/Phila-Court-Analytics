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
 * Since task STATIC-2b the page is prerendered at build time by the static
 * build script, which materializes the API and fails on any unserved fetch.
 * Site-wide noindex is inherited from the root layout, unchanged.
 */
export const metadata: Metadata = {
  title: METHODOLOGY_COPY.heading,
};

export default async function MethodologyPage() {
  const result = await getMethodology();

  // DP-3: content routes render as a 760px article inside the 1200px shell
  // (bglad §12.1); the shell itself lives in the root layout.
  if (!result.ok) {
    return (
      <div className="mx-auto w-full max-w-article">
        <MethodologyErrorState message={methodologyFailureMessage(result.error)} />
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-article">
      <MethodologyView data={result.data} />
    </div>
  );
}
