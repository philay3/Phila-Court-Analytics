/**
 * Generic result not-found view (task 13.3; role changed at fix R7b,
 * 2026-07-25). Originally the judge route's IN-PAGE soft-404; that route now
 * calls `notFound()` with real 404 semantics, and this shell renders inside
 * its `not-found.tsx` boundary with the single pinned
 * `JUDGE_RESULT_NOT_FOUND_MESSAGE` (the boundary is prop-less, so the two
 * per-reason literals stay on the API error envelopes only). The caller
 * passes the imported message verbatim; this component never re-types it.
 *
 * The "return to search" link text is reused from `CHARGE_RESULT_COPY`; the
 * link target is the homepage search. Presentational only — no data fetching.
 */
import Link from 'next/link';
import { CHARGE_RESULT_COPY } from './charge-result-copy';

interface ResultNotFoundViewProps {
  /** The pinned @pca/shared message literal for this not-found reason. */
  message: string;
}

export function ResultNotFoundView({ message }: ResultNotFoundViewProps) {
  return (
    <div className="space-y-4">
      <h1>{CHARGE_RESULT_COPY.notFoundHeading}</h1>
      <p className="text-muted">{message}</p>
      <Link href="/" className="text-accent hover:text-accent-hover hover:underline">
        {CHARGE_RESULT_COPY.notFoundHomeLinkText}
      </Link>
    </div>
  );
}
