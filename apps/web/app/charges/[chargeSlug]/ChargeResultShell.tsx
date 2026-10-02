'use client';

import { Suspense, useEffect, useRef, useState, type ReactNode } from 'react';
import { useSearchParams } from 'next/navigation';
import {
  FETCH_FAILURE_MESSAGE,
  JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE,
  type ChargeJudgeDataFile,
  type SearchIndexJudge,
} from '@pca/shared';
import { JudgeFilterNotice } from '../../components/JudgeFilterNotice';
import { JudgeSpecificResultView } from '../../components/JudgeSpecificResultView';
import { JUDGE_RESULT_COPY } from '../../components/judge-result-copy';
import { loadChargeJudgeData } from '../../lib/static-data';
import type { PublicApiResult } from '../../lib/public-api-client';

/**
 * In-page judge results on the charge page (task STATIC-2b, pin 3). The
 * server-rendered charge-only view arrives as `children`; this shell reads
 * `?judge=` on the client and decides what to show:
 *
 *   - no `judge` param            → the children, untouched (no panel at all);
 *   - a judge in the baked list   → the per-charge data file, fetched lazily
 *                                   (first selection, or on load with the
 *                                   param present), then JudgeSpecificResultView
 *                                   — the same component the judge route
 *                                   rendered — in place of the children; its
 *                                   remove-filter link clears the query;
 *   - an unknown or unpaired judge → the pinned unavailable notice above the
 *                                   children (the charge-only result remains);
 *   - a failed file load          → the transport-failure notice likewise.
 *
 * `useSearchParams` makes a static page client-render up to the nearest
 * Suspense boundary, so the boundary's fallback IS the children: the exported
 * HTML is the complete charge-only page, and hydration swaps in identical
 * markup. `window.history.pushState` from the judge filter updates the param
 * without a navigation; Next syncs it into `useSearchParams`.
 */
interface ChargeResultShellProps {
  chargeSlug: string;
  /** Judges with judge-specific results for this charge, baked at build time. */
  judges: readonly SearchIndexJudge[];
  children: ReactNode;
}

export function ChargeResultShell({ chargeSlug, judges, children }: ChargeResultShellProps) {
  return (
    <Suspense fallback={children}>
      <JudgePanel chargeSlug={chargeSlug} judges={judges}>
        {children}
      </JudgePanel>
    </Suspense>
  );
}

function JudgePanel({ chargeSlug, judges, children }: ChargeResultShellProps) {
  const searchParams = useSearchParams();
  const judgeSlug = searchParams.get('judge');
  const paired = judgeSlug !== null && judges.some((judge) => judge.slug === judgeSlug);
  // One per-charge file serves every judge on the page: request it once when a
  // paired judge is first selected; the loader itself forgets a failed load so
  // the next selection retries. State is written only from the resolved
  // promise, never synchronously in the effect body.
  const requestedRef = useRef(false);
  const mountedRef = useRef(true);
  const [result, setResult] = useState<PublicApiResult<ChargeJudgeDataFile> | null>(null);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (!paired || requestedRef.current) {
      return;
    }
    requestedRef.current = true;
    void loadChargeJudgeData(chargeSlug).then((loaded) => {
      if (!mountedRef.current) {
        return;
      }
      if (!loaded.ok) {
        requestedRef.current = false;
      }
      setResult(loaded);
    });
  }, [chargeSlug, paired]);

  if (judgeSlug === null) {
    return <>{children}</>;
  }
  if (!paired) {
    return (
      <>
        <JudgeFilterNotice chargeSlug={chargeSlug} message={JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE} />
        {children}
      </>
    );
  }
  if (result !== null) {
    if (!result.ok) {
      return (
        <>
          <JudgeFilterNotice chargeSlug={chargeSlug} message={FETCH_FAILURE_MESSAGE} />
          {children}
        </>
      );
    }
    const payload = result.data.judges[judgeSlug];
    if (!payload) {
      return (
        <>
          <JudgeFilterNotice chargeSlug={chargeSlug} message={JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE} />
          {children}
        </>
      );
    }
    return <JudgeSpecificResultView data={payload} />;
  }
  return (
    <>
      <p role="status" className="mb-6 text-muted">
        {JUDGE_RESULT_COPY.panelLoading}
      </p>
      {children}
    </>
  );
}
