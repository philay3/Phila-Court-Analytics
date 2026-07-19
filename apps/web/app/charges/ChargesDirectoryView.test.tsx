import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import {
  CHARGE_DIRECTORY_UNAVAILABLE_MESSAGE,
  type ChargeDirectoryEntry,
  type ChargeDirectoryResponse,
} from '@pca/shared';
import { ChargesDirectoryView } from './ChargesDirectoryView.js';
import { CHARGES_COPY, formatChargeCountLine } from './charges-copy.js';

// Fixtures typed straight from @pca/shared — no local/mock shapes. Invented
// charge names (never real docket data); sample sizes are distinctive values
// so the render-absence assertion cannot pass by accident.
const CHARGES = [
  {
    slug: 'aggravated-example',
    displayName: 'Aggravated Example',
    statuteCode: '18 § 9901',
    hasSentencing: true,
    outcomeSampleSize: 8412,
  },
  {
    slug: 'basic-example',
    displayName: 'Basic Example',
    hasSentencing: false,
    outcomeSampleSize: 517,
  },
  {
    slug: 'closing-example',
    displayName: 'Closing Example',
    statuteCode: '35 § 9902',
    hasSentencing: true,
    outcomeSampleSize: 1206,
  },
] satisfies ChargeDirectoryEntry[];

const ROWS: ChargeDirectoryResponse = { available: true, charges: CHARGES };
const SINGLE: ChargeDirectoryResponse = { available: true, charges: CHARGES.slice(0, 1) };

describe('ChargesDirectoryView', () => {
  it('renders the page heading (h1) and lead', () => {
    render(<ChargesDirectoryView data={ROWS} />);
    expect(
      screen.getByRole('heading', { level: 1, name: CHARGES_COPY.heading }),
    ).toBeInTheDocument();
    expect(screen.getByText(CHARGES_COPY.lead)).toBeInTheDocument();
  });

  it('renders one row per served charge, in served order', () => {
    render(<ChargesDirectoryView data={ROWS} />);
    const items = within(screen.getByRole('list')).getAllByRole('listitem');
    expect(items).toHaveLength(3);
    expect(items.map((item) => within(item).getByRole('link').textContent)).toEqual([
      'Aggravated Example',
      'Basic Example',
      'Closing Example',
    ]);
  });

  it('gives each row exactly one link, named by its charge, targeting its result page', () => {
    render(<ChargesDirectoryView data={ROWS} />);
    const items = within(screen.getByRole('list')).getAllByRole('listitem');
    for (const item of items) {
      expect(within(item).getAllByRole('link')).toHaveLength(1);
    }
    // Review-gate pin: the row link's accessible name contains its charge
    // name, so the screen-reader link list is distinguishable per row.
    const link = screen.getByRole('link', { name: /Aggravated Example/ });
    expect(link).toHaveAttribute('href', '/charges/aggravated-example');
  });

  it('keeps the sanctioned action text visible on every row without making it a second link', () => {
    render(<ChargesDirectoryView data={ROWS} />);
    expect(screen.getAllByText(CHARGES_COPY.rowAction)).toHaveLength(3);
    expect(screen.queryByRole('link', { name: CHARGES_COPY.rowAction })).not.toBeInTheDocument();
  });

  it('renders exactly the two availability states keyed off hasSentencing', () => {
    render(<ChargesDirectoryView data={ROWS} />);
    expect(screen.getAllByText(CHARGES_COPY.availabilityWithSentencing)).toHaveLength(2);
    expect(screen.getAllByText(CHARGES_COPY.availabilityOutcomesOnly)).toHaveLength(1);
  });

  it('renders the plural count line for several charges and the singular for one', () => {
    const { unmount } = render(<ChargesDirectoryView data={ROWS} />);
    expect(screen.getByText(formatChargeCountLine(3))).toBeInTheDocument();
    unmount();
    render(<ChargesDirectoryView data={SINGLE} />);
    expect(screen.getByText(formatChargeCountLine(1))).toBeInTheDocument();
  });

  it('renders the pinned recorded-outcomes line on every row and no other statistic (DP-5 AC5)', () => {
    const { container } = render(<ChargesDirectoryView data={ROWS} />);
    // Present direction: each row carries exactly the pinned Amendment A
    // line, formatted through the surface-scoped formatter (en-US grouping).
    const items = within(screen.getByRole('list')).getAllByRole('listitem');
    expect(items.map((item) => within(item).getByText(/^Recorded outcomes: /).textContent)).toEqual(
      ['Recorded outcomes: 8,412', 'Recorded outcomes: 517', 'Recorded outcomes: 1,206'],
    );
    // The result-page label never leaks onto this surface (Amendment A scope).
    expect(container.textContent).not.toContain('Sample size:');
    // Absent direction: no outcome/sentencing statistic renders — no
    // percentages, no counts outside the recorded-outcomes lines. Stripping
    // the recorded-outcomes lines leaves no digits from the payload values.
    const text = (container.textContent ?? '')
      .replace(/Recorded outcomes: [\d,]+/g, '')
      .replace(/%/g, 'PERCENT');
    expect(text).not.toContain('PERCENT');
    for (const sampleSize of ['8,412', '8412', '517', '1,206', '1206']) {
      expect(text).not.toContain(sampleSize);
    }
  });

  it('filters by display name, case-insensitively, updating rows and count', () => {
    render(<ChargesDirectoryView data={ROWS} />);
    fireEvent.change(screen.getByLabelText(CHARGES_COPY.filterLabel), {
      target: { value: 'BASIC exa' },
    });
    const items = within(screen.getByRole('list')).getAllByRole('listitem');
    expect(items).toHaveLength(1);
    expect(within(items[0] as HTMLElement).getByRole('link')).toHaveTextContent('Basic Example');
    expect(screen.getByText(formatChargeCountLine(1))).toBeInTheDocument();
  });

  it('matches statute codes as well as display names', () => {
    render(<ChargesDirectoryView data={ROWS} />);
    fireEvent.change(screen.getByLabelText(CHARGES_COPY.filterLabel), {
      target: { value: '9902' },
    });
    const items = within(screen.getByRole('list')).getAllByRole('listitem');
    expect(items).toHaveLength(1);
    expect(within(items[0] as HTMLElement).getByRole('link')).toHaveTextContent('Closing Example');
  });

  it('announces the count through a polite live region', () => {
    render(<ChargesDirectoryView data={ROWS} />);
    expect(screen.getByText(formatChargeCountLine(3))).toHaveAttribute('aria-live', 'polite');
  });

  it('shows the no-match state with a zero count and no list — never a blank container', () => {
    render(<ChargesDirectoryView data={ROWS} />);
    fireEvent.change(screen.getByLabelText(CHARGES_COPY.filterLabel), {
      target: { value: 'zzz-no-such-charge' },
    });
    expect(screen.getByText(CHARGES_COPY.noMatchBody)).toBeInTheDocument();
    expect(screen.getByText(formatChargeCountLine(0))).toBeInTheDocument();
    expect(screen.queryByRole('list')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: CHARGES_COPY.clearAction })).toBeInTheDocument();
  });

  it('clear restores the full list, empties the input, and refocuses it', () => {
    render(<ChargesDirectoryView data={ROWS} />);
    const input = screen.getByLabelText(CHARGES_COPY.filterLabel);
    fireEvent.change(input, { target: { value: 'zzz-no-such-charge' } });
    fireEvent.click(screen.getByRole('button', { name: CHARGES_COPY.clearAction }));

    expect(input).toHaveValue('');
    expect(input).toHaveFocus();
    expect(within(screen.getByRole('list')).getAllByRole('listitem')).toHaveLength(3);
    expect(screen.getByText(formatChargeCountLine(3))).toBeInTheDocument();
  });

  it('renders the served unavailable message for the unavailable arm — no list, no count', () => {
    render(
      <ChargesDirectoryView
        data={{ available: false, message: CHARGE_DIRECTORY_UNAVAILABLE_MESSAGE }}
      />,
    );
    expect(screen.getByRole('status')).toHaveTextContent(CHARGE_DIRECTORY_UNAVAILABLE_MESSAGE);
    expect(screen.queryByRole('list')).not.toBeInTheDocument();
    expect(screen.queryByText(formatChargeCountLine(0))).not.toBeInTheDocument();
  });

  it('renders the same shared message when an available run serves zero rows', () => {
    render(<ChargesDirectoryView data={{ available: true, charges: [] }} />);
    expect(screen.getByRole('status')).toHaveTextContent(CHARGE_DIRECTORY_UNAVAILABLE_MESSAGE);
    expect(screen.queryByRole('list')).not.toBeInTheDocument();
  });
});
