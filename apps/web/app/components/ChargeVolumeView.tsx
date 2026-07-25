/**
 * Charge-volume view (Phase 36). Renders the HTTP 200 `charge_only_volume`
 * arm IN PAGE: the charge is real and the published run has seen it, but no
 * final outcome has been recorded yet — the state every newly rostered charge
 * starts in. It replaces the old dead-end unavailable rendering for exactly
 * this case with the number that exists: the deduplicated charges-seen count.
 *
 * Per the operator display ruling (2026-07-25), only the deduplicated totals
 * appear — no stage breakdown; the counting convention lives on the
 * methodology page. The date range gives the count its window; the pinned
 * message is imported from @pca/shared (never re-typed, NOT read off
 * `data.message`). Presentational only — no data fetching.
 */
import Link from 'next/link';
import { CHARGE_VOLUME_ONLY_MESSAGE, type ChargeOnlyResultVolume } from '@pca/shared';
import { formatChargeVolumeSeenOnly } from '../lib/formatters';
import { CHARGE_RESULT_COPY } from './charge-result-copy';
import { DateRangeLabel } from './DateRangeLabel';

interface ChargeVolumeViewProps {
  data: ChargeOnlyResultVolume;
}

const LINK_CLASS = 'text-accent hover:text-accent-hover hover:underline';

export function ChargeVolumeView({ data }: ChargeVolumeViewProps) {
  return (
    <div className="space-y-4">
      <h1>{data.charge.displayName}</h1>
      <DateRangeLabel range={data.dateRange} />
      <p data-testid="volume-seen-line" className="text-base text-ink">
        {formatChargeVolumeSeenOnly(data.volume.chargesSeen)}
      </p>
      <p className="text-muted">{CHARGE_VOLUME_ONLY_MESSAGE}</p>
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
