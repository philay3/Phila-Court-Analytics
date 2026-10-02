import Link from 'next/link';
import { JUDGE_RESULT_COPY } from './judge-result-copy';

/**
 * In-page notice for a `?judge=` the charge page cannot satisfy (task
 * STATIC-2b, pin 3): the pinned judge-unavailable message when the judge has
 * no results for this charge (or is unknown), or the transport-failure
 * message when the per-charge data file could not be loaded. The remove-filter
 * action is the charge-only URL — a soft navigation that clears the query —
 * and the charge-only result stays visible below the notice.
 */
interface JudgeFilterNoticeProps {
  chargeSlug: string;
  /** A pinned @pca/shared literal, rendered verbatim. */
  message: string;
}

export function JudgeFilterNotice({ chargeSlug, message }: JudgeFilterNoticeProps) {
  return (
    <section
      role="status"
      data-testid="judge-filter-notice"
      className="mb-6 space-y-2 border-2 border-ink bg-card p-4"
    >
      <p className="text-muted">{message}</p>
      <p>
        <Link
          href={`/charges/${chargeSlug}`}
          className="text-accent hover:text-accent-hover hover:underline"
        >
          {JUDGE_RESULT_COPY.removeFilterLinkText}
        </Link>
      </p>
    </section>
  );
}
