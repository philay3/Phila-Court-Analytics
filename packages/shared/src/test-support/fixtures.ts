import { TAXONOMY_VERSION } from '@pca/taxonomy';

import { publicOutcomeCategories, publicSentencingCategories } from '../public/categories.js';
import type { OutcomeDistribution, SentencingDistribution } from '../public/common.js';
import type { ChargeOnlyResult, JudgeSpecificResult } from '../public/results.js';
import type { ChargeSearchResponse, JudgeSearchResponse } from '../public/search.js';

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

export function validChargeOnlyResult(): ChargeOnlyResult {
  return {
    chargeDisplayName: 'Example charge',
    geographyLabel: 'Philadelphia-wide',
    outcomes: validOutcomeDistribution(),
    sentencing: validSentencingDistribution(),
    taxonomyVersion: TAXONOMY_VERSION,
    lastRefreshed: '2026-07-01T04:30:00Z',
  };
}

export function validJudgeSpecificResult(): JudgeSpecificResult {
  return {
    chargeDisplayName: 'Example charge',
    judgeDisplayName: 'Example judge',
    judgeOutcomes: validOutcomeDistribution(),
    judgeSentencing: validSentencingDistribution(),
    baselineOutcomes: validOutcomeDistribution(),
    baselineSentencing: validSentencingDistribution(),
    taxonomyVersion: TAXONOMY_VERSION,
    lastRefreshed: '2026-07-01T04:30:00Z',
  };
}

export function validChargeSearchResponse(): ChargeSearchResponse {
  return {
    results: [{ chargeId: 'charge-1', displayName: 'Example charge', slug: 'example-charge' }],
  };
}

export function validJudgeSearchResponse(): JudgeSearchResponse {
  return {
    results: [{ judgeId: 'judge-1', displayName: 'Example judge', slug: 'example-judge' }],
  };
}
