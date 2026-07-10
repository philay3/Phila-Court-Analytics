'use client';

import { CHARGE_RESULT_COPY } from '../../../../components/charge-result-copy';

/**
 * Judge-specific result error boundary (task 13.3). A client component rendered
 * when the page throws (any non-not-found failure). It shows generic,
 * internal-detail-free copy: the thrown `error` is intentionally NOT rendered —
 * no message, digest, or request detail reaches the user. `reset` lets the user
 * retry the segment render. Copy is reused from `CHARGE_RESULT_COPY` (shared
 * result-page chrome) so it stays typed in one place.
 */
interface JudgeErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function JudgeError({ reset }: JudgeErrorProps) {
  return (
    <div className="space-y-4">
      <h1>{CHARGE_RESULT_COPY.errorHeading}</h1>
      <p className="text-muted">{CHARGE_RESULT_COPY.errorBody}</p>
      <button
        type="button"
        onClick={reset}
        className="rounded-md bg-accent px-5 py-3 text-base font-semibold text-canvas hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
      >
        {CHARGE_RESULT_COPY.errorRetryText}
      </button>
    </div>
  );
}
