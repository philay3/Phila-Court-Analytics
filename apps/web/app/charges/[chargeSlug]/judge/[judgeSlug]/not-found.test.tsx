import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { JUDGE_RESULT_NOT_FOUND_MESSAGE } from '@pca/shared';
import { CHARGE_RESULT_COPY } from '../../../../components/charge-result-copy.js';
import NotFound from './not-found.js';

vi.mock('next/link', () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) => (
    <a href={typeof href === 'string' ? href : ''} {...rest}>
      {children}
    </a>
  ),
}));

describe('judge-route not-found boundary (fix R7b)', () => {
  it('renders a page heading, the pinned combination message, and a link back to search', () => {
    render(<NotFound />);
    // Terminal state carries an h1 for heading navigation (task 15.1 a11y pass).
    expect(
      screen.getByRole('heading', { level: 1, name: CHARGE_RESULT_COPY.notFoundHeading }),
    ).toBeInTheDocument();
    // Message asserted via the imported @pca/shared constant, never re-typed.
    expect(screen.getByText(JUDGE_RESULT_NOT_FOUND_MESSAGE)).toBeInTheDocument();
    const home = screen.getByRole('link', { name: CHARGE_RESULT_COPY.notFoundHomeLinkText });
    expect(home).toHaveAttribute('href', '/');
  });
});
