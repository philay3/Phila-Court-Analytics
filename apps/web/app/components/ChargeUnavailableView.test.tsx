import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import {
  CHARGE_RESULT_UNAVAILABLE_MESSAGE,
  PUBLIC_ERROR_CODES,
  type ChargeOnlyResultUnavailable,
} from '@pca/shared';
import { CHARGE_RESULT_COPY } from './charge-result-copy.js';
import { ChargeUnavailableView } from './ChargeUnavailableView.js';

vi.mock('next/link', () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) => (
    <a href={typeof href === 'string' ? href : ''} {...rest}>
      {children}
    </a>
  ),
}));

const UNAVAILABLE: ChargeOnlyResultUnavailable = {
  resultType: 'charge_only_unavailable',
  code: PUBLIC_ERROR_CODES.CHARGE_RESULT_UNAVAILABLE,
  message: CHARGE_RESULT_UNAVAILABLE_MESSAGE,
  charge: {
    id: '00000000-0000-0000-0000-000000000009',
    slug: 'harassment',
    displayName: 'Harassment',
  },
  links: { methodology: '/methodology', definitions: '/definitions' },
};

describe('ChargeUnavailableView', () => {
  it('renders charge identity, the pinned shared unavailable message, and both links', () => {
    render(<ChargeUnavailableView data={UNAVAILABLE} />);

    expect(screen.getByRole('heading', { level: 1, name: 'Harassment' })).toBeInTheDocument();
    // Message asserted via the imported @pca/shared constant, never re-typed.
    expect(screen.getByText(CHARGE_RESULT_UNAVAILABLE_MESSAGE)).toBeInTheDocument();

    const methodology = screen.getByRole('link', { name: CHARGE_RESULT_COPY.methodologyLinkText });
    const definitions = screen.getByRole('link', { name: CHARGE_RESULT_COPY.definitionsLinkText });
    expect(methodology).toHaveAttribute('href', '/methodology');
    expect(definitions).toHaveAttribute('href', '/definitions');
  });
});
