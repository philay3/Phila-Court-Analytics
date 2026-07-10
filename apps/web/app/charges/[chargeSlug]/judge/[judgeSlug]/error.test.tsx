import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { CHARGE_RESULT_COPY } from '../../../../components/charge-result-copy.js';
import JudgeError from './error.js';

describe('judge-specific error boundary', () => {
  it('renders generic safe copy and never surfaces the thrown error detail', () => {
    const secret = 'internal-db-connection-string-leak';
    render(<JudgeError error={new Error(secret)} reset={() => {}} />);

    expect(screen.getByText(CHARGE_RESULT_COPY.errorHeading)).toBeInTheDocument();
    expect(screen.getByText(CHARGE_RESULT_COPY.errorBody)).toBeInTheDocument();
    // No internal detail from the thrown error reaches the DOM.
    expect(screen.queryByText(secret)).not.toBeInTheDocument();
  });

  it('invokes reset when the retry control is pressed', () => {
    const reset = vi.fn();
    render(<JudgeError error={new Error('boom')} reset={reset} />);

    fireEvent.click(screen.getByRole('button', { name: CHARGE_RESULT_COPY.errorRetryText }));
    expect(reset).toHaveBeenCalledOnce();
  });
});
