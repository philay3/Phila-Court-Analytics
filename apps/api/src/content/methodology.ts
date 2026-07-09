import type { MethodologyResponse } from '@pca/shared';

/**
 * Methodology copy for GET /public/methodology — static per deploy, computed
 * at module load, no database dependency (the 9.1 static-response pattern).
 * Plain-English and neutral throughout; the route test runs the word-boundary
 * forbidden-term regexes over the full response body, so any copy edit here
 * that introduces prediction/ranking/advice vocabulary fails tests.
 */

/**
 * The ONLY phrasings in which prediction/advice vocabulary may appear in
 * public methodology copy. The copy-safety test strips these exact phrases
 * (case-insensitively) before applying the forbidden-term regexes, so any
 * unguarded use of the vocabulary still fails. Migrates to @pca/shared with
 * the other copy-guard constants in task 10.2.
 */
export const GUARDED_DISCLAIMER_PHRASES = [
  'not a prediction',
  'do not predict',
  'not legal advice',
  'does not provide legal advice',
] as const;

export const METHODOLOGY_CONTENT: MethodologyResponse = {
  sections: {
    dataSource: {
      heading: 'Where the data comes from',
      body:
        'Figures are built from public docket sheets published on the Pennsylvania ' +
        'Unified Judicial System (UJS) portal. Coverage is limited to criminal cases ' +
        'heard in the Philadelphia courts.',
    },
    dataRange: {
      heading: 'What time period is covered',
      body:
        'Coverage begins on January 1, 2025 and is anchored to the date of the ' +
        'disposition or sentencing event, not the filing date. A case filed earlier ' +
        'is included when its qualifying event happened on or after that date.',
    },
    whatResultsMean: {
      heading: 'What the results mean',
      body:
        'Every figure is a historical aggregate: a summary of how charges were ' +
        'resolved in past Philadelphia cases during the covered period. Results ' +
        'describe groups of past cases as a whole, never any individual case.',
    },
    notPrediction: {
      heading: 'Not a prediction',
      body:
        'These figures are historical summaries — they are not a prediction of any ' +
        'future outcome. Past distributions do not predict what a court will decide ' +
        'in any current or future case.',
    },
    notLegalAdvice: {
      heading: 'Not legal advice',
      body:
        'This site does not provide legal advice. Nothing here is a substitute for ' +
        'consulting a licensed attorney about a specific situation.',
    },
    sampleSize: {
      heading: 'Sample size',
      body:
        'Every figure is shown with its sample size: the number of charge ' +
        'dispositions or sentencing events it summarizes. Figures built from more ' +
        'data are more stable, so the sample size appears on every figure to show ' +
        'how much data stands behind it.',
    },
    thinData: {
      heading: 'Thin data',
      body:
        'When a figure rests on a small sample, it is labeled as thin data and ' +
        'displayed with that warning rather than hidden. Small samples can shift ' +
        'noticeably as new cases arrive, so thin-data figures should be read with ' +
        'extra caution.',
    },
    chargeLevelAnalytics: {
      heading: 'Charge-level figures',
      body:
        'Outcomes and sentences are attributed at the level of the individual ' +
        'charge, not the docket. A single docket can carry several charges, each ' +
        'resolved differently, so charge-level figures can differ from a ' +
        'whole-case reading.',
    },
    sentencing: {
      heading: 'Sentencing figures',
      body:
        'Sentencing distributions summarize the sentence types recorded for charges ' +
        'that reached sentencing. They carry their own sentencing sample size, ' +
        'separate from and typically smaller than the outcome sample size, and may ' +
        'be unavailable for some charges.',
    },
    limitations: {
      heading: 'Known limitations',
      // Seeded-data disclosure (Sprint 2 standing requirement): every currently
      // published figure is fabricated seed data. Remove the final two
      // sentences in Sprint 7 when real aggregates replace the seeds.
      body:
        'Coverage starts on January 1, 2025, so earlier history is absent. Docket ' +
        'sheets are summaries and may be amended after we aggregate them. ' +
        'Aggregation groups many distinct dispositions into broad categories, and ' +
        'some charges have little or no data yet. Where the data is thin, the ' +
        'figures say so. All figures currently published are seeded demonstration ' +
        'data created for development and testing. They do not describe real ' +
        'Philadelphia court outcomes.',
    },
  },
};
