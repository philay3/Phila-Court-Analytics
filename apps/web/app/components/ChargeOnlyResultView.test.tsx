import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import {
  CHARGE_SENTENCING_UNAVAILABLE_MESSAGE,
  type ChargeOnlyResultSuccess,
  type OutcomeDistributionEntry,
  type SentencingDistributionEntry,
} from '@pca/shared';
import {
  RESULT_TYPE_CHARGE_ONLY_LABEL,
  THIN_DATA_LABEL,
  formatDateRange,
  formatLastRefreshed,
  formatSampleSize,
} from '../lib/formatters.js';
import { RESULT_DISPLAY_COPY } from './result-display-copy.js';
import { CHARGE_RESULT_COPY } from './charge-result-copy.js';
import { ChargeOnlyResultView } from './ChargeOnlyResultView.js';

// next/link and next/navigation are stubbed so the (client) JudgeFilterEntry
// and the page links render under jsdom without an App Router provider.
vi.mock('next/link', () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) => (
    <a href={typeof href === 'string' ? href : ''} {...rest}>
      {children}
    </a>
  ),
}));
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }));

const CHARGE = {
  id: '00000000-0000-0000-0000-000000000001',
  slug: 'theft',
  displayName: 'Theft',
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

const OUTCOME_SAMPLE_SIZE = 1234;
const SENTENCING_SAMPLE_SIZE = 600;

function makeSuccess(overrides: Partial<ChargeOnlyResultSuccess> = {}): ChargeOnlyResultSuccess {
  return {
    charge: CHARGE,
    resultType: 'charge_only',
    geography: 'philadelphia',
    dateRange: { start: '2025-01-01', end: '2026-06-30' },
    lastRefreshed: '2026-07-01T14:30:00.000Z',
    taxonomyVersion: '1.0.0',
    aggregateRunId: '00000000-0000-0000-0000-0000000000aa',
    outcomes: { sampleSize: OUTCOME_SAMPLE_SIZE, thinData: false, rows: OUTCOME_ROWS },
    sentencing: {
      available: true,
      sampleSize: SENTENCING_SAMPLE_SIZE,
      thinData: false,
      rows: SENTENCING_ROWS,
    },
    // Task 35.2 type-compatibility only: the absent arm, rendered by 35.3.
    sentencingIndex: { available: false },
    links: { methodology: '/methodology', definitions: '/definitions' },
    ...overrides,
  };
}

function sectionOrder(container: HTMLElement): string[] {
  // Top-level pinned order only (DP-3): the metadata aside itself is a pinned
  // section, but testids nested INSIDE it (the frozen section-judge-filter)
  // are its contents, not part of the page-level order.
  return Array.from(container.querySelectorAll('[data-testid^="section-"]'))
    .filter((element) => {
      const aside = element.closest('[data-testid="section-metadata"]');
      return aside === null || aside === element;
    })
    .map((element) => element.getAttribute('data-testid')) as string[];
}

describe('ChargeOnlyResultView', () => {
  it('renders the full success metadata: name, framing label, dates, both distributions and links', () => {
    render(<ChargeOnlyResultView data={makeSuccess()} />);

    expect(screen.getByRole('heading', { level: 1, name: CHARGE.displayName })).toBeInTheDocument();
    expect(screen.getByText(RESULT_TYPE_CHARGE_ONLY_LABEL)).toBeInTheDocument();
    expect(
      screen.getByText(formatDateRange({ start: '2025-01-01', end: '2026-06-30' })),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        `${CHARGE_RESULT_COPY.lastRefreshedLabel}: ${formatLastRefreshed('2026-07-01T14:30:00.000Z')}`,
      ),
    ).toBeInTheDocument();

    // Outcome distribution with its own sample size, scoped to its owning
    // section (DP-3.2 STOP ruling: the aside duplicates the value by design).
    const outcomeTable = screen.getByRole('table', { name: RESULT_DISPLAY_COPY.outcomeCaption });
    expect(within(outcomeTable).getByText('Dismissed')).toBeInTheDocument();
    const outcomeSection = within(screen.getByTestId('section-outcome'));
    expect(outcomeSection.getByText(formatSampleSize(OUTCOME_SAMPLE_SIZE))).toBeInTheDocument();

    // Sentencing distribution with its own, independent sample size — scoped
    // the same way.
    const sentencingTable = screen.getByRole('table', {
      name: RESULT_DISPLAY_COPY.sentencingCaption,
    });
    expect(within(sentencingTable).getByText('Probation')).toBeInTheDocument();
    const sentencingSection = within(screen.getByTestId('section-sentencing'));
    expect(
      sentencingSection.getByText(formatSampleSize(SENTENCING_SAMPLE_SIZE)),
    ).toBeInTheDocument();

    // The metadata aside pins the sanctioned duplication (DP-3.2 STOP ruling):
    // both context labels and both formatted sample-size values.
    const aside = within(screen.getByTestId('section-metadata'));
    expect(aside.getByText(CHARGE_RESULT_COPY.asideOutcomesLabel)).toBeInTheDocument();
    expect(aside.getByText(CHARGE_RESULT_COPY.asideSentencingLabel)).toBeInTheDocument();
    expect(aside.getByText(formatSampleSize(OUTCOME_SAMPLE_SIZE))).toBeInTheDocument();
    expect(aside.getByText(formatSampleSize(SENTENCING_SAMPLE_SIZE))).toBeInTheDocument();

    // Coverage note, responsible-use notice + both links.
    expect(screen.getByText(RESULT_DISPLAY_COPY.coverageNote)).toBeInTheDocument();
    expect(screen.getByText(RESULT_DISPLAY_COPY.responsibleUseHistorical)).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: CHARGE_RESULT_COPY.methodologyLinkText }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: CHARGE_RESULT_COPY.definitionsLinkText }),
    ).toBeInTheDocument();
  });

  it('renders a page-level thin-data callout and the per-distribution badge when a distribution is thin', () => {
    render(
      <ChargeOnlyResultView
        data={makeSuccess({
          outcomes: { sampleSize: 8, thinData: true, rows: OUTCOME_ROWS },
        })}
      />,
    );

    expect(screen.getByText(RESULT_DISPLAY_COPY.thinDataCalloutBody)).toBeInTheDocument();
    // The per-distribution badge (pinned formatter label) is still shown.
    expect(screen.getByText(THIN_DATA_LABEL)).toBeInTheDocument();
  });

  it('renders the sentencing-unavailable callout within a success payload without failing the page', () => {
    render(
      <ChargeOnlyResultView
        data={makeSuccess({
          sentencing: { available: false, message: CHARGE_SENTENCING_UNAVAILABLE_MESSAGE },
        })}
      />,
    );

    // Outcome section still renders in full.
    expect(
      screen.getByRole('table', { name: RESULT_DISPLAY_COPY.outcomeCaption }),
    ).toBeInTheDocument();
    // Sentencing section shows the pinned shared message, not a table.
    expect(screen.getByText(CHARGE_SENTENCING_UNAVAILABLE_MESSAGE)).toBeInTheDocument();
    expect(
      screen.queryByRole('table', { name: RESULT_DISPLAY_COPY.sentencingCaption }),
    ).not.toBeInTheDocument();
  });

  it('renders sentencing above outcome when sentencing is available (task 33.2 conditional order)', () => {
    const { container } = render(
      <ChargeOnlyResultView
        data={makeSuccess({ outcomes: { sampleSize: 8, thinData: true, rows: OUTCOME_ROWS } })}
      />,
    );

    expect(sectionOrder(container)).toEqual([
      'section-summary',
      'section-responsible-use',
      'section-thin-data',
      'section-sentencing',
      'section-outcome',
      'section-metadata',
    ]);
  });

  it('renders outcome first with the callout below on the sentencing-unavailable arm', () => {
    const { container } = render(
      <ChargeOnlyResultView
        data={makeSuccess({
          sentencing: { available: false, message: CHARGE_SENTENCING_UNAVAILABLE_MESSAGE },
        })}
      />,
    );

    expect(sectionOrder(container)).toEqual([
      'section-summary',
      'section-responsible-use',
      'section-outcome',
      'section-sentencing',
      'section-metadata',
    ]);
  });
});
