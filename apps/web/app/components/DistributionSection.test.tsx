import { describe, expect, it } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import {
  OUTCOME_GROUP_HEADING_DISMISSED_WITHDRAWN,
  OUTCOME_GROUP_HEADING_GUILTY,
  type OutcomeDistributionEntry,
  type SentencingDistributionEntry,
} from '@pca/shared';
import { DistributionSection } from './DistributionSection.js';
import { OUTCOME_DISPLAY_GROUPS } from './outcome-display-groups.js';
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

  // Pre-recording pinned decision 3: visual-only group headings over the two
  // served-adjacent pairs, in both the table and the bar stack. Rendering is a
  // consecutive-run partition of the served rows — never a re-sort (the
  // served-order test above runs WITHOUT groups and is deliberately untouched).
  describe('display groups', () => {
    const FULL_PAIR_ROWS: readonly OutcomeDistributionEntry[] = [
      { categoryCode: 'dismissed', displayName: 'Dismissed', count: 120, percentage: 12 },
      { categoryCode: 'withdrawn', displayName: 'Withdrawn', count: 80, percentage: 8 },
      { categoryCode: 'guilty_plea', displayName: 'Guilty plea', count: 540, percentage: 54 },
      { categoryCode: 'guilty_verdict', displayName: 'Guilty verdict', count: 60, percentage: 6 },
      { categoryCode: 'acquittal', displayName: 'Acquittal', count: 200, percentage: 20 },
    ];

    function renderWithGroups(rows: readonly OutcomeDistributionEntry[]) {
      return render(
        <DistributionSection
          kind="outcome"
          rows={rows}
          sampleSize={1000}
          thinData={false}
          groups={OUTCOME_DISPLAY_GROUPS}
        />,
      );
    }

    it('renders one shared heading per pair in the table, spanning both member rows', () => {
      renderWithGroups(FULL_PAIR_ROWS);

      const table = screen.getByRole('table', { name: RESULT_DISPLAY_COPY.outcomeCaption });
      const groupHeaders = Array.from(table.querySelectorAll('th[scope="rowgroup"]'));
      expect(groupHeaders.map((header) => header.textContent)).toEqual([
        OUTCOME_GROUP_HEADING_DISMISSED_WITHDRAWN,
        OUTCOME_GROUP_HEADING_GUILTY,
      ]);

      // Each heading's tbody contains exactly its member rows, in served
      // order; the ungrouped row lives outside both.
      const [dismissedGroup, guiltyGroup] = groupHeaders.map(
        (header) => header.closest('tbody') as HTMLElement,
      );
      expect(within(dismissedGroup!).getByText('Dismissed')).toBeInTheDocument();
      expect(within(dismissedGroup!).getByText('Withdrawn')).toBeInTheDocument();
      expect(within(guiltyGroup!).getByText('Guilty plea')).toBeInTheDocument();
      expect(within(guiltyGroup!).getByText('Guilty verdict')).toBeInTheDocument();
      expect(within(dismissedGroup!).queryByText('Acquittal')).not.toBeInTheDocument();
      expect(within(guiltyGroup!).queryByText('Acquittal')).not.toBeInTheDocument();
    });

    it('mirrors both headings in the aria-hidden bar stack', () => {
      const { container } = renderWithGroups(FULL_PAIR_ROWS);

      const barStack = container.querySelector('[aria-hidden="true"]') as HTMLElement;
      expect(barStack).not.toBeNull();
      expect(
        within(barStack).getByText(OUTCOME_GROUP_HEADING_DISMISSED_WITHDRAWN),
      ).toBeInTheDocument();
      expect(within(barStack).getByText(OUTCOME_GROUP_HEADING_GUILTY)).toBeInTheDocument();
    });

    it('keeps served row order and per-row served percentages under grouping (zero arithmetic)', () => {
      renderWithGroups(FULL_PAIR_ROWS);

      const table = screen.getByRole('table', { name: RESULT_DISPLAY_COPY.outcomeCaption });
      const rowHeaders = Array.from(table.querySelectorAll('th[scope="row"]'));
      expect(
        rowHeaders.map(
          (header) =>
            FULL_PAIR_ROWS.find((row) => header.textContent?.includes(row.displayName))
              ?.categoryCode,
        ),
      ).toEqual(FULL_PAIR_ROWS.map((row) => row.categoryCode));

      FULL_PAIR_ROWS.forEach((row) => {
        const fill = screen.getByTestId(`distribution-bar-fill-${row.categoryCode}`);
        expect(fill.style.width).toBe(`${row.percentage}%`);
      });
      // No summed group figure exists anywhere: the pair totals are absent.
      expect(screen.queryByText(formatPercentage(20))).toBeInTheDocument(); // acquittal's own
      expect(screen.queryByText(formatPercentage(60))).not.toBeInTheDocument(); // 54 + 6
    });

    it('renders a heading when only one member of a pair is present', () => {
      renderWithGroups(OUTCOME_ROWS); // dismissed + guilty_plea + acquittal only

      const table = screen.getByRole('table', { name: RESULT_DISPLAY_COPY.outcomeCaption });
      const groupHeaders = Array.from(table.querySelectorAll('th[scope="rowgroup"]'));
      expect(groupHeaders.map((header) => header.textContent)).toEqual([
        OUTCOME_GROUP_HEADING_DISMISSED_WITHDRAWN,
        OUTCOME_GROUP_HEADING_GUILTY,
      ]);
    });

    it('renders no group heading without the groups prop (sentencing sections unchanged)', () => {
      render(
        <DistributionSection
          kind="sentencing"
          rows={SENTENCING_ROWS}
          sampleSize={SENTENCING_SAMPLE_SIZE}
          thinData={false}
        />,
      );

      const table = screen.getByRole('table', { name: RESULT_DISPLAY_COPY.sentencingCaption });
      expect(table.querySelectorAll('th[scope="rowgroup"]')).toHaveLength(0);
      expect(table.querySelectorAll('tbody')).toHaveLength(1);
      expect(screen.queryByText(OUTCOME_GROUP_HEADING_DISMISSED_WITHDRAWN)).not.toBeInTheDocument();
      expect(screen.queryByText(OUTCOME_GROUP_HEADING_GUILTY)).not.toBeInTheDocument();
    });
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
