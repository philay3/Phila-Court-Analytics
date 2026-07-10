/**
 * Sample-size label (task 13.1). Renders the noun-free pinned "Sample size: N"
 * format through the 11.4 formatter — never re-typed inline. Generic over both
 * the outcome and sentencing sample sizes: the caller passes whichever value
 * applies. The value is required, so nothing is invented or defaulted.
 */
import type { SampleSize } from '@pca/shared';
import { formatSampleSize } from '../lib/formatters';

interface SampleSizeLabelProps {
  /** The distribution's sample size, straight from the API block. */
  sampleSize: SampleSize;
}

export function SampleSizeLabel({ sampleSize }: SampleSizeLabelProps) {
  return <p className="text-sm text-muted">{formatSampleSize(sampleSize)}</p>;
}
