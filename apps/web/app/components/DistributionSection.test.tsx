import { describe, expect, it } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import type { OutcomeDistributionEntry, SentencingDistributionEntry } from '@pca/shared';
import { DistributionSection } from './DistributionSection.js';
import { RESULT_DISPLAY_COPY } from './result-display-copy.js';
import { definitionAnchor } from '../lib/definition-anchor.js';
import {
  formatCount,
  formatPercentage,
  formatRecordsLabel,
  formatSentenceComponentsLabel,
  THIN_DATA_LABEL,
} from '../lib/formatters.js';

// Fixtures typed straight from @pca/shared — no local/mock shapes (decision 4).
const OUTCOME_ROWS: readonly OutcomeDistributionEntry[] = [
  { categoryCode: 'dismissed', displayName: 'Dismissed', count: 120, percentage: 12 },
  { categoryCode: 'guilty_plea', displayName: 'Guilty plea', count: 640, percentage: 64 },
  { categoryCode: 'acquittal', displayName: 'Acquittal', count: 240, percentage: 24 },
];
const OUTCOME_SAMPLE_SIZE = 1234;

const SENTENCING_ROWS: readonly SentencingDistributionEntry[] = [
  { categoryCode: 'probation', displayName: 'Probation', count: 300, percentage: 50 },
  { categoryCode: 'incarceration', displayName: 'Incarceration', count: 180, percentage: 30 },
  { categoryCode: 'fine', displayName: 'Fine', count: 120, percentage: 20 },
];
// Deliberately different from the outcome sample size (decision: independent).
const SENTENCING_SAMPLE_SIZE = 600;

describe('DistributionSection', () => {
  it('renders an outcome distribution: display names, counts, percentages, sample size, with count and percentage together per row', () => {
    render(
      <DistributionSection
        kind="outcome"
        rows={OUTCOME_ROWS}
        sampleSize={OUTCOME_SAMPLE_SIZE}
        thinData={false}
      />,
    );

    // Sample present via the 11.4 formatter (35.3 reconciled: records).
    expect(screen.getByText(formatRecordsLabel(OUTCOME_SAMPLE_SIZE))).toBeInTheDocument();

    const table = screen.getByRole('table', { name: RESULT_DISPLAY_COPY.outcomeCaption });
    const bodyRows = within(table).getAllByRole('row').slice(1); // drop the header row
    expect(bodyRows).toHaveLength(OUTCOME_ROWS.length);

    OUTCOME_ROWS.forEach((row, index) => {
      const cell = bodyRows[index]!;
      // Display name, count AND percentage all appear together in the same row.
      expect(within(cell).getByText(row.displayName)).toBeInTheDocument();
      expect(within(cell).getByText(formatCount(row.count))).toBeInTheDocument();
      expect(within(cell).getByText(formatPercentage(row.percentage))).toBeInTheDocument();
    });
  });

  it('renders a sentencing distribution with the separate sentencing sample size', () => {
    render(
      <DistributionSection
        kind="sentencing"
        rows={SENTENCING_ROWS}
        sampleSize={SENTENCING_SAMPLE_SIZE}
        thinData={false}
      />,
    );

    const table = screen.getByRole('table', { name: RESULT_DISPLAY_COPY.sentencingCaption });
    expect(table).toBeInTheDocument();
    expect(
      screen.getByText(formatSentenceComponentsLabel(SENTENCING_SAMPLE_SIZE)),
    ).toBeInTheDocument();
    // Not the outcome label — this distribution shows its own unit and value.
    expect(screen.queryByText(formatRecordsLabel(OUTCOME_SAMPLE_SIZE))).not.toBeInTheDocument();
  });

  it('renders a caption override in place of the default (35.3: the detail caption below the index)', () => {
    // Mechanism test with a test-local caption; the sanctioned detail-caption
    // string itself is byte-pinned in @pca/shared and asserted by the views'
    // tests via the imported constant (never re-typed here).
    render(
      <DistributionSection
        kind="sentencing"
        rows={SENTENCING_ROWS}
        sampleSize={SENTENCING_SAMPLE_SIZE}
        thinData={false}
        caption="Test-local caption override"
      />,
    );

    expect(screen.getByRole('table', { name: 'Test-local caption override' })).toBeInTheDocument();
    expect(
      screen.queryByRole('table', { name: RESULT_DISPLAY_COPY.sentencingCaption }),
    ).not.toBeInTheDocument();
  });

  it('renders rows in served order — a shuffled fixture is NOT re-sorted', () => {
    // Shuffled relative to taxonomy sortOrder; the component must preserve this.
    const shuffled: readonly OutcomeDistributionEntry[] = [
      { categoryCode: 'acquittal', displayName: 'Acquittal', count: 240, percentage: 24 },
      { categoryCode: 'dismissed', displayName: 'Dismissed', count: 120, percentage: 12 },
      { categoryCode: 'guilty_plea', displayName: 'Guilty plea', count: 640, percentage: 64 },
    ];
    render(
      <DistributionSection kind="outcome" rows={shuffled} sampleSize={1000} thinData={false} />,
    );

    const table = screen.getByRole('table', { name: RESULT_DISPLAY_COPY.outcomeCaption });
    const rowHeaders = within(table).getAllByRole('rowheader');
    const renderedOrder = rowHeaders.map(
      (header) =>
        shuffled.find((row) => header.textContent?.includes(row.displayName))?.categoryCode,
    );
    expect(renderedOrder).toEqual(shuffled.map((row) => row.categoryCode));
  });

  it('draws bars whose width matches the API percentage, keeps them aria-hidden, and mirrors every value in the table', () => {
    render(
      <DistributionSection
        kind="outcome"
        rows={OUTCOME_ROWS}
        sampleSize={OUTCOME_SAMPLE_SIZE}
        thinData={false}
      />,
    );

    const table = screen.getByRole('table', { name: RESULT_DISPLAY_COPY.outcomeCaption });

    OUTCOME_ROWS.forEach((row) => {
      const fill = screen.getByTestId(`distribution-bar-fill-${row.categoryCode}`);
      // Width derives from the API percentage only.
      expect(fill.style.width).toBe(`${row.percentage}%`);
      // The bar block is aria-hidden; the table is the accessible equivalent.
      expect(fill.closest('[aria-hidden="true"]')).not.toBeNull();
      // Every value a bar shows also lives in the table.
      expect(within(table).getByText(formatCount(row.count))).toBeInTheDocument();
      expect(within(table).getByText(formatPercentage(row.percentage))).toBeInTheDocument();
    });
  });

  it('links each category row to the pinned /definitions anchor', () => {
    render(
      <DistributionSection
        kind="outcome"
        rows={OUTCOME_ROWS}
        sampleSize={OUTCOME_SAMPLE_SIZE}
        thinData={false}
      />,
    );

    OUTCOME_ROWS.forEach((row) => {
      const link = screen.getByRole('link', {
        name: `${RESULT_DISPLAY_COPY.definitionLinkLabelPrefix}${row.displayName}`,
      });
      expect(link).toHaveAttribute('href', definitionAnchor('outcome', row.categoryCode));
    });
  });

  it('uses semantic table markup: a caption naming the distribution and scoped headers', () => {
    render(
      <DistributionSection
        kind="outcome"
        rows={OUTCOME_ROWS}
        sampleSize={OUTCOME_SAMPLE_SIZE}
        thinData={false}
      />,
    );

    const table = screen.getByRole('table', { name: RESULT_DISPLAY_COPY.outcomeCaption });
    for (const columnHeader of within(table).getAllByRole('columnheader')) {
      expect(columnHeader).toHaveAttribute('scope', 'col');
    }
    for (const rowHeader of within(table).getAllByRole('rowheader')) {
      expect(rowHeader).toHaveAttribute('scope', 'row');
    }
  });

  it('embeds the thin-data badge only when thin, and never renders the standalone callout', () => {
    const { rerender } = render(
      <DistributionSection
        kind="outcome"
        rows={OUTCOME_ROWS}
        sampleSize={OUTCOME_SAMPLE_SIZE}
        thinData
      />,
    );
    expect(screen.getByText(THIN_DATA_LABEL)).toBeInTheDocument();
    // The callout is a page-level concern (13.2/13.3), never in the section.
    expect(screen.queryByText(RESULT_DISPLAY_COPY.thinDataCalloutBody)).not.toBeInTheDocument();

    rerender(
      <DistributionSection
        kind="outcome"
        rows={OUTCOME_ROWS}
        sampleSize={OUTCOME_SAMPLE_SIZE}
        thinData={false}
      />,
    );
    expect(screen.queryByText(THIN_DATA_LABEL)).not.toBeInTheDocument();
    expect(screen.queryByText(RESULT_DISPLAY_COPY.thinDataCalloutBody)).not.toBeInTheDocument();
  });
});
