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
