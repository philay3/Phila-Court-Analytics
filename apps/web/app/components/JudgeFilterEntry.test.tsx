import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import type { JudgeSearchResult } from '@pca/shared';
import { CHARGE_RESULT_COPY } from './charge-result-copy.js';
import { JudgeFilterEntry } from './JudgeFilterEntry.js';

const DEBOUNCE_MS = 250;

// Router push is hoisted so the next/navigation mock can capture navigations.
const { pushMock } = vi.hoisted(() => ({ pushMock: vi.fn() }));
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: pushMock }) }));

const ALPHA: JudgeSearchResult = {
  id: '11111111-1111-1111-1111-111111111111',
  slug: 'alpha-judge',
  displayName: 'Judge Alpha',
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

async function settleDebounce(): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(DEBOUNCE_MS);
  });
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  pushMock.mockReset();
});

describe('JudgeFilterEntry', () => {
  it('renders the availability-caveat help copy', () => {
    render(<JudgeFilterEntry chargeSlug="theft" />);
    expect(screen.getByText(CHARGE_RESULT_COPY.judgeFilterHelp)).toBeInTheDocument();
  });

  it('routes to the judge-specific result when a judge is selected', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(jsonResponse({ results: [ALPHA] }))),
    );
    render(<JudgeFilterEntry chargeSlug="theft" />);

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'alpha' } });
    await settleDebounce();

    fireEvent.click(screen.getByText(ALPHA.displayName));

    expect(pushMock).toHaveBeenCalledWith(`/charges/theft/judge/${ALPHA.slug}`);
  });
});
