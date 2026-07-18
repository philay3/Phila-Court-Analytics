/**
 * Thin-data badge (task 13.1). Renders the pinned "Based on a small sample."
 * label — via the 11.4 `formatThinDataLabel` utility, never re-typed — only
 * when the distribution's API thin-data flag is set; renders nothing otherwise.
 * `formatThinDataLabel` returns `null` for a falsy flag, so the absence is
 * driven entirely by the API metadata.
 *
 * Embedded in `DistributionSection` adjacent to the sample-size label; also
 * usable standalone.
 */
import type { ThinDataStatus } from '@pca/shared';
import { formatThinDataLabel } from '../lib/formatters';

interface ThinDataBadgeProps {
  /** The distribution's thin-data flag, straight from the API block. */
  thin: ThinDataStatus;
}

export function ThinDataBadge({ thin }: ThinDataBadgeProps) {
  const label = formatThinDataLabel(thin);
  if (label === null) {
    return null;
  }
  return (
    <span className="inline-block border border-ink px-2 py-0.5 text-xs font-semibold text-ink">
      {label}
    </span>
  );
}
