import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import {
  CHARGE_SENTENCING_UNAVAILABLE_MESSAGE,
  type JudgeSpecificResultSuccess,
  type OutcomeDistributionEntry,
  type ResultDistributions,
  type SentencingDistributionEntry,
} from '@pca/shared';
import {
  RESULT_TYPE_JUDGE_SPECIFIC_LABEL,
  THIN_DATA_LABEL,
  formatDateRange,
  formatLastRefreshed,
  formatSampleSize,
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
// on-screen "Sample size: N" string.
const JUDGE_OUTCOME_N = 14;
const JUDGE_SENTENCING_N = 9;
const BASELINE_OUTCOME_N = 1000;
const BASELINE_SENTENCING_N = 600;

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
    aggregateRunId: '00000000-0000-0000-0000-0000000000aa',
    judgeSpecific: makeScope(JUDGE_OUTCOME_N, JUDGE_SENTENCING_N),
    baseline: makeScope(BASELINE_OUTCOME_N, BASELINE_SENTENCING_N),
    links: { methodology: '/methodology', definitions: '/definitions' },
    ...overrides,
  };
}

function sectionOrder(container: HTMLElement): string[] {
  return Array.from(container.querySelectorAll('[data-testid^="section-"]')).map((element) =>
    element.getAttribute('data-testid'),
  ) as string[];
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
    expect(judgeOutcome.getByText(formatSampleSize(JUDGE_OUTCOME_N))).toBeInTheDocument();

    const judgeSentencing = within(screen.getByTestId('section-judge-sentencing'));
    expect(
      judgeSentencing.getByRole('table', { name: RESULT_DISPLAY_COPY.sentencingCaption }),
    ).toBeInTheDocument();
    expect(judgeSentencing.getByText(formatSampleSize(JUDGE_SENTENCING_N))).toBeInTheDocument();

    const baselineOutcome = within(screen.getByTestId('section-baseline-outcome'));
    expect(
      baselineOutcome.getByRole('table', { name: RESULT_DISPLAY_COPY.outcomeCaption }),
    ).toBeInTheDocument();
    expect(baselineOutcome.getByText(formatSampleSize(BASELINE_OUTCOME_N))).toBeInTheDocument();

    const baselineSentencing = within(screen.getByTestId('section-baseline-sentencing'));
    expect(
      baselineSentencing.getByRole('table', { name: RESULT_DISPLAY_COPY.sentencingCaption }),
    ).toBeInTheDocument();
    expect(
      baselineSentencing.getByText(formatSampleSize(BASELINE_SENTENCING_N)),
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
      'section-links',
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
      'section-links',
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
      'section-links',
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
      'section-links',
    ]);
  });
});
