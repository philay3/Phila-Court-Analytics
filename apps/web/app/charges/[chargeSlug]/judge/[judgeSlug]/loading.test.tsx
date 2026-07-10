import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { CHARGE_RESULT_COPY } from '../../../../components/charge-result-copy.js';
import Loading from './loading.js';

describe('judge-specific loading state', () => {
  it('renders the neutral placeholder copy', () => {
    render(<Loading />);
    expect(screen.getByText(CHARGE_RESULT_COPY.loadingMessage)).toBeInTheDocument();
  });
});
