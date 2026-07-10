import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ResponsibleUseNotice } from './ResponsibleUseNotice.js';
import { RESULT_DISPLAY_COPY } from './result-display-copy.js';

describe('ResponsibleUseNotice', () => {
  it('renders all four required statements: historical aggregates, not legal advice, not a prediction, cases vary', () => {
    render(<ResponsibleUseNotice />);
    expect(screen.getByText(RESULT_DISPLAY_COPY.responsibleUseHistorical)).toBeInTheDocument();
    expect(screen.getByText(RESULT_DISPLAY_COPY.responsibleUseNotLegalAdvice)).toBeInTheDocument();
    expect(screen.getByText(RESULT_DISPLAY_COPY.responsibleUseNotPrediction)).toBeInTheDocument();
    expect(screen.getByText(RESULT_DISPLAY_COPY.responsibleUseCasesVary)).toBeInTheDocument();
  });
});
