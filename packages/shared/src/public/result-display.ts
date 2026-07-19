/**
 * Result-page display copy (task 35.3): the sentencing-index lead block, the
 * reconciled sample labels, and the provenance label. Every constant here is
 * sanctioned byte-exact by the 35.3 framing review — edits re-adjudicate.
 *
 * Templates use `{name}` substitution slots filled by the web formatters
 * (apps/web/app/lib/formatters.ts); the strings themselves are never re-typed
 * outside this module. Where grammatical number changes the sentence, both
 * variants are pinned here and the formatter branches on the count.
 */

/** Index table caption — the conditional header (conviction-denominated). */
export const SENTENCING_INDEX_CAPTION =
  'Historical sentencing rates: when charges like this ended in conviction';

/** Index table column headers. */
export const SENTENCING_INDEX_CATEGORY_HEADER = 'Sentence category';
export const SENTENCING_INDEX_COUNT_HEADER = 'Convictions';
export const SENTENCING_INDEX_PERCENTAGE_HEADER = 'Percentage of sentenced convictions';
export const SENTENCING_INDEX_MEDIAN_HEADER = 'Median (months)';

/** Index block count line: the denominator of the rates. */
export const SENTENCED_CONVICTIONS_LABEL_PREFIX = 'Sentenced convictions: ';

/**
 * Wedge disclosure (excluded-with-disclosure, ruling: neutral and numeric —
 * never implies absence of punishment, never promises future records).
 * Plural form covers wedgeCount 0 and >= 2; the singular form is pinned with
 * its literal `1`.
 */
export const WEDGE_DISCLOSURE_TEMPLATE =
  '{wedgeCount} of {convictions} recorded convictions ({wedgePercentage}) have no public sentencing record in the collected data and are not counted in the rates above.';
export const WEDGE_DISCLOSURE_TEMPLATE_SINGULAR =
  '1 of {convictions} recorded convictions ({wedgePercentage}) has no public sentencing record in the collected data and is not counted in the rates above.';

/**
 * Zero-sentenced arm fallback (ruling 4): carries the served conviction
 * count. Replaces the generic sentencing-unavailable notice on this arm only.
 */
export const ZERO_SENTENCED_FALLBACK_TEMPLATE =
  'None of the {convictions} recorded convictions here has a public sentencing record in the collected data.';
export const ZERO_SENTENCED_FALLBACK_SINGULAR =
  'The 1 recorded conviction here has no public sentencing record in the collected data.';

/**
 * Grade-mix line (charge pages only; judge cells serve no grades). Items are
 * rendered dominant-first exactly as served, joined by the pinned separator,
 * e.g. "Conviction grades: F3 50% · M1 25% · no recorded grade 5%".
 */
export const CONVICTION_GRADES_LABEL_PREFIX = 'Conviction grades: ';
export const CONVICTION_GRADES_ITEM_SEPARATOR = ' · ';
export const SINGLE_GRADE_TEMPLATE = 'Every recorded conviction here is grade {grade}.';
export const SINGLE_GRADE_UNGRADED_LINE = 'Every recorded conviction here has no recorded grade.';
/** Gated label for the served `ungraded` bucket. */
export const UNGRADED_GRADE_LABEL = 'no recorded grade';

/**
 * Component-grain sentencing caption when the block renders below the index.
 * The absent arm keeps today's caption (structural stability, ruling Q1).
 */
export const SENTENCING_DETAIL_CAPTION = 'Historical sentencing detail by sentence component';

/**
 * Reconciled sample labels (the Sample-size byte-identity guard lifted here
 * by design): outcome blocks count records, the component-grain sentencing
 * block counts sentence components. The directory/featured surfaces keep
 * their own RECORDED_OUTCOMES_LABEL_PREFIX untouched.
 */
export const RECORDS_LABEL_PREFIX = 'Records: ';
export const SENTENCE_COMPONENTS_LABEL_PREFIX = 'Sentence components: ';

/** Provenance line: prefix + the first 8 characters of `aggregateRunId`. */
export const AGGREGATE_RUN_LABEL_PREFIX = 'Data release: ';
