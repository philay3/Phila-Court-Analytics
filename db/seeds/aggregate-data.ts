import { OUTCOME_CATEGORIES, SENTENCING_CATEGORIES } from '@pca/taxonomy';

/**
 * Aggregate seed data for the analytics.* layer (task 6.4).
 *
 * Every number here is FABRICATED. Judges are the obviously-fake 6.3 seed
 * judges; distributions are hand-constructed to exercise the Sprint 2/3
 * scenario matrix (thin data, sentencing-unavailable, judge-vs-baseline
 * divergence), not to describe any real court.
 *
 * Category codes are read off the generated @pca/taxonomy artifacts via
 * `publicCodeMap`, so a code string only appears here as a value that came
 * from the taxonomy package at runtime — and only `public: true` categories
 * are addressable at all. Removing a category from the taxonomy breaks this
 * file at compile time.
 *
 * `judge-fakename-example` deliberately appears in NO distribution: both ref
 * rows exist, zero aggregate rows exist. That absence is the canonical
 * judge-specific-unavailable fixture — do not "fix" it.
 */

/** Fixed run UUIDs: re-runs upsert the same rows instead of accreting runs. */
export const SEED_PUBLISHED_RUN_ID = '5eedda7a-0000-4000-8000-000000000001';
export const SEED_UNPUBLISHED_RUN_ID = '5eedda7a-0000-4000-8000-000000000002';

/**
 * Fixed timestamps (never `now()`) so a re-run's guarded upsert compares
 * equal and leaves the run rows byte-identical. Aggregate rows pin
 * `created_at` to the same constant so delete-and-reinsert regenerates only
 * the surrogate ids, keeping every content column identical across re-runs.
 */
export const SEED_RUN_CREATED_AT = new Date('2026-07-01T00:00:00.000Z');
export const SEED_AGGREGATE_CREATED_AT = '2026-07-01T02:00:00.000Z';
export const PUBLISHED_RUN_TIMESTAMPS = {
  startedAt: '2026-07-01T00:00:00.000Z',
  completedAt: '2026-07-01T01:00:00.000Z',
  publishedAt: '2026-07-01T02:00:00.000Z',
} as const;
export const UNPUBLISHED_RUN_STARTED_AT = '2026-07-02T00:00:00.000Z';

/** MVP data range: every run and every aggregate row carries exactly this. */
export const AGGREGATE_DATE_RANGE = {
  start: '2025-01-01',
  end: '2026-06-30',
} as const;

type PublicCategoryCode<T extends readonly { code: string; public: boolean }[]> = Extract<
  T[number],
  { public: true }
>['code'];

export type PublicOutcomeCode = PublicCategoryCode<typeof OUTCOME_CATEGORIES>;
export type PublicSentencingCode = PublicCategoryCode<typeof SENTENCING_CATEGORIES>;

function publicCodeMap<T extends readonly { code: string; public: boolean }[]>(
  categories: T,
): { readonly [K in PublicCategoryCode<T>]: K } {
  // Cast: Object.fromEntries widens keys and values to string; the mapped
  // type restores the literal pairing the filter/map construction guarantees.
  return Object.fromEntries(categories.filter((c) => c.public).map((c) => [c.code, c.code])) as {
    [K in PublicCategoryCode<T>]: K;
  };
}

const OUTCOME = publicCodeMap(OUTCOME_CATEGORIES);
const SENTENCING = publicCodeMap(SENTENCING_CATEGORIES);

export interface CategoryCount<Code extends string> {
  readonly code: Code;
  readonly count: number;
}

export interface ChargeOutcomeDistribution {
  readonly chargeSlug: string;
  readonly sampleSize: number;
  readonly isThinData: boolean;
  readonly counts: readonly CategoryCount<PublicOutcomeCode>[];
}

export interface JudgeOutcomeDistribution extends ChargeOutcomeDistribution {
  readonly judgeSlug: string;
}

export interface ChargeSentencingDistribution {
  readonly chargeSlug: string;
  readonly sentencingSampleSize: number;
  readonly isThinData: boolean;
  readonly counts: readonly CategoryCount<PublicSentencingCode>[];
}

export interface JudgeSentencingDistribution extends ChargeSentencingDistribution {
  readonly judgeSlug: string;
}

/** Philadelphia charge-only outcome baselines. */
export const PUBLISHED_CHARGE_OUTCOMES: readonly ChargeOutcomeDistribution[] = [
  {
    chargeSlug: 'retail-theft',
    sampleSize: 1200,
    isThinData: false,
    counts: [
      { code: OUTCOME.guilty_plea, count: 540 },
      { code: OUTCOME.dismissed, count: 264 },
      { code: OUTCOME.withdrawn, count: 156 },
      { code: OUTCOME.diversion, count: 108 },
      { code: OUTCOME.guilty_verdict, count: 60 },
      { code: OUTCOME.acquittal, count: 36 },
      { code: OUTCOME.ard, count: 24 },
      { code: OUTCOME.other, count: 12 },
    ],
  },
  {
    chargeSlug: 'simple-assault',
    sampleSize: 800,
    isThinData: false,
    counts: [
      { code: OUTCOME.dismissed, count: 232 },
      { code: OUTCOME.guilty_plea, count: 216 },
      { code: OUTCOME.withdrawn, count: 176 },
      { code: OUTCOME.acquittal, count: 64 },
      { code: OUTCOME.guilty_verdict, count: 56 },
      { code: OUTCOME.diversion, count: 40 },
      { code: OUTCOME.other, count: 16 },
    ],
  },
  {
    // ARD-heavy: plausible for first-offense DUI dockets.
    chargeSlug: 'dui-general-impairment',
    sampleSize: 1500,
    isThinData: false,
    counts: [
      { code: OUTCOME.ard, count: 615 },
      { code: OUTCOME.guilty_plea, count: 540 },
      { code: OUTCOME.dismissed, count: 120 },
      { code: OUTCOME.withdrawn, count: 90 },
      { code: OUTCOME.guilty_verdict, count: 60 },
      { code: OUTCOME.acquittal, count: 45 },
      { code: OUTCOME.other, count: 30 },
    ],
  },
  {
    chargeSlug: 'possession-controlled-substance',
    sampleSize: 950,
    isThinData: false,
    counts: [
      { code: OUTCOME.guilty_plea, count: 285 },
      { code: OUTCOME.dismissed, count: 238 },
      { code: OUTCOME.withdrawn, count: 199 },
      { code: OUTCOME.diversion, count: 133 },
      { code: OUTCOME.guilty_verdict, count: 38 },
      { code: OUTCOME.acquittal, count: 29 },
      { code: OUTCOME.other, count: 28 },
    ],
  },
  {
    // Thin-data fixture: n = 18 is far below any plausible threshold.
    chargeSlug: 'criminal-trespass',
    sampleSize: 18,
    isThinData: true,
    counts: [
      { code: OUTCOME.dismissed, count: 6 },
      { code: OUTCOME.guilty_plea, count: 5 },
      { code: OUTCOME.withdrawn, count: 4 },
      { code: OUTCOME.acquittal, count: 2 },
      { code: OUTCOME.guilty_verdict, count: 1 },
    ],
  },
];

/**
 * Charge-only sentencing baselines. possession-controlled-substance and
 * criminal-trespass are deliberately ABSENT (sentencing-unavailable
 * scenario). Sentencing n is always below the charge's outcome n.
 */
export const PUBLISHED_CHARGE_SENTENCING: readonly ChargeSentencingDistribution[] = [
  {
    chargeSlug: 'retail-theft',
    sentencingSampleSize: 700,
    isThinData: false,
    counts: [
      { code: SENTENCING.probation, count: 245 },
      { code: SENTENCING.fine, count: 161 },
      { code: SENTENCING.costs_fees, count: 119 },
      { code: SENTENCING.incarceration, count: 70 },
      { code: SENTENCING.community_service, count: 56 },
      { code: SENTENCING.restitution, count: 35 },
      { code: SENTENCING.no_further_penalty, count: 14 },
    ],
  },
  {
    chargeSlug: 'simple-assault',
    sentencingSampleSize: 450,
    isThinData: false,
    counts: [
      { code: SENTENCING.probation, count: 189 },
      { code: SENTENCING.incarceration, count: 90 },
      { code: SENTENCING.costs_fees, count: 63 },
      { code: SENTENCING.fine, count: 45 },
      { code: SENTENCING.community_service, count: 27 },
      { code: SENTENCING.no_further_penalty, count: 20 },
      { code: SENTENCING.restitution, count: 16 },
    ],
  },
  {
    chargeSlug: 'dui-general-impairment',
    sentencingSampleSize: 1100,
    isThinData: false,
    counts: [
      { code: SENTENCING.fine, count: 385 },
      { code: SENTENCING.probation, count: 275 },
      { code: SENTENCING.incarceration, count: 187 },
      { code: SENTENCING.costs_fees, count: 132 },
      { code: SENTENCING.community_service, count: 77 },
      { code: SENTENCING.other, count: 44 },
    ],
  },
];

/**
 * Judge-specific outcomes. Each distribution diverges visibly from the same
 * charge's baseline above so the Sprint 3 comparison UI has contrast to
 * render (e.g. testina/retail-theft: dismissed 35% vs 22% baseline).
 */
export const PUBLISHED_JUDGE_OUTCOMES: readonly JudgeOutcomeDistribution[] = [
  {
    chargeSlug: 'retail-theft',
    judgeSlug: 'judge-testina-placeholder',
    sampleSize: 140,
    isThinData: false,
    counts: [
      { code: OUTCOME.dismissed, count: 49 },
      { code: OUTCOME.guilty_plea, count: 42 },
      { code: OUTCOME.withdrawn, count: 21 },
      { code: OUTCOME.diversion, count: 14 },
      { code: OUTCOME.guilty_verdict, count: 7 },
      { code: OUTCOME.acquittal, count: 7 },
    ],
  },
  {
    chargeSlug: 'dui-general-impairment',
    judgeSlug: 'judge-samuel-seeddata',
    sampleSize: 210,
    isThinData: false,
    counts: [
      { code: OUTCOME.guilty_plea, count: 105 },
      { code: OUTCOME.ard, count: 42 },
      { code: OUTCOME.dismissed, count: 25 },
      { code: OUTCOME.guilty_verdict, count: 17 },
      { code: OUTCOME.withdrawn, count: 13 },
      { code: OUTCOME.acquittal, count: 8 },
    ],
  },
  {
    // Judge-specific thin-data fixture: n = 9.
    chargeSlug: 'simple-assault',
    judgeSlug: 'judge-testina-placeholder',
    sampleSize: 9,
    isThinData: true,
    counts: [
      { code: OUTCOME.dismissed, count: 3 },
      { code: OUTCOME.guilty_plea, count: 2 },
      { code: OUTCOME.withdrawn, count: 2 },
      { code: OUTCOME.acquittal, count: 1 },
      { code: OUTCOME.guilty_verdict, count: 1 },
    ],
  },
];

/**
 * Judge-specific sentencing. simple-assault/judge-testina-placeholder is
 * deliberately ABSENT (judge-specific sentencing-unavailable scenario).
 */
export const PUBLISHED_JUDGE_SENTENCING: readonly JudgeSentencingDistribution[] = [
  {
    chargeSlug: 'retail-theft',
    judgeSlug: 'judge-testina-placeholder',
    sentencingSampleSize: 85,
    isThinData: false,
    counts: [
      { code: SENTENCING.probation, count: 40 },
      { code: SENTENCING.community_service, count: 17 },
      { code: SENTENCING.fine, count: 12 },
      { code: SENTENCING.costs_fees, count: 9 },
      { code: SENTENCING.incarceration, count: 4 },
      { code: SENTENCING.restitution, count: 3 },
    ],
  },
  {
    chargeSlug: 'dui-general-impairment',
    judgeSlug: 'judge-samuel-seeddata',
    sentencingSampleSize: 160,
    isThinData: false,
    counts: [
      { code: SENTENCING.incarceration, count: 48 },
      { code: SENTENCING.fine, count: 40 },
      { code: SENTENCING.probation, count: 36 },
      { code: SENTENCING.costs_fees, count: 20 },
      { code: SENTENCING.community_service, count: 10 },
      { code: SENTENCING.other, count: 6 },
    ],
  },
];

/**
 * Unpublished decoy run: retail-theft outcomes only, with obviously-wrong
 * magnitudes (uniform 9999s). Structurally valid — counts sum to the sample
 * size, codes are public — so it exercises the publication filter, not row
 * validation. Phase 8 tests will assert this data never surfaces publicly.
 */
export const DECOY_CHARGE_OUTCOMES: readonly ChargeOutcomeDistribution[] = [
  {
    chargeSlug: 'retail-theft',
    sampleSize: 49_995,
    isThinData: false,
    counts: [
      { code: OUTCOME.dismissed, count: 9999 },
      { code: OUTCOME.withdrawn, count: 9999 },
      { code: OUTCOME.guilty_plea, count: 9999 },
      { code: OUTCOME.guilty_verdict, count: 9999 },
      { code: OUTCOME.acquittal, count: 9999 },
    ],
  },
];
