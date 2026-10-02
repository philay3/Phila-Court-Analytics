import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import type { JudgeMatch, SearchIndexJudge } from '@pca/shared';
import { JudgeSearchInput } from './JudgeSearchInput.js';
import { JUDGE_SEARCH_COPY } from './judge-search-copy.js';

const DEBOUNCE_MS = 250;

// Invented judges. "Beta Judge" matches "b-j" only through its alias.
const JUDGES: SearchIndexJudge[] = [
  { slug: 'alpha-judge', displayName: 'Judge Alpha', aliases: [] },
  { slug: 'beta-judge', displayName: 'Beta Judge', aliases: ['b-judge'] },
];
const ALPHA_MATCH: JudgeMatch = { slug: 'alpha-judge', displayName: 'Judge Alpha' };

/** A parent harness mirroring SearchForm's committed-judge ownership. */
function Harness({
  judges = JUDGES,
  onCommit,
}: {
  judges?: readonly SearchIndexJudge[] | null;
  onCommit?: (judge: JudgeMatch | null) => void;
}) {
  const [committed, setCommitted] = useState<JudgeMatch | null>(null);
  return (
    <JudgeSearchInput
      id="judge-search"
      describedById="judge-search-help"
      judges={judges}
      committedJudge={committed}
      onCommitChange={(judge) => {
        onCommit?.(judge);
        setCommitted(judge);
      }}
    />
  );
}

async function settleDebounce(): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(DEBOUNCE_MS);
  });
}

function combobox(): HTMLInputElement {
  return screen.getByRole('combobox') as HTMLInputElement;
}

beforeEach(() => {
  vi.useFakeTimers();
  // No network anywhere in this component: a fetch would be a regression.
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.reject(new Error('JudgeSearchInput must not fetch'))),
  );
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('JudgeSearchInput (scoped, client-side)', () => {
  it('is disabled until the parent supplies a judge list, and enabled once it does', () => {
    const { unmount } = render(<Harness judges={null} />);
    expect(combobox()).toBeDisabled();
    unmount();
    render(<Harness />);
    expect(combobox()).not.toBeDisabled();
  });

  it('offers no suggestions below SEARCH_Q_MIN_LENGTH and never calls fetch', async () => {
    render(<Harness />);
    fireEvent.change(combobox(), { target: { value: '   ' } });
    await settleDebounce();
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });

  it('renders display name and matched alias from the supplied list; a mouse click commits and closes', async () => {
    const onCommit = vi.fn();
    render(<Harness onCommit={onCommit} />);

    fireEvent.change(combobox(), { target: { value: 'b-j' } });
    await settleDebounce();
    expect(screen.getByText('Beta Judge')).toBeInTheDocument();
    expect(screen.getByText(`${JUDGE_SEARCH_COPY.matchedAliasPrefix}b-judge`)).toBeInTheDocument();

    fireEvent.change(combobox(), { target: { value: 'judge' } });
    await settleDebounce();
    expect(screen.getAllByRole('option')).toHaveLength(2);

    fireEvent.click(screen.getByText('Judge Alpha'));
    expect(onCommit).toHaveBeenLastCalledWith(ALPHA_MATCH);
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    expect(combobox().value).toBe('Judge Alpha');
    expect(fetch).not.toHaveBeenCalled();
  });

  it('supports keyboard selection: ArrowDown then Enter commits the active option', async () => {
    const onCommit = vi.fn();
    render(<Harness onCommit={onCommit} />);
    const input = combobox();

    fireEvent.change(input, { target: { value: 'judge' } });
    await settleDebounce();

    expect(input).toHaveAttribute('aria-expanded', 'true');
    fireEvent.keyDown(input, { key: 'ArrowDown' });
    const firstOption = screen.getAllByRole('option')[0]!;
    expect(input.getAttribute('aria-activedescendant')).toBe(firstOption.id);
    expect(input).toHaveAttribute('aria-controls', screen.getByRole('listbox').id);

    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onCommit).toHaveBeenLastCalledWith(ALPHA_MATCH);
    expect(combobox().value).toBe('Judge Alpha');
  });

  it('closes on Escape, clears on a second Escape', async () => {
    render(<Harness />);
    const input = combobox();

    fireEvent.change(input, { target: { value: 'alpha' } });
    await settleDebounce();
    expect(screen.getByRole('listbox')).toBeInTheDocument();

    fireEvent.keyDown(input, { key: 'Escape' });
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    expect(input).toHaveAttribute('aria-expanded', 'false');
    expect(input.value).toBe('alpha');

    fireEvent.keyDown(input, { key: 'Escape' });
    expect(input.value).toBe('');
  });

  it('clears the committed judge when the input is edited after a commit', async () => {
    const onCommit = vi.fn();
    render(<Harness onCommit={onCommit} />);
    const input = combobox();

    fireEvent.change(input, { target: { value: 'alpha' } });
    await settleDebounce();
    fireEvent.click(screen.getByText('Judge Alpha'));
    expect(onCommit).toHaveBeenLastCalledWith(ALPHA_MATCH);

    fireEvent.change(input, { target: { value: 'Judge Alpha extra' } });
    expect(onCommit).toHaveBeenLastCalledWith(null);
  });

  it('renders the no-result copy for a valid query with zero suggestions, and for an empty list', async () => {
    const { unmount } = render(<Harness />);
    fireEvent.change(combobox(), { target: { value: 'zzzzz' } });
    await settleDebounce();
    expect(screen.getByText(JUDGE_SEARCH_COPY.noResult)).toBeInTheDocument();
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    unmount();

    render(<Harness judges={[]} />);
    fireEvent.change(combobox(), { target: { value: 'judge' } });
    await settleDebounce();
    expect(screen.getByText(JUDGE_SEARCH_COPY.noResult)).toBeInTheDocument();
  });
});
