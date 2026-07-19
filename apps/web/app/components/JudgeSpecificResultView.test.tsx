import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import {
  CHARGE_SENTENCING_UNAVAILABLE_MESSAGE,
  SENTENCING_DETAIL_CAPTION,
  SENTENCING_INDEX_CAPTION,
  type JudgeSentencingIndexPresent,
  type JudgeSpecificResultSuccess,
  type OutcomeDistributionEntry,
  type ResultDistributions,
  type SentencingDistributionEntry,
} from '@pca/shared';
import {
  RESULT_TYPE_JUDGE_SPECIFIC_LABEL,
  THIN_DATA_LABEL,
  formatAggregateRunLabel,
  formatDateRange,
  formatLastRefreshed,
  formatRecordsLabel,
  formatSentenceComponentsLabel,
  formatZeroSentencedFallback,
} from '../lib/formatters.js';
import { RESULT_DISPLAY_COPY } from './result-display-copy.js';
import { CHARGE_RESULT_COPY } from './charge-result-copy.js';
import { JUDGE_RESULT_COPY } from './judge-result-copy.js';
import { JudgeSpecificResultView } from './JudgeSpecificResultView.js';

// next/link is stubbed so the page links render under jsdom without an App
// Router provider.
vi.mock('next/link', () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) => (
    <a href={typeof href === 'string' ? href : ''} {...rest}>
      {children}
    </a>
  ),
}));

const CHARGE = {
  id: '00000000-0000-0000-0000-000000000001',
  slug: 'theft',
  displayName: 'Theft',
} as const;

const JUDGE = {
  id: '00000000-0000-0000-0000-000000000002',
  slug: 'example-judge',
  displayName: 'Example judge',
} as const;

const OUTCOME_ROWS: OutcomeDistributionEntry[] = [
  { categoryCode: 'dismissed', displayName: 'Dismissed', count: 120, percentage: 12 },
  { categoryCode: 'guilty_plea', displayName: 'Guilty plea', count: 640, percentage: 64 },
  { categoryCode: 'acquittal', displayName: 'Acquittal', count: 240, percentage: 24 },
];
const SENTENCING_ROWS: SentencingDistributionEntry[] = [
  { categoryCode: 'probation', displayName: 'Probation', count: 300, percentage: 50 },
  { categoryCode: 'incarceration', displayName: 'Incarceration', count: 180, percentage: 30 },
  { categoryCode: 'fine', displayName: 'Fine', count: 120, percentage: 20 },
];

// Four independent sample sizes, all distinct so each renders as a unique
// on-screen reconciled label string (35.3 pin 11).
const JUDGE_OUTCOME_N = 14;
const JUDGE_SENTENCING_N = 9;
const BASELINE_OUTCOME_N = 1000;
const BASELINE_SENTENCING_N = 600;
const AGGREGATE_RUN_ID = '00000000-0000-0000-0000-0000000000aa';

// Fabricated cell index (no grades at this grain, ruling 2).
const CELL_INDEX_PRESENT: JudgeSentencingIndexPresent = {
  available: true,
  summary: {
    convictions: 49,
    sentencedConvictions: 45,
    wedgeCount: 4,
    wedgePercentage: 8.2,
    thinData: false,
    dateRange: { start: '2025-02-01', end: '2026-06-10' },
  },
  categories: [
    {
      categoryCode: 'probation',
      convictionCount: 30,
      percentageOfSentenced: 66.7,
      medianMinMonths: 2,
      medianMaxMonths: 6,
      minAssumedPercentage: 40,
    },
    { categoryCode: 'fine', convictionCount: 20, percentageOfSentenced: 44.4 },
  ],
};

const CELL_INDEX_ZERO_SENTENCED: JudgeSentencingIndexPresent = {
  available: true,
  summary: {
    convictions: 7,
    sentencedConvictions: 0,
    wedgeCount: 7,
    wedgePercentage: 100,
    thinData: true,
    dateRange: { start: '2025-02-01', end: '2026-06-10' },
  },
  categories: [],
};

function makeScope(outcomeN: number, sentencingN: number): ResultDistributions {
  return {
    outcomes: { sampleSize: outcomeN, thinData: false, rows: OUTCOME_ROWS },
    sentencing: {
      available: true,
      sampleSize: sentencingN,
      thinData: false,
      rows: SENTENCING_ROWS,
    },
  };
}

function makeSuccess(
  overrides: Partial<JudgeSpecificResultSuccess> = {},
): JudgeSpecificResultSuccess {
  return {
    resultType: 'judge_specific',
    charge: CHARGE,
    judge: JUDGE,
    geography: 'philadelphia',
    dateRange: { start: '2025-01-01', end: '2026-06-30' },
    lastRefreshed: '2026-07-01T14:30:00.000Z',
    taxonomyVersion: '1.0.0',
    aggregateRunId: AGGREGATE_RUN_ID,
    judgeSpecific: makeScope(JUDGE_OUTCOME_N, JUDGE_SENTENCING_N),
    baseline: makeScope(BASELINE_OUTCOME_N, BASELINE_SENTENCING_N),
    // Default fixture keeps the absent arm: today's page (pin 2), with the
    // present arms exercised by their own tests below.
    sentencingIndex: { available: false },
    links: { methodology: '/methodology', definitions: '/definitions' },
    ...overrides,
  };
}

function sectionOrder(container: HTMLElement): string[] {
  // Top-level pinned order only (DP-3): the metadata aside itself is a pinned
  // section; testids nested inside it are its contents, not part of the
  // page-level order (parity with the ChargeOnlyResultView helper).
  return Array.from(container.querySelectorAll('[data-testid^="section-"]'))
    .filter((element) => {
      const aside = element.closest('[data-testid="section-metadata"]');
      return aside === null || aside === element;
    })
    .map((element) => element.getAttribute('data-testid')) as string[];
}

describe('JudgeSpecificResultView', () => {
  it('renders both names, the judge-specific label, dates, and all four distributions with distinct sample sizes', () => {
    render(<JudgeSpecificResultView data={makeSuccess()} />);

    // Both identities.
    expect(screen.getByRole('heading', { level: 1, name: CHARGE.displayName })).toBeInTheDocument();
    expect(screen.getByText(JUDGE.displayName)).toBeInTheDocument();

    // Framing label + result-level metadata.
    expect(screen.getByText(RESULT_TYPE_JUDGE_SPECIFIC_LABEL)).toBeInTheDocument();
    expect(
      screen.getByText(formatDateRange({ start: '2025-01-01', end: '2026-06-30' })),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        `${CHARGE_RESULT_COPY.lastRefreshedLabel}: ${formatLastRefreshed('2026-07-01T14:30:00.000Z')}`,
      ),
    ).toBeInTheDocument();

    // Both section headings, exact literals.
    expect(
      screen.getByRole('heading', {
        level: 2,
        name: JUDGE_RESULT_COPY.sectionJudgeSpecificHeading,
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { level: 2, name: JUDGE_RESULT_COPY.sectionBaselineHeading }),
    ).toBeInTheDocument();

    // Four distribution slots, each scoped to its own leaf container so the
    // shared captions do not collide, and each carrying its own sample size.
    const judgeOutcome = within(screen.getByTestId('section-judge-outcome'));
    expect(
      judgeOutcome.getByRole('table', { name: RESULT_DISPLAY_COPY.outcomeCaption }),
    ).toBeInTheDocument();
    expect(judgeOutcome.getByText(formatRecordsLabel(JUDGE_OUTCOME_N))).toBeInTheDocument();

    const judgeSentencing = within(screen.getByTestId('section-judge-sentencing'));
    expect(
      judgeSentencing.getByRole('table', { name: RESULT_DISPLAY_COPY.sentencingCaption }),
    ).toBeInTheDocument();
    expect(
      judgeSentencing.getByText(formatSentenceComponentsLabel(JUDGE_SENTENCING_N)),
    ).toBeInTheDocument();

    const baselineOutcome = within(screen.getByTestId('section-baseline-outcome'));
    expect(
      baselineOutcome.getByRole('table', { name: RESULT_DISPLAY_COPY.outcomeCaption }),
    ).toBeInTheDocument();
    expect(baselineOutcome.getByText(formatRecordsLabel(BASELINE_OUTCOME_N))).toBeInTheDocument();

    const baselineSentencing = within(screen.getByTestId('section-baseline-sentencing'));
    expect(
      baselineSentencing.getByRole('table', { name: RESULT_DISPLAY_COPY.sentencingCaption }),
    ).toBeInTheDocument();
    expect(
      baselineSentencing.getByText(formatSentenceComponentsLabel(BASELINE_SENTENCING_N)),
    ).toBeInTheDocument();

    // Coverage note, responsible-use notice + methodology/definitions links.
    expect(screen.getByText(RESULT_DISPLAY_COPY.coverageNote)).toBeInTheDocument();
    expect(screen.getByText(RESULT_DISPLAY_COPY.responsibleUseHistorical)).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: CHARGE_RESULT_COPY.methodologyLinkText }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: CHARGE_RESULT_COPY.definitionsLinkText }),
    ).toBeInTheDocument();
  });

  it('renders rows in the server-authoritative order within a slot (taxonomy-safe, no client sort)', () => {
    render(<JudgeSpecificResultView data={makeSuccess()} />);

    const judgeOutcomeTable = within(screen.getByTestId('section-judge-outcome')).getByRole(
      'table',
      {
        name: RESULT_DISPLAY_COPY.outcomeCaption,
      },
    );
    const rowHeaders = within(judgeOutcomeTable)
      .getAllByRole('rowheader')
      .map((cell) => cell.textContent);
    // Order matches the fixture (server order), not an alphabetized re-sort.
    expect(rowHeaders?.[0]).toContain('Dismissed');
    expect(rowHeaders?.[1]).toContain('Guilty plea');
    expect(rowHeaders?.[2]).toContain('Acquittal');
  });

  it('shows the page-level thin-data callout as a pure OR over the API booleans, keeping per-slot badges', () => {
    // Only the baseline sentencing block is thin; the page-level callout must
    // still appear (OR over all four rendered distributions).
    const data = makeSuccess({
      baseline: {
        outcomes: { sampleSize: BASELINE_OUTCOME_N, thinData: false, rows: OUTCOME_ROWS },
        sentencing: { available: true, sampleSize: 7, thinData: true, rows: SENTENCING_ROWS },
      },
    });
    render(<JudgeSpecificResultView data={data} />);

    // Page-level callout (supplements, never replaces, the per-slot badge).
    expect(screen.getByText(RESULT_DISPLAY_COPY.thinDataCalloutBody)).toBeInTheDocument();
    // The per-slot badge (pinned formatter label) still renders inside the thin
    // baseline sentencing slot.
    const baselineSentencing = within(screen.getByTestId('section-baseline-sentencing'));
    expect(baselineSentencing.getByText(THIN_DATA_LABEL)).toBeInTheDocument();
  });

  it('omits the page-level thin-data callout when no rendered distribution is thin', () => {
    render(<JudgeSpecificResultView data={makeSuccess()} />);
    expect(screen.queryByText(RESULT_DISPLAY_COPY.thinDataCalloutBody)).not.toBeInTheDocument();
    expect(screen.queryByTestId('section-thin-data')).not.toBeInTheDocument();
  });

  it('renders a sentencing-unavailable slot independently without failing the rest of the page', () => {
    // The judge sentencing slot is unavailable; every other slot still renders.
    const data = makeSuccess({
      judgeSpecific: {
        outcomes: { sampleSize: JUDGE_OUTCOME_N, thinData: false, rows: OUTCOME_ROWS },
        sentencing: { available: false, message: CHARGE_SENTENCING_UNAVAILABLE_MESSAGE },
      },
    });
    render(<JudgeSpecificResultView data={data} />);

    // The judge sentencing slot shows the pinned shared message, not a table.
    const judgeSentencing = within(screen.getByTestId('section-judge-sentencing'));
    expect(judgeSentencing.getByText(CHARGE_SENTENCING_UNAVAILABLE_MESSAGE)).toBeInTheDocument();
    expect(
      judgeSentencing.queryByRole('table', { name: RESULT_DISPLAY_COPY.sentencingCaption }),
    ).not.toBeInTheDocument();

    // The judge outcome and both baseline slots still render in full.
    expect(
      within(screen.getByTestId('section-judge-outcome')).getByRole('table', {
        name: RESULT_DISPLAY_COPY.outcomeCaption,
      }),
    ).toBeInTheDocument();
    expect(
      within(screen.getByTestId('section-baseline-sentencing')).getByRole('table', {
        name: RESULT_DISPLAY_COPY.sentencingCaption,
      }),
    ).toBeInTheDocument();
  });

  it('renders the remove-filter link pointing at the charge-only page', () => {
    render(<JudgeSpecificResultView data={makeSuccess()} />);
    const link = screen.getByRole('link', { name: JUDGE_RESULT_COPY.removeFilterLinkText });
    expect(link).toHaveAttribute('href', `/charges/${CHARGE.slug}`);
  });

  it('renders top-level leaf sections in the pinned mobile DOM order (both scopes sentencing-available)', () => {
    const { container } = render(
      <JudgeSpecificResultView
        data={makeSuccess({
          judgeSpecific: {
            outcomes: { sampleSize: JUDGE_OUTCOME_N, thinData: true, rows: OUTCOME_ROWS },
            sentencing: {
              available: true,
              sampleSize: JUDGE_SENTENCING_N,
              thinData: false,
              rows: SENTENCING_ROWS,
            },
          },
        })}
      />,
    );

    expect(sectionOrder(container)).toEqual([
      'section-summary',
      'section-responsible-use',
      'section-thin-data',
      'section-judge-sentencing',
      'section-judge-outcome',
      'section-baseline-sentencing',
      'section-baseline-outcome',
      'section-metadata',
    ]);
  });

  // Task 33.2 pinned decision 4: each scope orders its slots independently on
  // its own `sentencing.available` flag — available → sentencing first,
  // unavailable → outcome first with the callout below. The remaining three
  // availability combinations (both unavailable + one mixed case per
  // direction) complete the matrix; the both-available order is pinned above.
  const UNAVAILABLE_SENTENCING = {
    available: false,
    message: CHARGE_SENTENCING_UNAVAILABLE_MESSAGE,
  } as const;

  function makeUnavailableScope(outcomeN: number): ResultDistributions {
    return {
      outcomes: { sampleSize: outcomeN, thinData: false, rows: OUTCOME_ROWS },
      sentencing: UNAVAILABLE_SENTENCING,
    };
  }

  it('orders both scopes outcome-first when both sentencing slots are unavailable', () => {
    const { container } = render(
      <JudgeSpecificResultView
        data={makeSuccess({
          judgeSpecific: makeUnavailableScope(JUDGE_OUTCOME_N),
          baseline: makeUnavailableScope(BASELINE_OUTCOME_N),
        })}
      />,
    );

    expect(sectionOrder(container)).toEqual([
      'section-summary',
      'section-responsible-use',
      'section-judge-outcome',
      'section-judge-sentencing',
      'section-baseline-outcome',
      'section-baseline-sentencing',
      'section-metadata',
    ]);
  });

  it('mixes orders independently: judge sentencing unavailable, baseline available', () => {
    const { container } = render(
      <JudgeSpecificResultView
        data={makeSuccess({ judgeSpecific: makeUnavailableScope(JUDGE_OUTCOME_N) })}
      />,
    );

    expect(sectionOrder(container)).toEqual([
      'section-summary',
      'section-responsible-use',
      'section-judge-outcome',
      'section-judge-sentencing',
      'section-baseline-sentencing',
      'section-baseline-outcome',
      'section-metadata',
    ]);
  });

  it('mixes orders independently: judge sentencing available, baseline unavailable', () => {
    const { container } = render(
      <JudgeSpecificResultView
        data={makeSuccess({ baseline: makeUnavailableScope(BASELINE_OUTCOME_N) })}
      />,
    );

    expect(sectionOrder(container)).toEqual([
      'section-summary',
      'section-responsible-use',
      'section-judge-sentencing',
      'section-judge-outcome',
      'section-baseline-outcome',
      'section-baseline-sentencing',
      'section-metadata',
    ]);
  });

  it('leads the judge scope with the cell index and no grade line (35.3 pin 6); baseline unchanged', () => {
    const { container } = render(
      <JudgeSpecificResultView data={makeSuccess({ sentencingIndex: CELL_INDEX_PRESENT })} />,
    );

    expect(sectionOrder(container)).toEqual([
      'section-summary',
      'section-responsible-use',
      'section-judge-sentencing-index',
      'section-judge-sentencing',
      'section-judge-outcome',
      'section-baseline-sentencing',
      'section-baseline-outcome',
      'section-metadata',
    ]);

    const indexSection = within(screen.getByTestId('section-judge-sentencing-index'));
    expect(indexSection.getByRole('table', { name: SENTENCING_INDEX_CAPTION })).toBeInTheDocument();
    expect(indexSection.getByText('Sentenced convictions: 45')).toBeInTheDocument();
    expect(indexSection.getByTestId('index-wedge-disclosure')).toBeInTheDocument();
    // No grades exist at this grain (ruling 2): no grade line anywhere.
    expect(screen.queryByTestId('index-grade-mix')).not.toBeInTheDocument();

    // The judge-scope component block renders below under the detail caption;
    // the baseline keeps today's caption.
    const judgeSentencing = within(screen.getByTestId('section-judge-sentencing'));
    expect(
      judgeSentencing.getByRole('table', { name: SENTENCING_DETAIL_CAPTION }),
    ).toBeInTheDocument();
    const baselineSentencing = within(screen.getByTestId('section-baseline-sentencing'));
    expect(
      baselineSentencing.getByRole('table', { name: RESULT_DISPLAY_COPY.sentencingCaption }),
    ).toBeInTheDocument();
  });

  it('renders the judge scope outcome-first with the fallback line on the zero-sentenced cell arm', () => {
    const { container } = render(
      <JudgeSpecificResultView
        data={makeSuccess({
          sentencingIndex: CELL_INDEX_ZERO_SENTENCED,
          judgeSpecific: makeUnavailableScope(JUDGE_OUTCOME_N),
        })}
      />,
    );

    // Cell summary is thin → page-level callout renders.
    expect(sectionOrder(container)).toEqual([
      'section-summary',
      'section-responsible-use',
      'section-thin-data',
      'section-judge-outcome',
      'section-judge-sentencing-index',
      'section-baseline-sentencing',
      'section-baseline-outcome',
      'section-metadata',
    ]);

    const indexSlot = within(screen.getByTestId('section-judge-sentencing-index'));
    expect(
      indexSlot.getByText(
        formatZeroSentencedFallback(CELL_INDEX_ZERO_SENTENCED.summary.convictions),
      ),
    ).toBeInTheDocument();
    // The generic notice is replaced in the judge scope (ruling Q4); the
    // baseline scope still renders its full table, so the pinned message
    // appears nowhere on this arm.
    expect(screen.queryByText(CHARGE_SENTENCING_UNAVAILABLE_MESSAGE)).not.toBeInTheDocument();
  });

  it('renders the provenance line in the aside (35.3 pin 7)', () => {
    render(<JudgeSpecificResultView data={makeSuccess()} />);

    const aside = within(screen.getByTestId('section-metadata'));
    expect(aside.getByTestId('aggregate-run-line')).toHaveTextContent(
      formatAggregateRunLabel(AGGREGATE_RUN_ID),
    );
  });
});
