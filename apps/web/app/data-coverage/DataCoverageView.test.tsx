import { describe, expect, it } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import {
  DATA_COVERAGE_COURT_SCOPE,
  DATA_COVERAGE_JURISDICTION,
  DATA_COVERAGE_PLANNED_DATA_START,
  DATA_COVERAGE_UNAVAILABLE_MESSAGE,
  type DataCoverageResponse,
} from '@pca/shared';
import { DataCoverageView, DataCoverageErrorState } from './DataCoverageView.js';
import { DATA_COVERAGE_COPY } from './data-coverage-copy.js';
import Loading from './loading.js';

// Distinctive, order-sensitive limitations — the third entry stands in for the
// seeded-data disclosure. The strings are deliberately unusual so a paraphrase
// or truncation cannot accidentally still match.
const KNOWN_LIMITATIONS = [
  'Coverage is limited to cases with a completed disposition on or after the data start date.',
  'Some charge categories have too few records to report and are withheld.',
  'A portion of the underlying figures is seeded sample data and does not reflect real cases.',
];

const AVAILABLE: DataCoverageResponse = {
  jurisdiction: DATA_COVERAGE_JURISDICTION,
  courtScope: DATA_COVERAGE_COURT_SCOPE,
  plannedDataStart: DATA_COVERAGE_PLANNED_DATA_START,
  knownLimitations: KNOWN_LIMITATIONS,
  coverage: {
    available: true,
    dataStart: '2025-01-01',
    dataEnd: '2026-06-30',
    lastRefreshed: '2026-07-01T02:00:00Z',
    taxonomyVersion: '2026.07.01',
    aggregateRunId: '2f9c1e04-8d5b-4c33-9a67-0d1e2f3a4b5c',
    counts: {
      chargesWithOutcomeAggregates: 1234,
      chargesWithSentencingAggregates: 567,
      judgeChargePairs: 89,
    },
  },
};

const UNAVAILABLE: DataCoverageResponse = {
  ...AVAILABLE,
  coverage: { available: false, message: DATA_COVERAGE_UNAVAILABLE_MESSAGE },
};

function renderedLimitations(): string[] {
  const list = screen.getByTestId('known-limitations');
  return within(list)
    .getAllByRole('listitem')
    .map((item) => item.textContent ?? '');
}

describe('DataCoverageView — available arm', () => {
  it('renders the page heading and the always-present overview fields', () => {
    render(<DataCoverageView data={AVAILABLE} />);

    expect(
      screen.getByRole('heading', { level: 1, name: DATA_COVERAGE_COPY.heading }),
    ).toBeInTheDocument();
    expect(screen.getByText(DATA_COVERAGE_JURISDICTION)).toBeInTheDocument();
    expect(screen.getByText(DATA_COVERAGE_COURT_SCOPE)).toBeInTheDocument();
  });

  // AC 4 (non-circular): the expected rendered date is pinned as a literal, so a
  // formatter regression cannot silently keep this green.
  it('renders the 2025-01-01 data start as "January 1, 2025"', () => {
    render(<DataCoverageView data={AVAILABLE} />);
    expect(screen.getByText('January 1, 2025')).toBeInTheDocument();
  });

  it('renders the covered data window including the data end date', () => {
    render(<DataCoverageView data={AVAILABLE} />);
    // Pinned literal window output (start – end) from the 11.4 formatter.
    expect(screen.getByText('January 1, 2025 – June 30, 2026')).toBeInTheDocument();
  });

  it('renders last refreshed with an explicit UTC suffix', () => {
    render(<DataCoverageView data={AVAILABLE} />);
    expect(screen.getByText('July 1, 2026 at 2:00 AM UTC')).toBeInTheDocument();
  });

  it('renders the public-safe aggregate run metadata', () => {
    render(<DataCoverageView data={AVAILABLE} />);
    expect(screen.getByText('2f9c1e04-8d5b-4c33-9a67-0d1e2f3a4b5c')).toBeInTheDocument();
    expect(screen.getByText('2026.07.01')).toBeInTheDocument();
  });

  it('renders the high-level seeded count metadata, count-formatted', () => {
    render(<DataCoverageView data={AVAILABLE} />);
    expect(screen.getByText('1,234')).toBeInTheDocument();
    expect(screen.getByText('567')).toBeInTheDocument();
    expect(screen.getByText('89')).toBeInTheDocument();
  });

  it('renders known limitations verbatim AND in served document order', () => {
    render(<DataCoverageView data={AVAILABLE} />);
    // Deep equality against the payload array: catches paraphrase, truncation,
    // AND reordering — presence-only assertions cannot catch a reorder.
    expect(renderedLimitations()).toEqual(KNOWN_LIMITATIONS);
  });
});

describe('DataCoverageView — unavailable arm', () => {
  it('renders the served unavailable message verbatim', () => {
    render(<DataCoverageView data={UNAVAILABLE} />);
    expect(screen.getByText(DATA_COVERAGE_UNAVAILABLE_MESSAGE)).toBeInTheDocument();
  });

  it('still renders the always-present overview fields and start date', () => {
    render(<DataCoverageView data={UNAVAILABLE} />);
    expect(screen.getByText(DATA_COVERAGE_JURISDICTION)).toBeInTheDocument();
    expect(screen.getByText(DATA_COVERAGE_COURT_SCOPE)).toBeInTheDocument();
    expect(screen.getByText('January 1, 2025')).toBeInTheDocument();
  });

  it('keeps the seeded-data disclosure visible via known limitations, in order', () => {
    render(<DataCoverageView data={UNAVAILABLE} />);
    expect(renderedLimitations()).toEqual(KNOWN_LIMITATIONS);
  });

  it('renders no aggregate coverage figures in the unavailable arm', () => {
    render(<DataCoverageView data={UNAVAILABLE} />);
    expect(screen.queryByText('2f9c1e04-8d5b-4c33-9a67-0d1e2f3a4b5c')).not.toBeInTheDocument();
    expect(screen.queryByText('1,234')).not.toBeInTheDocument();
  });
});

describe('DataCoverageErrorState', () => {
  it('renders the error heading and the supplied shared message, with no internal detail', () => {
    const message = "We couldn't reach the server. Please check your connection and try again.";
    render(<DataCoverageErrorState message={message} />);

    expect(
      screen.getByRole('heading', { level: 1, name: DATA_COVERAGE_COPY.errorHeading }),
    ).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent(message);
  });
});

describe('data coverage loading state', () => {
  it('renders a neutral in-flight status message', () => {
    render(<Loading />);
    expect(screen.getByRole('status')).toHaveTextContent(DATA_COVERAGE_COPY.loadingMessage);
  });
});
