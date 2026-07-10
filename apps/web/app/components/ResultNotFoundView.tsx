/**
 * Generic result not-found view (task 13.3). Renders a friendly not-found state
 * IN PAGE — the judge-specific route resolves both missing-charge and
 * missing-judge to this view (HTTP 200, a soft 404) rather than calling
 * `notFound()`, because the two cases carry DISTINCT pinned @pca/shared message
 * literals and Next's not-found boundary is prop-less. The caller passes the
 * imported message verbatim; this component never re-types it.
 *
 * (This diverges from 13.2's real-404 behavior for a missing charge; it is
 * acceptable because result pages are noindex, and is flagged for the Sprint 9
 * launch-readiness indexing review — see tasks/worklog.md.)
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
      <p className="text-muted">{message}</p>
      <Link
        href="/"
        className="text-accent hover:underline focus-visible:rounded-xs focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
      >
        {CHARGE_RESULT_COPY.notFoundHomeLinkText}
      </Link>
    </div>
  );
}
