import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { JUDGE_FILTER_HELP_MESSAGE, type SearchIndexJudge } from '@pca/shared';
import { JudgeFilterEntry } from './JudgeFilterEntry.js';

const DEBOUNCE_MS = 250;

const JUDGES: SearchIndexJudge[] = [
  { slug: 'alpha-judge', displayName: 'Judge Alpha', aliases: [] },
  { slug: 'beta-judge', displayName: 'Judge Beta', aliases: [] },
];

async function settleDebounce(): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(DEBOUNCE_MS);
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.reject(new Error('JudgeFilterEntry must not fetch'))),
  );
  // jsdom has no layout: stub the scroll-to-top the in-place selection requests.
  vi.stubGlobal('scrollTo', vi.fn());
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('JudgeFilterEntry (in-page, STATIC-2b)', () => {
  it('renders the sanctioned shared help line (DP-5) and nothing more', () => {
    render(<JudgeFilterEntry chargeSlug="theft" judges={JUDGES} />);
    expect(screen.getByText(JUDGE_FILTER_HELP_MESSAGE)).toBeInTheDocument();
    expect(document.getElementById('judge-filter-help')?.textContent).toBe(
      JUDGE_FILTER_HELP_MESSAGE,
    );
  });

  it('offers only the baked judge list and selects in place with history.pushState (no navigation)', async () => {
    const pushState = vi.spyOn(window.history, 'pushState');
    render(<JudgeFilterEntry chargeSlug="theft" judges={JUDGES} />);

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'judge' } });
    await settleDebounce();
    expect(screen.getAllByRole('option')).toHaveLength(2);

    fireEvent.click(screen.getByText('Judge Alpha'));

    expect(pushState).toHaveBeenCalledWith(null, '', '/charges/theft?judge=alpha-judge');
    expect(window.scrollTo).toHaveBeenCalledWith({ top: 0 });
    expect(fetch).not.toHaveBeenCalled();
  });
});
