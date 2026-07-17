import type { MethodologyResponse } from '@pca/shared';

/**
 * Methodology copy for GET /public/methodology — static per deploy, computed
 * at module load, no database dependency (the 9.1 static-response pattern).
 * Plain-English and neutral throughout; the route test scans the full
 * response body with the @pca/shared copy-safety scanner (plus stricter
 * route-specific patterns), so any copy edit here that introduces
 * prediction/ranking/advice vocabulary fails tests. The guarded disclaimer
 * phrases live in @pca/shared (GUARDED_DISCLAIMER_PHRASES, migrated in 10.2).
 */

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
        'Coverage begins on January 1, 2025 and applies that date twice: only ' +
        'cases filed on or after January 1, 2025 are covered, and only ' +
        'disposition or sentencing events on or after that date are counted. A ' +
        'case filed earlier is excluded, even when its disposition or ' +
        'sentencing happened after coverage began.',
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
        'Every figure is shown with its sample size: the number of records it ' +
        'summarizes (charge dispositions for outcome figures, and individual ' +
        'sentence components for sentencing figures). Figures built from more data ' +
        'are more stable, so the sample size appears on every figure to show how ' +
        'much data stands behind it.',
    },
    thinData: {
      heading: 'Thin data',
      body:
        'When a figure rests on a small sample, it is labeled as thin data and ' +
        'displayed with that warning rather than hidden. Small samples can shift ' +
        'noticeably as new cases arrive, so thin-data figures should be read with ' +
        'extra caution. At this stage most judge-specific figures are thin: the ' +
        'thin-data warning is the norm for judge-level results, and judge-level ' +
        'coverage deepens as collection continues.',
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
      // SD-15 disclosure: sentencing dates are captured independently of
      // disposition dates, usually coincide, can fall earlier, and decide
      // covered-period eligibility for sentencing figures.
      body:
        'Sentencing distributions summarize the sentence types recorded for charges ' +
        'that reached sentencing. A single sentencing event can include several ' +
        'components (for example probation plus a fine), and each component is ' +
        'counted as its own entry, so the sentencing sample size counts sentence ' +
        'components rather than sentenced charges. It is measured separately from ' +
        'the outcome sample size and can be smaller or larger: not every disposed ' +
        'charge reaches sentencing, while each charge that does can contribute more ' +
        'than one component. Sentencing figures may be unavailable for some charges. ' +
        'Sentencing dates are recorded independently of disposition dates: the two ' +
        'usually coincide, but a small share of sentencing dates fall earlier, and ' +
        'whether a sentencing event is inside the covered period is decided by the ' +
        'sentencing date itself.',
    },
    limitations: {
      heading: 'Known limitations',
      // The Sprint 2 seeded-data disclosure lived here until the first real
      // aggregate run was published (task 28.2); published figures now come
      // from real Philadelphia court records.
      // Ambiguity handling (no "admin review in this version"-style wording:
      // this route's tests forbid internal-process vocabulary): unclear
      // records are excluded automatically, and no figure is corrected by
      // hand in this version — a manual correction process is future work.
      body:
        'Coverage starts on January 1, 2025, so earlier history is absent. ' +
        'Collection is ongoing: the covered records are a growing subset of ' +
        'Philadelphia criminal cases, and figures change as newly collected ' +
        'records are aggregated. Docket sheets are summaries and may be amended ' +
        'after we aggregate them. Aggregation groups many distinct dispositions ' +
        'into broad categories, and some charges have little or no data yet. ' +
        'Where the data is thin, the figures say so. Records whose outcome or ' +
        'judge attribution is unclear are excluded from the figures automatically ' +
        'rather than resolved by hand, and in this version no figure is adjusted ' +
        'or corrected manually after aggregation — a process for that is planned ' +
        'as future work. At this stage, dismissals are underrepresented in the ' +
        'figures: dismissals tend to take longer to resolve than convictions, ' +
        'and records without a recorded event date are excluded until one is ' +
        'recorded, so dismissal figures fill in more slowly than other outcomes.',
    },
  },
};
