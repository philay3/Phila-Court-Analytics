/**
 * Outcome-distribution display groups (pre-recording session, pinned decision
 * 3). Purely presentational structure passed to every kind="outcome"
 * DistributionSection: member codes only select which SERVED rows a shared
 * heading spans — nothing here (or downstream) reorders, filters, sums, or
 * recomputes rows, so the 13.1 server-authoritative-order pin is untouched.
 * Heading strings are the @pca/shared sanctioned byte-pins; no user-facing
 * string is typed in this module.
 */
import {
  OUTCOME_GROUP_HEADING_DISMISSED_WITHDRAWN,
  OUTCOME_GROUP_HEADING_GUILTY,
} from '@pca/shared';

export interface DistributionRowGroup {
  /** Sanctioned heading rendered over the group's rows (table and bar stack). */
  readonly heading: string;
  /** Category codes the heading spans; membership only, never order. */
  readonly memberCodes: readonly string[];
}

/**
 * The two pinned outcome groups. Both pairs are adjacent in taxonomy
 * sortOrder (dismissed 1 / withdrawn 2; guilty_plea 3 / guilty_verdict 4), so
 * consecutive-run segmentation over served rows yields one heading per group.
 */
export const OUTCOME_DISPLAY_GROUPS: readonly DistributionRowGroup[] = [
  {
    heading: OUTCOME_GROUP_HEADING_DISMISSED_WITHDRAWN,
    memberCodes: ['dismissed', 'withdrawn'],
  },
  {
    heading: OUTCOME_GROUP_HEADING_GUILTY,
    memberCodes: ['guilty_plea', 'guilty_verdict'],
  },
];
