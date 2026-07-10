import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import {
  JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE,
  PUBLIC_ERROR_CODES,
  type JudgeSpecificResultUnavailable,
} from '@pca/shared';
import { JUDGE_RESULT_COPY } from './judge-result-copy.js';
import { JudgeUnavailableView } from './JudgeUnavailableView.js';

vi.mock('next/link', () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) => (
    <a href={typeof href === 'string' ? href : ''} {...rest}>
      {children}
    </a>
  ),
}));

const CHARGE = {
  id: '00000000-0000-0000-0000-000000000001',
  slug: 'theft',
  displayName: 'Theft',
} as const;

const JUDGE = {
  id: '00000000-0000-0000-0000-000000000002',
  slug: 'example-judge',
  displayName: 'Example judge',
} as const;

const UNAVAILABLE: JudgeSpecificResultUnavailable = {
  resultType: 'judge_specific_unavailable',
  code: PUBLIC_ERROR_CODES.JUDGE_SPECIFIC_RESULT_UNAVAILABLE,
  message: JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE,
  charge: CHARGE,
  judge: JUDGE,
  fallback: { chargeOnlyResultPath: '/api/v1/public/results/charge/theft' },
};

describe('JudgeUnavailableView', () => {
  it('renders the pinned shared literal, both names, and a link to the charge-only page', () => {
    render(<JudgeUnavailableView data={UNAVAILABLE} />);

    // Literal asserted via the imported @pca/shared constant, never re-typed.
    expect(screen.getByText(JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE)).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1, name: CHARGE.displayName })).toBeInTheDocument();
    expect(screen.getByText(JUDGE.displayName)).toBeInTheDocument();

    const link = screen.getByRole('link', { name: JUDGE_RESULT_COPY.removeFilterLinkText });
    expect(link).toHaveAttribute('href', `/charges/${CHARGE.slug}`);
  });

  it('renders NO distribution sections — only the literal, names, and charge-only link', () => {
    const { container } = render(<JudgeUnavailableView data={UNAVAILABLE} />);

    // No outcome/sentencing tables and no presentational bars are rendered.
    expect(screen.queryAllByRole('table')).toHaveLength(0);
    expect(container.querySelectorAll('[data-testid^="distribution-bar-fill-"]')).toHaveLength(0);
  });

  it('never surfaces the internal error code', () => {
    render(<JudgeUnavailableView data={UNAVAILABLE} />);
    expect(
      screen.queryByText(PUBLIC_ERROR_CODES.JUDGE_SPECIFIC_RESULT_UNAVAILABLE),
    ).not.toBeInTheDocument();
  });
});
