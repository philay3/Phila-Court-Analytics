import { CHARGE_RESULT_COPY } from '../../components/charge-result-copy';

/**
 * Route-level loading state (task 13.2, pinned decision 2). Neutral
 * placeholder copy: it describes the in-flight fetch only, never any outcome.
 */
export default function Loading() {
  return (
    <p role="status" className="text-muted">
      {CHARGE_RESULT_COPY.loadingMessage}
    </p>
  );
}
