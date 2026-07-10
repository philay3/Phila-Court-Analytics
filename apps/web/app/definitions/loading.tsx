import { DEFINITIONS_COPY } from './definitions-copy';

/**
 * Route-level loading state (task 14.1). Neutral placeholder copy: it describes
 * the in-flight fetch only, never any category, figure, or outcome.
 */
export default function Loading() {
  return (
    <p role="status" className="text-muted">
      {DEFINITIONS_COPY.loadingMessage}
    </p>
  );
}
