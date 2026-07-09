/**
 * Homepage user-facing copy (task 12.1). Every string the homepage renders
 * lives here as an exported constant so the app/-walking copy guard covers it
 * automatically and the `home-copy.test.ts` suite can scan each value with
 * `scanPublicCopy` from @pca/shared directly.
 *
 * Disclaimer sourcing: @pca/shared exposes no pinned disclaimer *literal*
 * suitable for rendering (its `notPrediction` is a served-content schema
 * section, and `GUARDED_DISCLAIMER_PHRASES` are scanner guards, not prose), so
 * the framing copy below is written here. It deliberately uses the exact
 * guarded phrases "not a prediction" and "not legal advice" so it passes the
 * copy-safety scanner.
 *
 * No inline JSX string literals for user-facing copy — including input
 * placeholder text — may live in page.tsx or SearchForm.tsx; add them here.
 */
export const HOME_COPY = {
  heading: 'Philadelphia Court Outcomes',
  intro:
    'Philadelphia Court Outcomes presents historical aggregate outcomes from Philadelphia criminal court data. It summarizes how charges were resolved in past cases — historical outcome distributions and historical sentencing distributions, shown Philadelphia-wide and, when you add a judge, as judge-specific results where available — always with the sample size behind each figure.',
  disclaimer:
    'This site describes what happened in past cases. It is not a prediction of any current or future case, and it is not legal advice. Where the underlying data is thin, we say so rather than draw conclusions.',
  searchHeading: 'Search court outcomes',
  chargeLabel: 'Charge',
  chargePlaceholder: 'Search by charge',
  chargeHelp: 'Start with the charge you want to look up.',
  judgeLabel: 'Judge (optional)',
  judgePlaceholder: 'Add a judge',
  judgeHelp:
    'Adding a judge is optional. Leave it blank for Philadelphia-wide results, or add one to see judge-specific results where available.',
  linksIntro: 'To understand these figures:',
  methodologyLinkText: 'Methodology',
  methodologyLinkDescription: 'how these figures are produced',
  dataCoverageLinkText: 'Data Coverage',
  dataCoverageLinkDescription: 'the time window and courts the data covers',
} as const;
