/**
 * Thin-data callout (task 13.1). A standalone explanatory block that renders
 * only when the API thin-data flag is set. Deliberately NOT embedded in
 * DistributionSection: tasks 13.2/13.3 place it at page level (before the
 * distribution sections) to satisfy the required mobile content order.
 *
 * Copy is the plain-English `thinDataCalloutBody` from the copy module —
 * nothing user-facing is typed inline here.
 */
import type { ThinDataStatus } from '@pca/shared';
import { RESULT_DISPLAY_COPY } from './result-display-copy';

interface ThinDataCalloutProps {
  /** The distribution's thin-data flag, straight from the API block. */
  thin: ThinDataStatus;
}

export function ThinDataCallout({ thin }: ThinDataCalloutProps) {
  if (!thin) {
    return null;
  }
  return (
    <div role="note" className="border border-rule bg-card p-4 text-sm text-body">
      {RESULT_DISPLAY_COPY.thinDataCalloutBody}
    </div>
  );
}
