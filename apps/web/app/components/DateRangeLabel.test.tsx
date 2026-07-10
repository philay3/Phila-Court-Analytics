import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { DateRange } from '@pca/shared';
import { DateRangeLabel } from './DateRangeLabel.js';
import { formatDateRange } from '../lib/formatters.js';

describe('DateRangeLabel', () => {
  it('renders an API-provided range via the 11.4 utility', () => {
    const range: DateRange = { start: '2025-01-01', end: '2026-06-30' };
    render(<DateRangeLabel range={range} />);
    expect(screen.getByText(formatDateRange(range))).toBeInTheDocument();
  });

  it('renders nothing when the optional range is absent — never invents a default', () => {
    const { container } = render(<DateRangeLabel />);
    expect(container).toBeEmptyDOMElement();
  });
});
