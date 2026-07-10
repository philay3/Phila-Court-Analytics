import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ThinDataBadge } from './ThinDataBadge.js';
import { THIN_DATA_LABEL } from '../lib/formatters.js';

describe('ThinDataBadge', () => {
  it('renders the pinned "Based on a small sample." label when thin', () => {
    render(<ThinDataBadge thin />);
    expect(screen.getByText(THIN_DATA_LABEL)).toBeInTheDocument();
    // Pinned wording, asserted exactly.
    expect(THIN_DATA_LABEL).toBe('Based on a small sample.');
  });

  it('renders nothing when not thin', () => {
    const { container } = render(<ThinDataBadge thin={false} />);
    expect(container).toBeEmptyDOMElement();
  });
});
