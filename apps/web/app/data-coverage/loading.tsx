import { DATA_COVERAGE_COPY } from './data-coverage-copy';

/**
 * Route-level loading state (task 14.2). Neutral placeholder copy: it describes
 * the in-flight fetch only, never any coverage figure or limitation.
 */
export default function Loading() {
  return (
    <p role="status" className="text-muted">
      {DATA_COVERAGE_COPY.loadingMessage}
    </p>
  );
}
