import { CHARGE_RESULT_COPY } from '../../../../components/charge-result-copy';

/**
 * Route-level loading state (task 13.3). Neutral placeholder copy: it describes
 * the in-flight fetch only, never any outcome. The message is reused from
 * `CHARGE_RESULT_COPY` (shared result-page chrome) so it stays typed in one
 * place.
 */
export default function Loading() {
  return (
    <p role="status" className="mx-auto w-full max-w-article text-muted">
      {CHARGE_RESULT_COPY.loadingMessage}
    </p>
  );
}
