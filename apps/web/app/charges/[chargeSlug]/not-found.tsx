import Link from 'next/link';
import { CHARGE_NOT_FOUND_MESSAGE } from '@pca/shared';
import { CHARGE_RESULT_COPY } from '../../components/charge-result-copy';

/**
 * Charge not-found state (task 13.2, pinned decision 2). Rendered via
 * `notFound()` when the client returns CHARGE_NOT_FOUND (real 404 semantics).
 * The body is the pinned `CHARGE_NOT_FOUND_MESSAGE` imported from @pca/shared —
 * never re-typed — with a link back to the homepage search.
 */
export default function NotFound() {
  return (
    <div className="space-y-4">
      <h1>{CHARGE_RESULT_COPY.notFoundHeading}</h1>
      <p className="text-muted">{CHARGE_NOT_FOUND_MESSAGE}</p>
      <Link href="/" className="text-accent hover:text-accent-hover hover:underline">
        {CHARGE_RESULT_COPY.notFoundHomeLinkText}
      </Link>
    </div>
  );
}
