/**
 * Charge-unavailable view (task 13.2, pinned decision 3). Renders the HTTP 200
 * `charge_only_unavailable` arm IN PAGE — never routed through not-found.tsx.
 * The charge entity exists but no publishable aggregate does.
 *
 * It shows the charge identity as served, the pinned
 * `CHARGE_RESULT_UNAVAILABLE_MESSAGE` imported from @pca/shared (never re-typed,
 * and NOT read off `data.message`), and both the methodology and definitions
 * links whose hrefs come from the API `links` object (the arm carries both by
 * design, 13.2a). Presentational only — no data fetching.
 */
import Link from 'next/link';
import { CHARGE_RESULT_UNAVAILABLE_MESSAGE, type ChargeOnlyResultUnavailable } from '@pca/shared';
import { CHARGE_RESULT_COPY } from './charge-result-copy';

interface ChargeUnavailableViewProps {
  data: ChargeOnlyResultUnavailable;
}

const LINK_CLASS = 'text-accent hover:text-accent-hover hover:underline';

export function ChargeUnavailableView({ data }: ChargeUnavailableViewProps) {
  return (
    <div className="space-y-4">
      <h1>{data.charge.displayName}</h1>
      <p className="text-muted">{CHARGE_RESULT_UNAVAILABLE_MESSAGE}</p>
      <p className="flex flex-wrap gap-4">
        <Link href={data.links.methodology} className={LINK_CLASS}>
          {CHARGE_RESULT_COPY.methodologyLinkText}
        </Link>
        <Link href={data.links.definitions} className={LINK_CLASS}>
          {CHARGE_RESULT_COPY.definitionsLinkText}
        </Link>
      </p>
    </div>
  );
}
