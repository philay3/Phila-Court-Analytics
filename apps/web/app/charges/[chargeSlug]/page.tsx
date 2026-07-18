import { cache } from 'react';
import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { getChargeResult } from '../../lib/public-api-client';
import { ChargeOnlyResultView } from '../../components/ChargeOnlyResultView';
import { ChargeUnavailableView } from '../../components/ChargeUnavailableView';
import { resolveChargeResultState } from './charge-result-state';

/**
 * Charge-only result route (task 13.2). A thin async server component: it
 * fetches via the 11.2 client (server-side, absolute base URL — no rewrite)
 * and branches through the pure `resolveChargeResultState` helper into the
 * presentational success view, the in-page unavailable view, `notFound()`, or
 * the error boundary. All render logic lives in the presentational components;
 * this file only dispatches (pinned decision 1).
 *
 * `loadChargeResult` is request-memoized with React `cache` so the one fetch is
 * shared between `generateMetadata` and the page body (a single API round-trip
 * per request). Site-wide noindex is inherited from the root layout, unchanged.
 */
const loadChargeResult = cache((chargeSlug: string) => getChargeResult(chargeSlug));

interface ChargeResultPageProps {
  params: Promise<{ chargeSlug: string }>;
}

export async function generateMetadata({ params }: ChargeResultPageProps): Promise<Metadata> {
  const { chargeSlug } = await params;
  const state = resolveChargeResultState(await loadChargeResult(chargeSlug));
  // Both the success and unavailable 200 arms carry charge identity, so the
  // title is the charge display name in each; not-found/error fall back to the
  // site default title from the layout template.
  if (state.kind === 'success' || state.kind === 'unavailable') {
    return { title: state.data.charge.displayName };
  }
  return {};
}

export default async function ChargeResultPage({ params }: ChargeResultPageProps) {
  const { chargeSlug } = await params;
  const state = resolveChargeResultState(await loadChargeResult(chargeSlug));

  if (state.kind === 'not-found') {
    notFound();
  }
  if (state.kind === 'error') {
    // Generic, detail-free throw — error.tsx renders its own safe copy and
    // never surfaces this message or any request detail.
    throw new Error('The charge result could not be loaded.');
  }
  // DP-3: the success view manages its own two-column layout inside the
  // 1200px shell; the unavailable state stays a single 760px article.
  return state.kind === 'success' ? (
    <ChargeOnlyResultView data={state.data} />
  ) : (
    <div className="mx-auto w-full max-w-article">
      <ChargeUnavailableView data={state.data} />
    </div>
  );
}
