import { describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import type { ComponentProps, ReactNode } from 'react';
import { formatLastRefreshed } from '../lib/formatters.js';
import { CHARGE_RESULT_COPY } from './charge-result-copy.js';
import { RESULT_DISPLAY_COPY } from './result-display-copy.js';
import { ResultMetadataAside } from './ResultMetadataAside.js';

// next/link renders an anchor; stub it so jsdom needs no router context.
vi.mock('next/link', () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

const LAST_REFRESHED = '2026-07-01T14:30:00.000Z';

function renderAside(overrides: Partial<ComponentProps<typeof ResultMetadataAside>> = {}) {
  return render(
    <ResultMetadataAside
      lastRefreshed={LAST_REFRESHED}
      links={{ methodology: '/methodology', definitions: '/definitions' }}
      {...overrides}
    />,
  );
}

describe('ResultMetadataAside', () => {
  it('is an aside labelled by the sanctioned heading', () => {
    renderAside();

    const aside = screen.getByRole('complementary', { name: RESULT_DISPLAY_COPY.asideHeading });
    expect(aside).toHaveAttribute('data-testid', 'section-metadata');
    expect(
      within(aside).getByRole('heading', { level: 2, name: RESULT_DISPLAY_COPY.asideHeading }),
    ).toBeInTheDocument();
  });

  it('renders the relocated last-refreshed line byte-identically (label + 11.4 formatter)', () => {
    renderAside();

    expect(
      screen.getByText(
        `${CHARGE_RESULT_COPY.lastRefreshedLabel}: ${formatLastRefreshed(LAST_REFRESHED)}`,
      ),
    ).toBeInTheDocument();
  });

  it('renders the relocated Methodology and Definitions links with the API hrefs', () => {
    renderAside();

    expect(
      screen.getByRole('link', { name: CHARGE_RESULT_COPY.methodologyLinkText }),
    ).toHaveAttribute('href', '/methodology');
    expect(
      screen.getByRole('link', { name: CHARGE_RESULT_COPY.definitionsLinkText }),
    ).toHaveAttribute('href', '/definitions');
  });

  it('renders children between the heading and the last-refreshed line, and actions after it', () => {
    renderAside({
      children: <p data-testid="aside-child">child row</p>,
      actions: <p data-testid="aside-action">action row</p>,
    });

    const aside = screen.getByRole('complementary', { name: RESULT_DISPLAY_COPY.asideHeading });
    const order = Array.from(aside.querySelectorAll('h2, p')).map(
      (el) => el.getAttribute('data-testid') ?? el.tagName.toLowerCase(),
    );
    // heading → children → last-refreshed → actions → links paragraph.
    expect(order).toEqual(['h2', 'aside-child', 'p', 'aside-action', 'p']);
  });
});
