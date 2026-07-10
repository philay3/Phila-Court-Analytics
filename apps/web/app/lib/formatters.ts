import type { ChargeOnlyResultSuccess, DateRange, JudgeSpecificResultSuccess } from '@pca/shared';

/**
 * Shared frontend formatting utilities (task 11.4). Pure functions, no React,
 * `Intl` only. Every Sprint 3 result and content page renders counts,
 * percentages, sample sizes, date ranges, last-refreshed timestamps,
 * result-type labels, and thin-data labels through this module so the display
 * conventions stay in one place and every user-facing label string is covered
 * by the copy guard (which walks `app/**`).
 *
 * Two rules run through everything here:
 *   - No analytics. Formatters render the values the API already computed;
 *     they never derive percentages from counts and sample sizes.
 *   - Pinned locale. Every `Intl` call passes `en-US` explicitly, so output
 *     never depends on the host locale.
 */

// en-US locale is pinned in one place and threaded through every Intl call.
const LOCALE = 'en-US';

const countFormatter = new Intl.NumberFormat(LOCALE);

// Up to one decimal place, no trailing `.0` (Intl never pads fraction digits).
const percentageFormatter = new Intl.NumberFormat(LOCALE, {
  maximumFractionDigits: 1,
});

// Date-only values are formatted against a UTC-constructed Date with a
// UTC-pinned formatter, so a `YYYY-MM-DD` renders on the same calendar day in
// every host timezone (locked decision 3).
const dateOnlyFormatter = new Intl.DateTimeFormat(LOCALE, {
  timeZone: 'UTC',
  year: 'numeric',
  month: 'long',
  day: 'numeric',
});

// `lastRefreshed` is an absolute instant; it is rendered in UTC with an
// explicit `UTC` suffix so the output is deterministic and host-independent.
const timestampFormatter = new Intl.DateTimeFormat(LOCALE, {
  timeZone: 'UTC',
  year: 'numeric',
  month: 'long',
  day: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
  timeZoneName: 'short',
});

/** en-dash with surrounding spaces, e.g. "January 1, 2025 – June 30, 2026". */
const DATE_RANGE_SEPARATOR = ' – ';

/** Prefix for the sample-size label; the value follows via {@link formatCount}. */
export const SAMPLE_SIZE_LABEL_PREFIX = 'Sample size: ';

/**
 * Result-type display labels. The sample-size unit (charge-level) is explained
 * in methodology, not here — these strings are deliberately noun-free.
 */
export const RESULT_TYPE_CHARGE_ONLY_LABEL = 'Philadelphia-wide historical result';
export const RESULT_TYPE_JUDGE_SPECIFIC_LABEL = 'Judge-specific historical result';

/**
 * Shown when a distribution's `thinData` flag is set. Unit-free by design: the
 * API sends a plain boolean, so there is no reason category to name here.
 */
export const THIN_DATA_LABEL = 'Based on a small sample.';

/**
 * The result-type values this module labels, derived from the shared response
 * contracts rather than hand-written literals. Adding a new labelable result
 * type to the contract makes {@link formatResultTypeLabel} fail typecheck at
 * the `never` assertion instead of silently mislabeling. The
 * `*_unavailable` arms (`charge_only_unavailable`, `judge_specific_unavailable`)
 * are intentionally excluded — they are absent-data states, not labelable
 * results — so both `resultType`s are drawn from the success arms only.
 */
type LabelableResultType =
  ChargeOnlyResultSuccess['resultType'] | JudgeSpecificResultSuccess['resultType'];

/** Integer count with en-US grouping separators. `0` renders as "0". */
export function formatCount(count: number): string {
  return countFormatter.format(count);
}

/**
 * Formats the API-provided percentage (0–100 scale, per the `@pca/shared`
 * distribution schema) for display: at most one decimal place, no trailing
 * `.0`, always suffixed with `%`. Performs no count/sample-size arithmetic.
 */
export function formatPercentage(percentage: number): string {
  return `${percentageFormatter.format(percentage)}%`;
}

/**
 * Sample-size label, e.g. "Sample size: 1,234". Generic over both outcome and
 * sentencing sample sizes: the caller passes the value and this utility does
 * not encode which distribution it belongs to. Noun-free because sample sizes
 * are charge-level, not case-level.
 */
export function formatSampleSize(sampleSize: number): string {
  return `${SAMPLE_SIZE_LABEL_PREFIX}${formatCount(sampleSize)}`;
}

/**
 * Formats a `{ start, end }` pair of `YYYY-MM-DD` strings into a human-readable
 * range, e.g. "January 1, 2025 – June 30, 2026". Both bounds are required by
 * the shared `DateRange` schema, so neither gets fallback handling (13.1: this
 * absence is intentional, not an oversight). Timezone-safe via UTC construction.
 */
export function formatDateRange(range: DateRange): string {
  return `${formatDateOnly(range.start)}${DATE_RANGE_SEPARATOR}${formatDateOnly(range.end)}`;
}

/**
 * Formats the API `lastRefreshed` value — an RFC 3339 `date-time` per the
 * shared contract — in UTC with an explicit `UTC` suffix, e.g.
 * "January 5, 2026, 2:30 PM UTC". `lastRefreshed` is required on every success
 * response, so there is no fallback handling here (intentional for 13.1).
 */
export function formatLastRefreshed(lastRefreshed: string): string {
  return timestampFormatter.format(new Date(lastRefreshed));
}

/** Exhaustive, compile-time-checked mapping from result type to display label. */
export function formatResultTypeLabel(resultType: LabelableResultType): string {
  switch (resultType) {
    case 'charge_only':
      return RESULT_TYPE_CHARGE_ONLY_LABEL;
    case 'judge_specific':
      return RESULT_TYPE_JUDGE_SPECIFIC_LABEL;
    default: {
      // Future result types must add a case above rather than fall through.
      const exhaustive: never = resultType;
      return exhaustive;
    }
  }
}

/**
 * Maps the shared thin-data flag (a plain boolean) to its display label, or
 * `null` when the flag is not set. No reason categories are invented because
 * the API sends none.
 */
export function formatThinDataLabel(thinData: boolean): string | null {
  return thinData ? THIN_DATA_LABEL : null;
}

const DATE_ONLY_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;

/**
 * Formats a single `YYYY-MM-DD` string timezone-safely. The string is split
 * into calendar parts and rebuilt with `Date.UTC`, then rendered by a
 * UTC-pinned formatter — the naive `new Date("2025-01-01")` UTC-midnight shift
 * never applies (locked decision 3).
 */
function formatDateOnly(dateOnly: string): string {
  const match = DATE_ONLY_PATTERN.exec(dateOnly);
  const [, yearPart, monthPart, dayPart] = match ?? [];
  if (yearPart === undefined || monthPart === undefined || dayPart === undefined) {
    throw new Error(`Expected a YYYY-MM-DD date string, received "${dateOnly}".`);
  }
  const utcDate = new Date(Date.UTC(Number(yearPart), Number(monthPart) - 1, Number(dayPart)));
  return dateOnlyFormatter.format(utcDate);
}
