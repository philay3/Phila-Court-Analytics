import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SampleSizeLabel } from './SampleSizeLabel.js';
import { formatRecordsLabel, formatSentenceComponentsLabel } from '../lib/formatters.js';

describe('SampleSizeLabel', () => {
  it('renders the pre-formatted label it is given (35.3 reconciled labels)', () => {
    render(<SampleSizeLabel label={formatRecordsLabel(1234)} />);
    expect(screen.getByText('Records: 1,234')).toBeInTheDocument();
  });

  it('renders the sentence-components label without altering it', () => {
    render(<SampleSizeLabel label={formatSentenceComponentsLabel(0)} />);
    expect(screen.getByText('Sentence components: 0')).toBeInTheDocument();
  });
});
