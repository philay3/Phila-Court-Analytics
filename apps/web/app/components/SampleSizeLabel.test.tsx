import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SampleSizeLabel } from './SampleSizeLabel.js';
import { formatSampleSize } from '../lib/formatters.js';

describe('SampleSizeLabel', () => {
  it('renders the noun-free pinned "Sample size: N" format via the 11.4 utility', () => {
    render(<SampleSizeLabel sampleSize={1234} />);
    expect(screen.getByText(formatSampleSize(1234))).toBeInTheDocument();
    expect(screen.getByText('Sample size: 1,234')).toBeInTheDocument();
  });

  it('renders a zero sample size without inventing a value', () => {
    render(<SampleSizeLabel sampleSize={0} />);
    expect(screen.getByText('Sample size: 0')).toBeInTheDocument();
  });
});
