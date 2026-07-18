'use client';

import { CHARGE_RESULT_COPY } from '../components/charge-result-copy';
import { CHARGES_COPY } from './charges-copy';

/**
 * Charges directory error boundary (task DP-4), mirroring the charge-result
 * boundary: generic, internal-detail-free copy — the thrown `error` is
 * intentionally NOT rendered. Heading and retry label are reused
 * byte-identically from CHARGE_RESULT_COPY; only the body is
 * directory-specific. `reset` lets the user retry the segment render. The
 * nested [chargeSlug] boundary takes precedence for child routes.
 */
interface ChargesDirectoryErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function ChargesDirectoryError({ reset }: ChargesDirectoryErrorProps) {
  return (
    <div className="mx-auto w-full max-w-article space-y-4">
      <h1>{CHARGE_RESULT_COPY.errorHeading}</h1>
      <p className="text-muted">{CHARGES_COPY.errorBody}</p>
      <button
        type="button"
        onClick={reset}
        className="min-h-11 bg-ink px-5 py-3 text-sm font-semibold tracking-[.08em] text-card uppercase hover:bg-ink-hover"
      >
        {CHARGE_RESULT_COPY.errorRetryText}
      </button>
    </div>
  );
}
