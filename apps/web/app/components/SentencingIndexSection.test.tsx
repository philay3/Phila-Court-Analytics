import { describe, expect, it } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import {
  SENTENCING_INDEX_CAPTION,
  SENTENCING_INDEX_CATEGORY_HEADER,
  SENTENCING_INDEX_COUNT_HEADER,
  SENTENCING_INDEX_MEDIAN_HEADER,
  SENTENCING_INDEX_PERCENTAGE_HEADER,
} from '@pca/shared';
import { THIN_DATA_LABEL } from '../lib/formatters';
import type {
  ConvictionGradeRow,
  SentencingIndexCategoryRow,
  SentencingIndexSummary,
} from '@pca/shared';
import { SentencingIndexSection } from './SentencingIndexSection';

/**
 * Every number below is fabricated (the seeded-matrix convention): tests may
 * assert only test-local or seeded-scenario values, never corpus figures.
 */
function summary(overrides: Partial<SentencingIndexSummary> = {}): SentencingIndexSummary {
  return {
    convictions: 600,
    sentencedConvictions: 588,
    wedgeCount: 12,
    wedgePercentage: 2,
    thinData: false,
    dateRange: { start: '2025-01-03', end: '2026-06-27' },
    ...overrides,
  };
}

const categories: readonly SentencingIndexCategoryRow[] = [
  {
    categoryCode: 'probation',
    convictionCount: 290,
    percentageOfSentenced: 49.3,
    medianMinMonths: 12,
    medianMaxMonths: 18,
    minAssumedPercentage: 10,
  },
  {
    categoryCode: 'incarceration',
    convictionCount: 88,
    percentageOfSentenced: 15,
    medianMinMonths: 3,
    medianMaxMonths: 3,
    minAssumedPercentage: 20,
  },
  { categoryCode: 'fine', convictionCount: 200, percentageOfSentenced: 34 },
];

const grades: readonly ConvictionGradeRow[] = [
  { grade: 'F3', convictionCount: 300, percentageOfConvictions: 50 },
  { grade: 'M1', convictionCount: 150, percentageOfConvictions: 25 },
  { grade: 'ungraded', convictionCount: 30, percentageOfConvictions: 5 },
];

describe('SentencingIndexSection', () => {
  it('renders the conditional caption, headers, and the sentenced-convictions label', () => {
    render(<SentencingIndexSection summary={summary()} categories={categories} grades={grades} />);

    expect(screen.getByText(SENTENCING_INDEX_CAPTION)).toBeInTheDocument();
    for (const header of [
      SENTENCING_INDEX_CATEGORY_HEADER,
      SENTENCING_INDEX_COUNT_HEADER,
      SENTENCING_INDEX_PERCENTAGE_HEADER,
      SENTENCING_INDEX_MEDIAN_HEADER,
    ]) {
      expect(screen.getByRole('columnheader', { name: header })).toBeInTheDocument();
    }
    expect(screen.getByText('Sentenced convictions: 588')).toBeInTheDocument();
  });

  it('renders rows in served order with API percentages and taxonomy display names', () => {
    render(<SentencingIndexSection summary={summary()} categories={categories} grades={grades} />);

    const rowHeaders = screen
      .getAllByRole('rowheader')
      .map((header) => within(header).getByText(/./, { selector: 'span' }).textContent);
    expect(rowHeaders).toEqual(['Probation', 'Incarceration', 'Fine']);

    const probationRow = screen.getByRole('rowheader', { name: /Probation/ }).closest('tr');
    expect(probationRow).not.toBeNull();
    expect(within(probationRow as HTMLElement).getByText('290')).toBeInTheDocument();
    expect(within(probationRow as HTMLElement).getByText('49.3%')).toBeInTheDocument();
  });

  it('renders median pairs per pin 4: range, flat-pair collapse, and empty duration-free cell', () => {
    render(<SentencingIndexSection summary={summary()} categories={categories} grades={grades} />);

    const probationRow = screen.getByRole('rowheader', { name: /Probation/ }).closest('tr');
    expect(within(probationRow as HTMLElement).getByText('12–18')).toBeInTheDocument();

    const incarcerationRow = screen.getByRole('rowheader', { name: /Incarceration/ }).closest('tr');
    expect(within(incarcerationRow as HTMLElement).getByText('3')).toBeInTheDocument();

    const fineRow = screen.getByRole('rowheader', { name: /Fine/ }).closest('tr');
    const fineCells = within(fineRow as HTMLElement).getAllByRole('cell');
    expect(fineCells[fineCells.length - 1]).toHaveTextContent('');
  });

  it('renders the wedge disclosure line from served values', () => {
    render(<SentencingIndexSection summary={summary()} categories={categories} grades={grades} />);

    expect(screen.getByTestId('index-wedge-disclosure')).toHaveTextContent(
      '12 of 600 recorded convictions (2%) have no public sentencing record in the collected data and are not counted in the rates above.',
    );
  });

  it('renders the grade-mix line dominant-first with the gated ungraded label (charge pages)', () => {
    render(<SentencingIndexSection summary={summary()} categories={categories} grades={grades} />);

    expect(screen.getByTestId('index-grade-mix')).toHaveTextContent(
      'Conviction grades: F3 50% · M1 25% · no recorded grade 5%',
    );
  });

  it('renders no grade line when no grades are passed (judge cells, ruling 2)', () => {
    render(<SentencingIndexSection summary={summary()} categories={categories} />);

    expect(screen.queryByTestId('index-grade-mix')).not.toBeInTheDocument();
  });

  it('shows the byte-identical thin badge when the served flag is set', () => {
    render(
      <SentencingIndexSection
        summary={summary({ thinData: true })}
        categories={categories}
        grades={grades}
      />,
    );

    expect(screen.getByText(THIN_DATA_LABEL)).toBeInTheDocument();
  });

  it('keeps the bars presentational: aria-hidden fills sized by the served percentage', () => {
    render(<SentencingIndexSection summary={summary()} categories={categories} grades={grades} />);

    const fill = screen.getByTestId('index-bar-fill-probation');
    expect(fill).toHaveStyle({ width: '49.3%' });
    expect(fill.closest('[aria-hidden="true"]')).not.toBeNull();
  });
});
