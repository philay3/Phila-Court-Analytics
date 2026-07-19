import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import {
  BROWSE_ALL_CHARGES_LINK_TEXT,
  FEATURED_CHARGES_HEADING,
  CHARGE_DIRECTORY_UNAVAILABLE_MESSAGE,
  type ChargeDirectoryEntry,
} from '@pca/shared';
import { HOME_COPY } from './components/home-copy.js';
import { CHARGE_SEARCH_COPY } from './components/charge-search-copy.js';

/**
 * Homepage composition (task DP-5, pins 5 and 8): the featured section is
 * strictly fail-soft. Every arm — top rows, fewer than 4, zero rows, the
 * unavailable arm, a failed fetch, a THROWN fetch — is exercised here with
 * the fetch mocked at the public-api-client seam; the search surface must
 * render in every arm and the page must never throw because of the section.
 */
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

const getCharges = vi.fn();
// Partial mock: only the directory fetch is stubbed; the search functions the
// combobox children import from the same module stay real (never called here).
vi.mock('./lib/public-api-client.js', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./lib/public-api-client.js')>()),
  getCharges: () => getCharges(),
}));

const { default: HomePage } = await import('./page.js');

// Invented charge names (never real docket data), served order sample-size
// descending per the DP-5 API pin.
const ROWS = [
  {
    slug: 'hotel-example',
    displayName: 'Hotel Example',
    hasSentencing: true,
    outcomeSampleSize: 5150,
  },
  {
    slug: 'india-example',
    displayName: 'India Example',
    hasSentencing: true,
    outcomeSampleSize: 2048,
  },
  {
    slug: 'juliet-example',
    displayName: 'Juliet Example',
    hasSentencing: false,
    outcomeSampleSize: 512,
  },
  {
    slug: 'kilo-example',
    displayName: 'Kilo Example',
    hasSentencing: false,
    outcomeSampleSize: 64,
  },
  {
    slug: 'lima-example',
    displayName: 'Lima Example',
    hasSentencing: false,
    outcomeSampleSize: 8,
  },
] satisfies ChargeDirectoryEntry[];

afterEach(() => {
  getCharges.mockReset();
});

function expectSearchSurface(): void {
  expect(screen.getByRole('heading', { level: 1, name: HOME_COPY.heading })).toBeInTheDocument();
  expect(screen.getByText(HOME_COPY.chargeLabel)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: CHARGE_SEARCH_COPY.submitButton })).toBeInTheDocument();
}

function expectNoFeaturedSection(): void {
  expect(screen.queryByText(FEATURED_CHARGES_HEADING)).not.toBeInTheDocument();
  expect(screen.queryByText(BROWSE_ALL_CHARGES_LINK_TEXT)).not.toBeInTheDocument();
}

describe('HomePage featured section', () => {
  it('renders the top 4 served rows as cards, in served order, with the browse-all link', async () => {
    getCharges.mockResolvedValue({ ok: true, data: { available: true, charges: ROWS } });
    render(await HomePage());

    expect(screen.getByText(FEATURED_CHARGES_HEADING)).toBeInTheDocument();
    const items = within(screen.getByRole('list')).getAllByRole('listitem');
    expect(items).toHaveLength(4);
    expect(items.map((item) => within(item).getByRole('link').textContent)).toEqual([
      'Hotel Example',
      'India Example',
      'Juliet Example',
      'Kilo Example',
    ]);
    // The fifth row never renders: the section is exactly the top 4.
    expect(screen.queryByText('Lima Example')).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: BROWSE_ALL_CHARGES_LINK_TEXT })).toHaveAttribute(
      'href',
      '/charges',
    );
    expectSearchSurface();
  });

  it('renders however many rows exist when fewer than 4 are available', async () => {
    getCharges.mockResolvedValue({
      ok: true,
      data: { available: true, charges: ROWS.slice(0, 2) },
    });
    render(await HomePage());

    expect(within(screen.getByRole('list')).getAllByRole('listitem')).toHaveLength(2);
    expectSearchSurface();
  });

  it('omits the section entirely on zero rows; the search surface renders normally', async () => {
    getCharges.mockResolvedValue({ ok: true, data: { available: true, charges: [] } });
    render(await HomePage());

    expectNoFeaturedSection();
    expectSearchSurface();
  });

  it('omits the section on the served unavailable arm', async () => {
    getCharges.mockResolvedValue({
      ok: true,
      data: { available: false, message: CHARGE_DIRECTORY_UNAVAILABLE_MESSAGE },
    });
    render(await HomePage());

    expectNoFeaturedSection();
    expectSearchSurface();
  });

  it('omits the section on a failed fetch result; the homepage never errors', async () => {
    getCharges.mockResolvedValue({ ok: false, error: { kind: 'fetch_failed' } });
    render(await HomePage());

    expectNoFeaturedSection();
    expectSearchSurface();
  });

  it('omits the section when the fetch THROWS; the homepage never errors', async () => {
    getCharges.mockRejectedValue(new Error('network exploded'));
    render(await HomePage());

    expectNoFeaturedSection();
    expectSearchSurface();
  });
});
