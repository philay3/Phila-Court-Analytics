import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ThinDataCallout } from './ThinDataCallout.js';
import { RESULT_DISPLAY_COPY } from './result-display-copy.js';

describe('ThinDataCallout', () => {
  it('renders the plain-English explanation when thin', () => {
    render(<ThinDataCallout thin />);
    expect(screen.getByText(RESULT_DISPLAY_COPY.thinDataCalloutBody)).toBeInTheDocument();
  });

  it('renders nothing when not thin', () => {
    const { container } = render(<ThinDataCallout thin={false} />);
    expect(container).toBeEmptyDOMElement();
  });
});
