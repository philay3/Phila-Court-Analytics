import { cache } from 'react';
import type { Metadata } from 'next';
import { CHARGE_NOT_FOUND_MESSAGE, JUDGE_NOT_FOUND_MESSAGE } from '@pca/shared';
import { getJudgeSpecificResult } from '../../../../lib/public-api-client';
import { JudgeSpecificResultView } from '../../../../components/JudgeSpecificResultView';
import { JudgeUnavailableView } from '../../../../components/JudgeUnavailableView';
import { JudgeChargeUnavailableView } from '../../../../components/JudgeChargeUnavailableView';
import { ResultNotFoundView } from '../../../../components/ResultNotFoundView';
import { resolveJudgeResultState } from './judge-result-state';

/**
 * Judge-specific result route (task 13.3). A thin async server component: it
 * fetches via the 11.2 client (server-side, absolute base URL — no rewrite) and
 * branches through the pure `resolveJudgeResultState` helper into the
 * presentational success view, the in-page unavailable view, the in-page
 * not-found view, or the error boundary. All render logic lives in the
 * presentational components; this file only dispatches (mirrors 13.2).
 *
 * Not-found is rendered IN PAGE (a soft 404, HTTP 200) rather than via
 * `notFound()`, so the two distinct pinned messages (missing charge vs missing
 * judge) can each be shown. This diverges from 13.2's real-404 behavior for a
 * missing charge; it is acceptable because result pages are noindex, and is
 * flagged for the Sprint 9 launch-readiness indexing review (see worklog).
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

  if (state.kind === 'error') {
    // Generic, detail-free throw — error.tsx renders its own safe copy and
    // never surfaces this message or any request detail.
    throw new Error('The judge-specific result could not be loaded.');
  }
  if (state.kind === 'not-found') {
    return (
      <ResultNotFoundView
        message={state.reason === 'judge' ? JUDGE_NOT_FOUND_MESSAGE : CHARGE_NOT_FOUND_MESSAGE}
      />
    );
  }
  if (state.kind === 'charge-unavailable') {
    // Designed friendly state for a charge with no publishable aggregate,
    // handled before the generic throw above catches truly unexpected responses.
    return <JudgeChargeUnavailableView />;
  }
  return state.kind === 'success' ? (
    <JudgeSpecificResultView data={state.data} />
  ) : (
    <JudgeUnavailableView data={state.data} />
  );
}
