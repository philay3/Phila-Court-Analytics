import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { CHARGES_COPY } from './charges-copy.js';
import Loading from './loading.js';

describe('charges directory loading state', () => {
  it('renders the neutral placeholder copy as a status', () => {
    render(<Loading />);
    expect(screen.getByRole('status')).toHaveTextContent(CHARGES_COPY.loadingMessage);
  });
});
