import {
  AGGREGATE_RUN_LABEL_PREFIX,
  CONVICTION_GRADES_ITEM_SEPARATOR,
  CONVICTION_GRADES_LABEL_PREFIX,
  RECORDED_OUTCOMES_LABEL_PREFIX,
  RECORDS_LABEL_PREFIX,
  SENTENCE_COMPONENTS_LABEL_PREFIX,
  SENTENCED_CONVICTIONS_LABEL_PREFIX,
  SINGLE_GRADE_TEMPLATE,
  SINGLE_GRADE_UNGRADED_LINE,
  UNGRADED_GRADE_LABEL,
  WEDGE_DISCLOSURE_TEMPLATE,
  WEDGE_DISCLOSURE_TEMPLATE_SINGULAR,
  ZERO_SENTENCED_FALLBACK_SINGULAR,
  ZERO_SENTENCED_FALLBACK_TEMPLATE,
} from '@pca/shared';
import type {
  ChargeOnlyResultSuccess,
  ConvictionGradeRow,
  DateRange,
  JudgeSpecificResultSuccess,
  SentencingIndexSummary,
} from '@pca/shared';

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
 * Reconciled sample labels (35.3, pin 11): each block names the unit its
 * sample actually counts. Outcome blocks count records (charge dispositions);
 * the component-grain sentencing block counts sentence components; the
 * sentencing-index block counts sentenced convictions (the rates'
 * denominator). Prefixes are @pca/shared pinned literals.
 */
export function formatRecordsLabel(sampleSize: number): string {
  return `${RECORDS_LABEL_PREFIX}${formatCount(sampleSize)}`;
}

export function formatSentenceComponentsLabel(sampleSize: number): string {
  return `${SENTENCE_COMPONENTS_LABEL_PREFIX}${formatCount(sampleSize)}`;
}

export function formatSentencedConvictionsLabel(sentencedConvictions: number): string {
  return `${SENTENCED_CONVICTIONS_LABEL_PREFIX}${formatCount(sentencedConvictions)}`;
}

/**
 * Surface-scoped sample-size label for EXACTLY two surfaces: /charges
 * directory rows and the homepage featured cards (DP-5 Amendment A), e.g.
 * "Recorded outcomes: 1,234". The prefix is the @pca/shared
 * RECORDED_OUTCOMES_LABEL_PREFIX pinned literal; the value path is the same
 * en-US grouping as every other count.
 */
export function formatRecordedOutcomes(sampleSize: number): string {
  return `${RECORDED_OUTCOMES_LABEL_PREFIX}${formatCount(sampleSize)}`;
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
 *
 * Exported for task 14.2: the data-coverage page renders lone date-only fields
 * (`plannedDataStart`) that are not part of a `{ start, end }` range, so they
 * need this single-value path directly. {@link formatDateRange} composes it for
 * the two-bound case; neither caller reimplements the calendar math.
 */
export function formatDateOnly(dateOnly: string): string {
  const match = DATE_ONLY_PATTERN.exec(dateOnly);
  const [, yearPart, monthPart, dayPart] = match ?? [];
  if (yearPart === undefined || monthPart === undefined || dayPart === undefined) {
    throw new Error(`Expected a YYYY-MM-DD date string, received "${dateOnly}".`);
  }
  const utcDate = new Date(Date.UTC(Number(yearPart), Number(monthPart) - 1, Number(dayPart)));
  return dateOnlyFormatter.format(utcDate);
}

// Median month values arrive pre-converted from the API (at most one decimal
// place); like percentages they are rendered without trailing `.0`.
const monthsFormatter = new Intl.NumberFormat(LOCALE, {
  maximumFractionDigits: 1,
});

/** Unspaced en dash between a distinct median pair, e.g. "12–18". */
const MEDIAN_RANGE_SEPARATOR = '–';

/**
 * Median pair display (35.3, pin 4): a flat pair (min = max) collapses to a
 * single figure; a distinct pair renders as a range. Equality comparison here
 * is presentation, not analytics — both values come from the API as served.
 * Returns `null` for duration-free categories (the trio is all-or-none per
 * the shared contract), which render an empty cell by ruling Q7.
 */
export function formatMedianMonths(
  medianMinMonths: number | undefined,
  medianMaxMonths: number | undefined,
): string | null {
  if (medianMinMonths === undefined || medianMaxMonths === undefined) {
    return null;
  }
  if (medianMinMonths === medianMaxMonths) {
    return monthsFormatter.format(medianMinMonths);
  }
  return `${monthsFormatter.format(medianMinMonths)}${MEDIAN_RANGE_SEPARATOR}${monthsFormatter.format(medianMaxMonths)}`;
}

/**
 * Wedge disclosure line (35.3, pin 10). Both grammatical variants are pinned
 * in @pca/shared; this formatter only picks the variant and fills the slots
 * with API-served values.
 */
export function formatWedgeDisclosure(summary: SentencingIndexSummary): string {
  const template =
    summary.wedgeCount === 1 ? WEDGE_DISCLOSURE_TEMPLATE_SINGULAR : WEDGE_DISCLOSURE_TEMPLATE;
  return template
    .replace('{wedgeCount}', formatCount(summary.wedgeCount))
    .replace('{convictions}', formatCount(summary.convictions))
    .replace('{wedgePercentage}', formatPercentage(summary.wedgePercentage));
}

/**
 * Zero-sentenced fallback line (35.3, ruling 4): carries the served
 * conviction count. Variant selection mirrors {@link formatWedgeDisclosure}.
 */
export function formatZeroSentencedFallback(convictions: number): string {
  if (convictions === 1) {
    return ZERO_SENTENCED_FALLBACK_SINGULAR;
  }
  return ZERO_SENTENCED_FALLBACK_TEMPLATE.replace('{convictions}', formatCount(convictions));
}

/** The served `ungraded` bucket renders under its gated label (pin 5). */
function gradeDisplayLabel(grade: string): string {
  return grade === 'ungraded' ? UNGRADED_GRADE_LABEL : grade;
}

/**
 * Grade-mix line (35.3, pin 5; charge pages only). Rows render dominant-first
 * exactly as served — no re-sorting. A single grade row states the grade
 * rather than a mix; an empty array yields `null` (nothing to state).
 */
export function formatGradeMixLine(grades: readonly ConvictionGradeRow[]): string | null {
  const [firstGrade] = grades;
  if (firstGrade === undefined) {
    return null;
  }
  if (grades.length === 1) {
    if (firstGrade.grade === 'ungraded') {
      return SINGLE_GRADE_UNGRADED_LINE;
    }
    return SINGLE_GRADE_TEMPLATE.replace('{grade}', firstGrade.grade);
  }
  const items = grades.map(
    (row) => `${gradeDisplayLabel(row.grade)} ${formatPercentage(row.percentageOfConvictions)}`,
  );
  return `${CONVICTION_GRADES_LABEL_PREFIX}${items.join(CONVICTION_GRADES_ITEM_SEPARATOR)}`;
}

/** Length of the short id form rendered on the provenance line (pin 7). */
const AGGREGATE_RUN_SHORT_ID_LENGTH = 8;

/**
 * Provenance line (35.3, pin 7): the already-served `aggregateRunId` in its
 * short id form, e.g. "Data release: 2f9c1e04".
 */
export function formatAggregateRunLabel(aggregateRunId: string): string {
  return `${AGGREGATE_RUN_LABEL_PREFIX}${aggregateRunId.slice(0, AGGREGATE_RUN_SHORT_ID_LENGTH)}`;
}
