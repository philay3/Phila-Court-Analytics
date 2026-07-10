/**
 * Date-range label (task 13.1). Renders an API-provided `{ start, end }` range
 * through the 11.4 formatter. The range is optional at the component boundary:
 * when it is absent the component renders nothing rather than inventing or
 * defaulting a value (task pins: "neither invents or defaults values"). Both
 * bounds are required by the shared `DateRange` schema, so once a range IS
 * provided the formatter handles it without any fallback.
 */
import type { DateRange } from '@pca/shared';
import { formatDateRange } from '../lib/formatters';

interface DateRangeLabelProps {
  /** The API-provided range, or undefined when none applies. */
  range?: DateRange;
}

export function DateRangeLabel({ range }: DateRangeLabelProps) {
  if (range === undefined) {
    return null;
  }
  return <p className="text-sm text-muted">{formatDateRange(range)}</p>;
}
