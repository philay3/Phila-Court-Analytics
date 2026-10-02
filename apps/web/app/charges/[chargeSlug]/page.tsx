import { cache } from 'react';
import type { Metadata } from 'next';
import { getChargeResult, getSearchIndex } from '../../lib/public-api-client';
import { ChargeOnlyResultView } from '../../components/ChargeOnlyResultView';
import { ChargeUnavailableView } from '../../components/ChargeUnavailableView';
import { ChargeVolumeView } from '../../components/ChargeVolumeView';
import { judgesWithResultsFor } from '@pca/shared';
import { ChargeResultShell } from './ChargeResultShell';
import { resolveChargeResultState } from './charge-result-state';

/**
 * Charge result route (task 13.2; static since task STATIC-2b). A thin async
 * server component: it fetches via the 11.2 client (server-side, absolute base
 * URL — under the static build that is the build script's throwaway server)
 * and branches through the pure `resolveChargeResultState` helper into the
 * presentational success view, the volume view, or the in-page unavailable
 * view. All render logic lives in the presentational components; this file
 * only dispatches (pinned decision 1).
 *
 * Enumeration (STATIC-2b pin 2): every active roster charge, from
 * GET /api/v1/public/search-index, with `dynamicParams = false` so no path
 * outside that set is ever emitted or served. A slug the result endpoint does
 * not resolve, or any other failure, THROWS — which fails the export (the
 * STATIC-2a trial showed `notFound()` would instead bake a not-found page at
 * that slug). The index is also read for the page's baked judge list.
 *
 * `loadChargeResult` is memoized with React `cache` so the one fetch is shared
 * between `generateMetadata` and the page body. Site-wide noindex is inherited
 * from the root layout, unchanged.
 */
export const dynamicParams = false;

const loadChargeResult = cache((chargeSlug: string) => getChargeResult(chargeSlug));
const loadSearchIndex = cache(() => getSearchIndex());

export async function generateStaticParams(): Promise<{ chargeSlug: string }[]> {
  const result = await loadSearchIndex();
  if (!result.ok) {
    const why =
      result.error.kind === 'api_error'
        ? `${result.error.code} (${result.error.statusCode})`
        : 'fetch_failed';
    throw new Error(
      `The search index could not be loaded (${why}), so no charge page can be enumerated.`,
    );
  }
  if (!result.data.available) {
    throw new Error('The search index is unavailable (no published run); nothing to enumerate.');
  }
  return result.data.charges.map((charge) => ({ chargeSlug: charge.slug }));
}

interface ChargeResultPageProps {
  params: Promise<{ chargeSlug: string }>;
}

export async function generateMetadata({ params }: ChargeResultPageProps): Promise<Metadata> {
  const { chargeSlug } = await params;
  const state = resolveChargeResultState(await loadChargeResult(chargeSlug));
  // Every 200 arm (success, volume, unavailable) carries charge identity, so
  // the title is the charge display name in each.
  if (state.kind === 'success' || state.kind === 'volume' || state.kind === 'unavailable') {
    return { title: state.data.charge.displayName };
  }
  return {};
}

/** The judges with results for this charge (pin 4), from the same index read. */
async function loadJudgesFor(chargeSlug: string) {
  const index = await loadSearchIndex();
  if (!index.ok || !index.data.available) {
    throw new Error('The search index could not be loaded for the charge page judge list.');
  }
  return judgesWithResultsFor(index.data, chargeSlug);
}

export default async function ChargeResultPage({ params }: ChargeResultPageProps) {
  const { chargeSlug } = await params;
  const state = resolveChargeResultState(await loadChargeResult(chargeSlug));
  const judges = await loadJudgesFor(chargeSlug);

  if (state.kind === 'not-found') {
    // An enumerated slug the result endpoint does not know: fail the export
    // rather than emit a page (STATIC-2b pin 2).
    throw new Error(
      'An enumerated charge slug did not resolve to a result; refusing to emit a page.',
    );
  }
  if (state.kind === 'error') {
    // Generic, detail-free throw — fails the export; never reaches a page.
    throw new Error('The charge result could not be loaded.');
  }
  // DP-3: the success view manages its own two-column layout inside the
  // 1200px shell; the volume and unavailable states stay a single 760px
  // article.
  // The shell (STATIC-2b pin 3) owns `?judge=`: it renders these children
  // untouched when the param is absent and the in-page judge result or
  // notice when it is present. Volume/unavailable arms carry no pairs, so
  // their judge list is empty and any `?judge=` renders the unavailable notice.
  if (state.kind === 'success') {
    return (
      <ChargeResultShell chargeSlug={chargeSlug} judges={judges}>
        <ChargeOnlyResultView data={state.data} judges={judges} />
      </ChargeResultShell>
    );
  }
  return (
    <ChargeResultShell chargeSlug={chargeSlug} judges={[]}>
      <div className="mx-auto w-full max-w-article">
        {state.kind === 'volume' ? (
          <ChargeVolumeView data={state.data} />
        ) : (
          <ChargeUnavailableView data={state.data} />
        )}
      </div>
    </ChargeResultShell>
  );
}
