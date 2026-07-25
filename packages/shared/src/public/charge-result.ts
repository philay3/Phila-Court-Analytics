import { Type, type Static } from '@sinclair/typebox';
import { PUBLIC_ERROR_CODES } from '../errors.js';
import {
  dateRangeSchema,
  outcomeDistributionEntrySchema,
  sampleSizeSchema,
  sentencingDistributionEntrySchema,
  taxonomyVersionSchema,
  thinDataStatusSchema,
} from './common.js';
import { chargeSentencingIndexSchema } from './sentencing-index.js';

/**
 * Charge-only public result contract (task 8.1):
 * GET /api/v1/public/results/charge/{chargeIdOrSlug}.
 *
 * Sample sizes live on each distribution block, never per row, and the
 * outcome and sentencing sample sizes are independent. The date range is
 * result-level — it describes the aggregate run, not a single distribution.
 */

/**
 * The ONLY message the sentencing-unavailable arm may carry. Public-safe by
 * construction: schema-pinned as a literal below, so any internal wording
 * (parser/review/extraction) is a contract violation, not just a convention.
 */
export const CHARGE_SENTENCING_UNAVAILABLE_MESSAGE =
  'Historical sentencing data is not available for this charge yet.';

/**
 * Pinned public message literals for the charge-result error arms (migrated
 * from the 8.1 service in task 10.2). CHARGE_NOT_FOUND_MESSAGE accompanies
 * PUBLIC_ERROR_CODES.CHARGE_NOT_FOUND; CHARGE_RESULT_UNAVAILABLE_MESSAGE is
 * the one message for both no-published-run and zero-outcome-rows — the two
 * states are publicly indistinguishable by design.
 */
export const CHARGE_NOT_FOUND_MESSAGE = 'No charge matches the requested identifier.';
export const CHARGE_RESULT_UNAVAILABLE_MESSAGE = 'Results are not available for this charge yet.';

/**
 * The ONLY message the volume arm may carry (Phase 36). Fires when the
 * published run has a volume row for the charge but zero recorded outcomes —
 * the charge is real and seen; nothing has resolved yet. Plain fact, no
 * prediction framing.
 */
export const CHARGE_VOLUME_ONLY_MESSAGE =
  'No final outcomes have been recorded for this charge yet.';

export const chargeSummarySchema = Type.Object(
  {
    id: Type.String({ format: 'uuid' }),
    slug: Type.String(),
    displayName: Type.String(),
    statuteCode: Type.Optional(Type.String()),
    grade: Type.Optional(Type.String()),
  },
  { additionalProperties: false },
);
export type ChargeSummary = Static<typeof chargeSummarySchema>;

export const chargeOutcomesSchema = Type.Object(
  {
    sampleSize: sampleSizeSchema,
    thinData: thinDataStatusSchema,
    rows: Type.Array(outcomeDistributionEntrySchema),
  },
  { additionalProperties: false },
);
export type ChargeOutcomes = Static<typeof chargeOutcomesSchema>;

export const chargeSentencingAvailableSchema = Type.Object(
  {
    available: Type.Literal(true),
    // The SENTENCING sample size — independent of the outcomes sample size.
    sampleSize: sampleSizeSchema,
    thinData: thinDataStatusSchema,
    rows: Type.Array(sentencingDistributionEntrySchema),
  },
  { additionalProperties: false },
);
export type ChargeSentencingAvailable = Static<typeof chargeSentencingAvailableSchema>;

export const chargeSentencingUnavailableSchema = Type.Object(
  {
    available: Type.Literal(false),
    message: Type.Literal(CHARGE_SENTENCING_UNAVAILABLE_MESSAGE),
  },
  { additionalProperties: false },
);
export type ChargeSentencingUnavailable = Static<typeof chargeSentencingUnavailableSchema>;

export const chargeSentencingSchema = Type.Union([
  chargeSentencingAvailableSchema,
  chargeSentencingUnavailableSchema,
]);
export type ChargeSentencing = Static<typeof chargeSentencingSchema>;

const resultLinksSchema = Type.Object(
  {
    methodology: Type.Literal('/methodology'),
    definitions: Type.Literal('/definitions'),
  },
  { additionalProperties: false },
);

/**
 * Charge-volume block (Phase 36, operator display ruling 2026-07-25): the
 * public payload carries the DEDUPLICATED totals only — `chargesSeen` counts
 * each charge journey once (an MC held charge traced to its CP continuation
 * is counted there, never twice), and `outcomesRecorded` equals the outcome
 * distribution's sample size by publish-blocking validation. The itemized
 * stage breakdown (pending / excluded / untraced held) is methodology-page
 * material and is deliberately NOT served here.
 *
 * Two arms on the success payload, the house section-level `available`
 * convention: absent covers a published run predating the volume population.
 */
export const chargeVolumePresentSchema = Type.Object(
  {
    available: Type.Literal(true),
    chargesSeen: Type.Integer({ minimum: 1 }),
    outcomesRecorded: Type.Integer({ minimum: 0 }),
  },
  { additionalProperties: false },
);
export type ChargeVolumePresent = Static<typeof chargeVolumePresentSchema>;

export const chargeVolumeAbsentSchema = Type.Object(
  {
    available: Type.Literal(false),
  },
  { additionalProperties: false },
);

export const chargeVolumeSchema = Type.Union([chargeVolumePresentSchema, chargeVolumeAbsentSchema]);
export type ChargeVolume = Static<typeof chargeVolumeSchema>;

export const chargeOnlyResultSuccessSchema = Type.Object(
  {
    charge: chargeSummarySchema,
    resultType: Type.Literal('charge_only'),
    geography: Type.Literal('philadelphia'),
    dateRange: dateRangeSchema,
    lastRefreshed: Type.String({ format: 'date-time' }),
    taxonomyVersion: taxonomyVersionSchema,
    // Public-safe run reference; no other run fields are ever exposed.
    aggregateRunId: Type.String({ format: 'uuid' }),
    outcomes: chargeOutcomesSchema,
    sentencing: chargeSentencingSchema,
    // Task 35.2: the conviction-grain index, a sibling of (never a change
    // to) the component-grain sentencing section above. Success arm only.
    sentencingIndex: chargeSentencingIndexSchema,
    // Phase 36: the deduplicated volume totals (sibling section, additive).
    volume: chargeVolumeSchema,
    links: resultLinksSchema,
  },
  { additionalProperties: false },
);
export type ChargeOnlyResultSuccess = Static<typeof chargeOnlyResultSuccessSchema>;

/**
 * HTTP 200 unavailable arm (task 13.2a): the charge entity exists but no
 * publishable aggregate does (no published run, or zero rows for the charge in
 * the published run — the two states are publicly indistinguishable by
 * design). Discriminated by `resultType`, mirroring the shipped 8.2
 * judge-unavailable pattern exactly. It carries charge identity as served, the
 * pinned code/message literals, and the methodology/definitions links only —
 * no distributions, sample sizes, or run metadata. Where the 8.2 arm carries a
 * `fallback` to the charge-only result, this arm carries `links`: the
 * charge-only result IS the terminal baseline, so there is nothing to fall
 * back to, and the links object matches the success arm's shape.
 */
export const chargeOnlyResultUnavailableSchema = Type.Object(
  {
    resultType: Type.Literal('charge_only_unavailable'),
    code: Type.Literal(PUBLIC_ERROR_CODES.CHARGE_RESULT_UNAVAILABLE),
    message: Type.Literal(CHARGE_RESULT_UNAVAILABLE_MESSAGE),
    charge: chargeSummarySchema,
    links: resultLinksSchema,
  },
  { additionalProperties: false },
);
export type ChargeOnlyResultUnavailable = Static<typeof chargeOnlyResultUnavailableSchema>;

/**
 * HTTP 200 volume arm (Phase 36, the R6-(ii) third union arm): the charge is
 * real and the published run has seen it — `volume.chargesSeen >= 1` — but no
 * recorded outcome exists yet, so there are no distributions to serve. It
 * replaces the dead-end unavailable arm for exactly this state (every newly
 * rostered charge starts here). Carries the run provenance the volume line
 * needs for honest captioning (dateRange, lastRefreshed, aggregateRunId) —
 * unlike the bare unavailable arm, which stays reserved for the truly-nothing
 * case (no published run, or no volume row in it) and still carries no run
 * metadata by design.
 */
export const chargeOnlyResultVolumeSchema = Type.Object(
  {
    resultType: Type.Literal('charge_only_volume'),
    message: Type.Literal(CHARGE_VOLUME_ONLY_MESSAGE),
    charge: chargeSummarySchema,
    geography: Type.Literal('philadelphia'),
    dateRange: dateRangeSchema,
    lastRefreshed: Type.String({ format: 'date-time' }),
    taxonomyVersion: taxonomyVersionSchema,
    aggregateRunId: Type.String({ format: 'uuid' }),
    volume: chargeVolumePresentSchema,
    links: resultLinksSchema,
  },
  { additionalProperties: false },
);
export type ChargeOnlyResultVolume = Static<typeof chargeOnlyResultVolumeSchema>;

// Structurally disjoint via the resultType literals; used as the single 200
// response schema so serialization stripping covers every arm.
export const chargeOnlyResultResponseSchema = Type.Union([
  chargeOnlyResultSuccessSchema,
  chargeOnlyResultVolumeSchema,
  chargeOnlyResultUnavailableSchema,
]);
export type ChargeOnlyResultResponse = Static<typeof chargeOnlyResultResponseSchema>;
