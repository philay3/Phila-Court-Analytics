import { TAXONOMY_VERSION } from '@pca/taxonomy';

import { publicOutcomeCategories, publicSentencingCategories } from '../public/categories.js';
import {
  CHARGE_RESULT_UNAVAILABLE_MESSAGE,
  CHARGE_SENTENCING_UNAVAILABLE_MESSAGE,
  type ChargeOnlyResultSuccess,
  type ChargeOnlyResultUnavailable,
  type ChargeSentencingAvailable,
} from '../public/charge-result.js';
import type { OutcomeDistribution, SentencingDistribution } from '../public/common.js';
import {
  JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE,
  type JudgeSpecificResultSuccess,
  type JudgeSpecificResultUnavailable,
} from '../public/judge-result.js';
import type { ChargeSentencingIndex, JudgeSentencingIndex } from '../public/sentencing-index.js';
import type { ChargeSearchResponse, JudgeSearchResponse } from '../public/search.js';
import {
  DATA_COVERAGE_COURT_SCOPE,
  DATA_COVERAGE_JURISDICTION,
  DATA_COVERAGE_PLANNED_DATA_START,
  DATA_COVERAGE_UNAVAILABLE_MESSAGE,
  type DataCoverageResponse,
} from '../public/data-coverage.js';
import { METHODOLOGY_SECTION_KEYS, type MethodologyResponse } from '../public/methodology.js';

// Fixtures are typed against the Static types and built from taxonomy artifacts, so a
// schema/type drift or a hand-copied category code fails to compile.

export function validOutcomeDistribution(): OutcomeDistribution {
  return {
    entries: publicOutcomeCategories.map((category, index) => ({
      categoryCode: category.code,
      displayName: category.displayName,
      count: index + 1,
      percentage: 100 / publicOutcomeCategories.length,
    })),
    sampleSize: 120,
    dateRange: { start: '2020-01-01', end: '2025-12-31' },
    thinData: false,
  };
}

export function validSentencingDistribution(): SentencingDistribution {
  return {
    entries: publicSentencingCategories.map((category, index) => ({
      categoryCode: category.code,
      displayName: category.displayName,
      count: index + 1,
      percentage: 100 / publicSentencingCategories.length,
    })),
    sampleSize: 45,
    dateRange: { start: '2021-06-01', end: '2025-06-30' },
    thinData: true,
  };
}

/**
 * Charge-arm present index (task 35.2): categories from the taxonomy (first
 * one duration-bearing with the all-or-none month trio, second without),
 * grade mix with the explicit ungraded bucket, dominant-count-first.
 */
export function validChargeSentencingIndex(): ChargeSentencingIndex {
  return {
    available: true,
    summary: {
      convictions: 60,
      sentencedConvictions: 58,
      wedgeCount: 2,
      wedgePercentage: 3.3,
      thinData: false,
      dateRange: { start: '2025-01-02', end: '2026-06-28' },
    },
    categories: publicSentencingCategories.slice(0, 2).map((category, index) => ({
      categoryCode: category.code,
      convictionCount: 20 - index,
      percentageOfSentenced: 34.5 - index,
      ...(index === 0
        ? { medianMinMonths: 11.5, medianMaxMonths: 23, minAssumedPercentage: 10 }
        : {}),
    })),
    grades: [
      { grade: 'F3', convictionCount: 30, percentageOfConvictions: 50 },
      { grade: 'M1', convictionCount: 20, percentageOfConvictions: 33.3 },
      { grade: 'ungraded', convictionCount: 10, percentageOfConvictions: 16.7 },
    ],
  };
}

/** Judge-arm present index: no grade mix key at all (ruling 2). */
export function validJudgeSentencingIndex(): JudgeSentencingIndex {
  return {
    available: true,
    summary: {
      convictions: 12,
      sentencedConvictions: 9,
      wedgeCount: 3,
      wedgePercentage: 25,
      thinData: true,
      dateRange: { start: '2025-02-10', end: '2026-05-15' },
    },
    categories: publicSentencingCategories.slice(0, 1).map((category) => ({
      categoryCode: category.code,
      convictionCount: 9,
      percentageOfSentenced: 100,
      medianMinMonths: 0.2,
      medianMaxMonths: 1.5,
      minAssumedPercentage: 90.1,
    })),
  };
}

export function validChargeOnlyResult(): ChargeOnlyResultSuccess {
  return {
    charge: {
      id: 'b8eb27a6-6fa1-4d0c-816b-96be2e3428b6',
      slug: 'example-charge',
      displayName: 'Example charge',
      statuteCode: '18 § 0000',
      grade: 'M1',
    },
    resultType: 'charge_only',
    geography: 'philadelphia',
    dateRange: { start: '2025-01-01', end: '2026-06-30' },
    lastRefreshed: '2026-07-01T04:30:00Z',
    taxonomyVersion: TAXONOMY_VERSION,
    aggregateRunId: '2f9c1e04-8d5b-4c33-9a67-0d1e2f3a4b5c',
    outcomes: {
      sampleSize: 120,
      thinData: false,
      rows: publicOutcomeCategories.map((category, index) => ({
        categoryCode: category.code,
        displayName: category.displayName,
        count: index + 1,
        percentage: 100 / publicOutcomeCategories.length,
      })),
    },
    sentencing: {
      available: true,
      sampleSize: 45,
      thinData: true,
      rows: publicSentencingCategories.map((category, index) => ({
        categoryCode: category.code,
        displayName: category.displayName,
        count: index + 1,
        percentage: 100 / publicSentencingCategories.length,
      })),
    },
    sentencingIndex: validChargeSentencingIndex(),
    links: { methodology: '/methodology', definitions: '/definitions' },
  };
}

export function validChargeOnlyResultSentencingUnavailable(): ChargeOnlyResultSuccess {
  return {
    ...validChargeOnlyResult(),
    sentencing: { available: false, message: CHARGE_SENTENCING_UNAVAILABLE_MESSAGE },
  };
}

export function validChargeOnlyResultUnavailable(): ChargeOnlyResultUnavailable {
  const base = validChargeOnlyResult();
  return {
    resultType: 'charge_only_unavailable',
    code: 'CHARGE_RESULT_UNAVAILABLE',
    message: CHARGE_RESULT_UNAVAILABLE_MESSAGE,
    charge: base.charge,
    links: base.links,
  };
}

export function validJudgeSpecificResultSuccess(): JudgeSpecificResultSuccess {
  const base = validChargeOnlyResult();
  // Cast: validChargeOnlyResult always builds the available sentencing arm;
  // the return type just widens it to the union.
  const baseSentencing = base.sentencing as ChargeSentencingAvailable;
  return {
    resultType: 'judge_specific',
    charge: base.charge,
    judge: {
      id: 'c4d5e6f7-1a2b-4c3d-8e9f-0a1b2c3d4e5f',
      slug: 'example-judge',
      displayName: 'Example judge',
    },
    geography: 'philadelphia',
    dateRange: base.dateRange,
    lastRefreshed: base.lastRefreshed,
    taxonomyVersion: TAXONOMY_VERSION,
    aggregateRunId: base.aggregateRunId,
    // Four independent sample sizes: the judge-scoped blocks reuse the base
    // fixture's shapes with distinct ns.
    judgeSpecific: {
      outcomes: { ...base.outcomes, sampleSize: 14 },
      sentencing: { ...baseSentencing, sampleSize: 9 },
    },
    baseline: { outcomes: base.outcomes, sentencing: base.sentencing },
    sentencingIndex: validJudgeSentencingIndex(),
    links: base.links,
  };
}

export function validJudgeSpecificResultUnavailable(): JudgeSpecificResultUnavailable {
  const success = validJudgeSpecificResultSuccess();
  return {
    resultType: 'judge_specific_unavailable',
    code: 'JUDGE_SPECIFIC_RESULT_UNAVAILABLE',
    message: JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE,
    charge: success.charge,
    judge: success.judge,
    fallback: { chargeOnlyResultPath: '/api/v1/public/results/charge/example-charge' },
  };
}

export function validChargeSearchResponse(): ChargeSearchResponse {
  return {
    results: [
      {
        id: 'b8eb27a6-6fa1-4d0c-816b-96be2e3428b6',
        slug: 'example-charge',
        displayName: 'Example charge',
        statuteCode: '18 § 0000',
        grade: 'M1',
        matchedAlias: 'example alias',
      },
      {
        // Optionals omitted — the shared convention is omission, not null.
        id: '2f9c1e04-8d5b-4c33-9a67-0d1e2f3a4b5c',
        slug: 'minimal-charge',
        displayName: 'Minimal charge',
      },
    ],
  };
}

export function validJudgeSearchResponse(): JudgeSearchResponse {
  return {
    results: [
      {
        id: 'c4d5e6f7-1a2b-4c3d-8e9f-0a1b2c3d4e5f',
        slug: 'example-judge',
        displayName: 'Example judge',
        matchedAlias: 'example alias',
      },
      {
        // Optionals omitted — the shared convention is omission, not null.
        id: '9e8d7c6b-5a4f-4e3d-9c2b-1a0f9e8d7c6b',
        slug: 'minimal-judge',
        displayName: 'Minimal judge',
      },
    ],
  };
}

export function validMethodologyResponse(): MethodologyResponse {
  // Built by iterating the exported key list, so a key added to the schema
  // without being added to METHODOLOGY_SECTION_KEYS fails to compile here.
  const sections = Object.fromEntries(
    METHODOLOGY_SECTION_KEYS.map((key) => [
      key,
      { heading: `Heading for ${key}`, body: `Body copy for ${key}.` },
    ]),
  ) as MethodologyResponse['sections'];
  return { sections };
}

export function validDataCoverageAvailable(): DataCoverageResponse {
  return {
    jurisdiction: DATA_COVERAGE_JURISDICTION,
    courtScope: DATA_COVERAGE_COURT_SCOPE,
    plannedDataStart: DATA_COVERAGE_PLANNED_DATA_START,
    knownLimitations: ['An example public-safe limitation.'],
    coverage: {
      available: true,
      dataStart: '2025-01-01',
      dataEnd: '2026-06-30',
      lastRefreshed: '2026-07-01T02:00:00Z',
      taxonomyVersion: TAXONOMY_VERSION,
      aggregateRunId: '2f9c1e04-8d5b-4c33-9a67-0d1e2f3a4b5c',
      counts: {
        chargesWithOutcomeAggregates: 5,
        chargesWithSentencingAggregates: 3,
        judgeChargePairs: 3,
      },
    },
  };
}

export function validDataCoverageUnavailable(): DataCoverageResponse {
  return {
    ...validDataCoverageAvailable(),
    coverage: { available: false, message: DATA_COVERAGE_UNAVAILABLE_MESSAGE },
  };
}
