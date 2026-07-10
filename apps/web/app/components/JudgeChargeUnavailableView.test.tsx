import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { CHARGE_RESULT_UNAVAILABLE_MESSAGE } from '@pca/shared';
import { CHARGE_RESULT_COPY } from './charge-result-copy.js';
import { JudgeChargeUnavailableView } from './JudgeChargeUnavailableView.js';

vi.mock('next/link', () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) => (
    <a href={typeof href === 'string' ? href : ''} {...rest}>
      {children}
    </a>
  ),
}));

describe('JudgeChargeUnavailableView', () => {
  it('renders a heading, the pinned shared unavailable message, and both links', () => {
    render(<JudgeChargeUnavailableView />);

    // Terminal state carries an h1 for heading navigation (task 15.1 a11y pass).
    expect(
      screen.getByRole('heading', { level: 1, name: CHARGE_RESULT_COPY.chargeUnavailableHeading }),
    ).toBeInTheDocument();
    // Message asserted via the imported @pca/shared constant, never re-typed.
    expect(screen.getByText(CHARGE_RESULT_UNAVAILABLE_MESSAGE)).toBeInTheDocument();

    const methodology = screen.getByRole('link', { name: CHARGE_RESULT_COPY.methodologyLinkText });
    const definitions = screen.getByRole('link', { name: CHARGE_RESULT_COPY.definitionsLinkText });
    expect(methodology).toHaveAttribute('href', '/methodology');
    expect(definitions).toHaveAttribute('href', '/definitions');
  });
});
