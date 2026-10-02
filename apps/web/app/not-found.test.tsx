import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import {
  BROWSE_ALL_CHARGES_LINK_TEXT,
  ROOT_NOT_FOUND_HEADING,
  ROOT_NOT_FOUND_HOME_LINK_TEXT,
  ROOT_NOT_FOUND_MESSAGE,
} from '@pca/shared';
import NotFound from './not-found.js';

vi.mock('next/link', () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

describe('root not-found page (STATIC-2b)', () => {
  it('renders the pinned heading, message, and both links verbatim', () => {
    render(<NotFound />);
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(ROOT_NOT_FOUND_HEADING);
    expect(screen.getByText(ROOT_NOT_FOUND_MESSAGE)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: ROOT_NOT_FOUND_HOME_LINK_TEXT })).toHaveAttribute(
      'href',
      '/',
    );
    expect(screen.getByRole('link', { name: BROWSE_ALL_CHARGES_LINK_TEXT })).toHaveAttribute(
      'href',
      '/charges',
    );
  });
});
