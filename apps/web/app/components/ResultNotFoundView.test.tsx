import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { CHARGE_NOT_FOUND_MESSAGE, JUDGE_NOT_FOUND_MESSAGE } from '@pca/shared';
import { CHARGE_RESULT_COPY } from './charge-result-copy.js';
import { ResultNotFoundView } from './ResultNotFoundView.js';

vi.mock('next/link', () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) => (
    <a href={typeof href === 'string' ? href : ''} {...rest}>
      {children}
    </a>
  ),
}));

describe('ResultNotFoundView', () => {
  it('renders a page heading, the missing-charge pinned message, and a link back to search', () => {
    // Message asserted via the imported @pca/shared constant, never re-typed.
    render(<ResultNotFoundView message={CHARGE_NOT_FOUND_MESSAGE} />);

    // Terminal state carries an h1 for heading navigation (task 15.1 a11y pass).
    expect(
      screen.getByRole('heading', { level: 1, name: CHARGE_RESULT_COPY.notFoundHeading }),
    ).toBeInTheDocument();
    expect(screen.getByText(CHARGE_NOT_FOUND_MESSAGE)).toBeInTheDocument();
    const home = screen.getByRole('link', { name: CHARGE_RESULT_COPY.notFoundHomeLinkText });
    expect(home).toHaveAttribute('href', '/');
  });

  it('renders the missing-judge pinned message and a link back to search', () => {
    render(<ResultNotFoundView message={JUDGE_NOT_FOUND_MESSAGE} />);

    expect(screen.getByText(JUDGE_NOT_FOUND_MESSAGE)).toBeInTheDocument();
    const home = screen.getByRole('link', { name: CHARGE_RESULT_COPY.notFoundHomeLinkText });
    expect(home).toHaveAttribute('href', '/');
  });
});
