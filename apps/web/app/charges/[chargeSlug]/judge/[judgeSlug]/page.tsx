import { cache } from 'react';
import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { getJudgeSpecificResult } from '../../../../lib/public-api-client';
import { JudgeSpecificResultView } from '../../../../components/JudgeSpecificResultView';
import { JudgeUnavailableView } from '../../../../components/JudgeUnavailableView';
import { JudgeChargeUnavailableView } from '../../../../components/JudgeChargeUnavailableView';
import { resolveJudgeResultState } from './judge-result-state';

/**
 * Judge-specific result route (task 13.3). A thin async server component: it
 * fetches via the 11.2 client (server-side, absolute base URL — no rewrite) and
 * branches through the pure `resolveJudgeResultState` helper into the
 * presentational success view, the in-page unavailable view, `notFound()`, or
 * the error boundary. All render logic lives in the presentational components;
 * this file only dispatches (mirrors 13.2).
 *
 * Not-found is a REAL 404 via `notFound()` (fix R7b, 2026-07-25), replacing
 * the original in-page soft-404. The boundary is prop-less, so the two
 * distinct pinned messages were traded for the single
 * `JUDGE_RESULT_NOT_FOUND_MESSAGE` in `not-found.tsx`; the per-reason
 * literals remain on the API error envelopes. This route and its parent no
 * longer define `loading.tsx` — a route-level Suspense boundary would flush a
 * 200 shell before `notFound()` runs, which was the R7a/R7b defect. Do not
 * reintroduce one on this segment or any ancestor of a `notFound()` caller.
 *
 * `loadJudgeResult` is request-memoized with React `cache` so the one fetch is
 * shared between `generateMetadata` and the page body (a single API round-trip
 * per request). Site-wide noindex is inherited from the root layout, unchanged.
 */
const loadJudgeResult = cache((chargeSlug: string, judgeSlug: string) =>
  getJudgeSpecificResult(chargeSlug, judgeSlug),
);

interface JudgeResultPageProps {
  params: Promise<{ chargeSlug: string; judgeSlug: string }>;
}

export async function generateMetadata({ params }: JudgeResultPageProps): Promise<Metadata> {
  const { chargeSlug, judgeSlug } = await params;
  const state = resolveJudgeResultState(await loadJudgeResult(chargeSlug, judgeSlug));
  // Both the success and unavailable 200 arms carry charge AND judge identity,
  // so the title names both; not-found/error fall back to the site default
  // title from the layout template.
  if (state.kind === 'success' || state.kind === 'unavailable') {
    return { title: `${state.data.charge.displayName} — ${state.data.judge.displayName}` };
  }
  return {};
}

export default async function JudgeResultPage({ params }: JudgeResultPageProps) {
  const { chargeSlug, judgeSlug } = await params;
  const state = resolveJudgeResultState(await loadJudgeResult(chargeSlug, judgeSlug));

  if (state.kind === 'not-found') {
    // Real 404 semantics (fix R7b): not-found.tsx renders the boundary copy.
    // `state.reason` is not consumed here anymore; the resolver keeps it so
    // the distinction stays unit-tested and available to any future consumer.
    notFound();
  }
  if (state.kind === 'error') {
    // Generic, detail-free throw — error.tsx renders its own safe copy and
    // never surfaces this message or any request detail.
    throw new Error('The judge-specific result could not be loaded.');
  }
  // DP-3: the success view manages its own two-column layout inside the
  // 1200px shell; every non-success state stays a single 760px article.
  if (state.kind === 'charge-unavailable') {
    // Designed friendly state for a charge with no publishable aggregate,
    // handled before the generic throw above catches truly unexpected responses.
    return (
      <div className="mx-auto w-full max-w-article">
        <JudgeChargeUnavailableView />
      </div>
    );
  }
  return state.kind === 'success' ? (
    <JudgeSpecificResultView data={state.data} />
  ) : (
    <div className="mx-auto w-full max-w-article">
      <JudgeUnavailableView data={state.data} />
    </div>
  );
}
