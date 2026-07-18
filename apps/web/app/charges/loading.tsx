import { CHARGES_COPY } from './charges-copy';

/** Route-level loading state for the charges directory (task DP-4). */
export default function Loading() {
  return (
    <p role="status" className="text-muted">
      {CHARGES_COPY.loadingMessage}
    </p>
  );
}
