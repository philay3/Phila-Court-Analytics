import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { FETCH_FAILURE_MESSAGE, PUBLIC_ERROR_MESSAGES, type JudgeSearchResult } from '@pca/shared';
import { JudgeSearchInput } from './JudgeSearchInput.js';
import { JUDGE_SEARCH_COPY } from './judge-search-copy.js';

const DEBOUNCE_MS = 250;

const ALPHA: JudgeSearchResult = {
  id: '11111111-1111-1111-1111-111111111111',
  slug: 'alpha-judge',
  displayName: 'Judge Alpha',
};
const BETA: JudgeSearchResult = {
  id: '22222222-2222-2222-2222-222222222222',
  slug: 'beta-judge',
  displayName: 'Judge Beta',
  matchedAlias: 'b-judge',
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

/** A parent harness mirroring SearchForm's committed-judge ownership. */
function Harness({ onCommit }: { onCommit?: (judge: JudgeSearchResult | null) => void }) {
  const [committed, setCommitted] = useState<JudgeSearchResult | null>(null);
  return (
    <JudgeSearchInput
      id="judge-search"
      describedById="judge-search-help"
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
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('JudgeSearchInput', () => {
  it('is labeled optional via the visible label wiring', () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(jsonResponse({ results: [] }))),
    );
    render(<Harness />);
    // The "(optional)" label lives on the form label (HOME_COPY.judgeLabel);
    // this component's input is a non-disabled combobox that never blocks.
    expect(combobox()).not.toBeDisabled();
  });

  it('fires no request when the trimmed query is below SEARCH_Q_MIN_LENGTH', async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse({ results: [] })));
    vi.stubGlobal('fetch', fetchMock);
    render(<Harness />);

    fireEvent.change(combobox(), { target: { value: '   ' } });
    await settleDebounce();

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('renders the loading state while a request is in flight', async () => {
    const deferred: Array<(response: Response) => void> = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(() => new Promise<Response>((resolve) => deferred.push(resolve))),
    );
    render(<Harness />);

    fireEvent.change(combobox(), { target: { value: 'jud' } });
    await settleDebounce();

    expect(screen.getByText(JUDGE_SEARCH_COPY.loading)).toBeInTheDocument();

    await act(async () => {
      deferred[0]?.(jsonResponse({ results: [ALPHA] }));
      await vi.advanceTimersByTimeAsync(0);
    });
  });

  it('renders display name and matched alias; a mouse click commits and closes', async () => {
    const onCommit = vi.fn();
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(jsonResponse({ results: [ALPHA, BETA] }))),
    );
    render(<Harness onCommit={onCommit} />);

    fireEvent.change(combobox(), { target: { value: 'judge' } });
    await settleDebounce();

    expect(screen.getByText(ALPHA.displayName)).toBeInTheDocument();
    expect(
      screen.getByText(`${JUDGE_SEARCH_COPY.matchedAliasPrefix}${BETA.matchedAlias}`),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByText(ALPHA.displayName));

    expect(onCommit).toHaveBeenLastCalledWith(ALPHA);
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    expect(combobox().value).toBe(ALPHA.displayName);
  });

  it('supports keyboard selection: ArrowDown then Enter commits the active option', async () => {
    const onCommit = vi.fn();
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(jsonResponse({ results: [ALPHA, BETA] }))),
    );
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
    expect(onCommit).toHaveBeenLastCalledWith(ALPHA);
    expect(combobox().value).toBe(ALPHA.displayName);
  });

  it('closes on Escape, clears on a second Escape', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(jsonResponse({ results: [ALPHA] }))),
    );
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
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(jsonResponse({ results: [ALPHA] }))),
    );
    render(<Harness onCommit={onCommit} />);
    const input = combobox();

    fireEvent.change(input, { target: { value: 'alpha' } });
    await settleDebounce();
    fireEvent.click(screen.getByText(ALPHA.displayName));
    expect(onCommit).toHaveBeenLastCalledWith(ALPHA);

    fireEvent.change(input, { target: { value: `${ALPHA.displayName} extra` } });
    expect(onCommit).toHaveBeenLastCalledWith(null);
  });

  it('renders the no-result copy for a valid query with zero suggestions', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(jsonResponse({ results: [] }))),
    );
    render(<Harness />);

    fireEvent.change(combobox(), { target: { value: 'zzzzz' } });
    await settleDebounce();

    expect(screen.getByText(JUDGE_SEARCH_COPY.noResult)).toBeInTheDocument();
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  });

  it('renders the shared error-message copy on an API error', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          jsonResponse(
            {
              statusCode: 429,
              code: 'RATE_LIMITED',
              error: 'Too Many Requests',
              message: 'slow down',
              requestId: 'req-1',
            },
            429,
          ),
        ),
      ),
    );
    render(<Harness />);

    fireEvent.change(combobox(), { target: { value: 'jud' } });
    await settleDebounce();

    expect(screen.getByText(PUBLIC_ERROR_MESSAGES.RATE_LIMITED)).toBeInTheDocument();
  });

  it('renders the transport-failure copy when the request rejects', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new Error('network down'))),
    );
    render(<Harness />);

    fireEvent.change(combobox(), { target: { value: 'jud' } });
    await settleDebounce();

    expect(screen.getByText(FETCH_FAILURE_MESSAGE)).toBeInTheDocument();
  });

  it('never lets a stale response overwrite a newer query', async () => {
    const deferred: Array<(response: Response) => void> = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(() => new Promise<Response>((resolve) => deferred.push(resolve))),
    );
    render(<Harness />);
    const input = combobox();

    fireEvent.change(input, { target: { value: 'a' } });
    await settleDebounce();
    fireEvent.change(input, { target: { value: 'ab' } });
    await settleDebounce();

    await act(async () => {
      deferred[1]?.(jsonResponse({ results: [BETA] }));
      await vi.advanceTimersByTimeAsync(0);
    });
    await act(async () => {
      deferred[0]?.(jsonResponse({ results: [ALPHA] }));
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(screen.getByText(BETA.displayName)).toBeInTheDocument();
    expect(screen.queryByText(ALPHA.displayName)).not.toBeInTheDocument();
  });
});
