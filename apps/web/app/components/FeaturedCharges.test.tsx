import { describe, expect, it } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import {
  BROWSE_ALL_CHARGES_LINK_TEXT,
  FEATURED_CHARGES_HEADING,
  type ChargeDirectoryEntry,
} from '@pca/shared';
import { FeaturedCharges } from './FeaturedCharges.js';
import { CHARGES_COPY } from '../charges/charges-copy.js';

// Invented charge names (never real docket data); distinctive sample sizes so
// the no-other-statistic assertion cannot pass by accident. Served order is
// sample-size descending per the DP-5 API pin.
const FEATURED = [
  {
    slug: 'delta-example',
    displayName: 'Delta Example',
    statuteCode: '18 § 9904',
    hasSentencing: true,
    outcomeSampleSize: 9317,
  },
  {
    slug: 'echo-example',
    displayName: 'Echo Example',
    hasSentencing: false,
    outcomeSampleSize: 4206,
  },
  {
    slug: 'foxtrot-example',
    displayName: 'Foxtrot Example',
    statuteCode: '35 § 9905',
    hasSentencing: true,
    outcomeSampleSize: 815,
  },
  {
    slug: 'golf-example',
    displayName: 'Golf Example',
    hasSentencing: false,
    outcomeSampleSize: 42,
  },
] satisfies ChargeDirectoryEntry[];

describe('FeaturedCharges', () => {
  it('renders the sanctioned heading as an h2 labelling the section', () => {
    render(<FeaturedCharges charges={FEATURED} />);
    expect(
      screen.getByRole('heading', { level: 2, name: FEATURED_CHARGES_HEADING }),
    ).toBeInTheDocument();
  });

  it('renders one card per row, in served order', () => {
    render(<FeaturedCharges charges={FEATURED} />);
    const items = within(screen.getByRole('list')).getAllByRole('listitem');
    expect(items).toHaveLength(4);
    expect(items.map((item) => within(item).getByRole('link').textContent)).toEqual([
      'Delta Example',
      'Echo Example',
      'Foxtrot Example',
      'Golf Example',
    ]);
  });

  it('renders fewer cards when fewer rows are passed (fail-soft degradation)', () => {
    render(<FeaturedCharges charges={FEATURED.slice(0, 2)} />);
    expect(within(screen.getByRole('list')).getAllByRole('listitem')).toHaveLength(2);
  });

  it('gives each card exactly one link, named by its charge, targeting its result page', () => {
    render(<FeaturedCharges charges={FEATURED} />);
    for (const item of within(screen.getByRole('list')).getAllByRole('listitem')) {
      expect(within(item).getAllByRole('link')).toHaveLength(1);
    }
    expect(screen.getByRole('link', { name: /Delta Example/ })).toHaveAttribute(
      'href',
      '/charges/delta-example',
    );
  });

  it('renders the availability line as directory rows do, keyed off hasSentencing', () => {
    render(<FeaturedCharges charges={FEATURED} />);
    expect(screen.getAllByText(CHARGES_COPY.availabilityWithSentencing)).toHaveLength(2);
    expect(screen.getAllByText(CHARGES_COPY.availabilityOutcomesOnly)).toHaveLength(2);
  });

  it('renders the pinned sample-size line on every card and no other statistic', () => {
    const { container } = render(<FeaturedCharges charges={FEATURED} />);
    const items = within(screen.getByRole('list')).getAllByRole('listitem');
    expect(items.map((item) => within(item).getByText(/^Sample size: /).textContent)).toEqual([
      'Sample size: 9,317',
      'Sample size: 4,206',
      'Sample size: 815',
      'Sample size: 42',
    ]);
    const text = (container.textContent ?? '').replace(/Sample size: [\d,]+/g, '');
    expect(text).not.toContain('%');
    for (const value of ['9,317', '9317', '4,206', '4206', '815', '42']) {
      expect(text).not.toContain(value);
    }
  });

  it('renders the sanctioned browse-all link to the directory, outside the card list', () => {
    render(<FeaturedCharges charges={FEATURED} />);
    const browseAll = screen.getByRole('link', { name: BROWSE_ALL_CHARGES_LINK_TEXT });
    expect(browseAll).toHaveAttribute('href', '/charges');
    expect(
      within(screen.getByRole('list')).queryByRole('link', { name: BROWSE_ALL_CHARGES_LINK_TEXT }),
    ).not.toBeInTheDocument();
  });
});
