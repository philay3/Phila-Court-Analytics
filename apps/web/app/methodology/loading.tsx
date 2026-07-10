import { METHODOLOGY_COPY } from './methodology-copy';

/**
 * Route-level loading state (task 14.2). Neutral placeholder copy: it describes
 * the in-flight fetch only, never any methodology section or figure.
 */
export default function Loading() {
  return (
    <p role="status" className="text-muted">
      {METHODOLOGY_COPY.loadingMessage}
    </p>
  );
}
