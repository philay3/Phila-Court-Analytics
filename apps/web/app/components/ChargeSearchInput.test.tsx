import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { FETCH_FAILURE_MESSAGE, PUBLIC_ERROR_MESSAGES, type ChargeSearchResult } from '@pca/shared';
import { ChargeSearchInput } from './ChargeSearchInput.js';
import { CHARGE_SEARCH_COPY } from './charge-search-copy.js';

const DEBOUNCE_MS = 250;

const ALPHA: ChargeSearchResult = {
  id: '11111111-1111-1111-1111-111111111111',
  slug: 'alpha-charge',
  displayName: 'Alpha Charge',
  statuteCode: '18 § 1111',
};
const BETA: ChargeSearchResult = {
  id: '22222222-2222-2222-2222-222222222222',
  slug: 'beta-charge',
  displayName: 'Beta Charge',
  matchedAlias: 'b-charge',
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

/** A parent harness mirroring SearchForm's committed-charge ownership. */
function Harness({ onCommit }: { onCommit?: (charge: ChargeSearchResult | null) => void }) {
  const [committed, setCommitted] = useState<ChargeSearchResult | null>(null);
  return (
    <ChargeSearchInput
      id="charge-search"
      describedById="charge-search-help"
      committedCharge={committed}
      onCommitChange={(charge) => {
        onCommit?.(charge);
        setCommitted(charge);
      }}
    />
  );
}

/** Advance past the debounce window and flush the fetch microtask chain. */
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

describe('ChargeSearchInput', () => {
  it('fires no request when the trimmed query is below SEARCH_Q_MIN_LENGTH', async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse({ results: [] })));
    vi.stubGlobal('fetch', fetchMock);
    render(<Harness />);

    fireEvent.change(combobox(), { target: { value: '   ' } });
    await settleDebounce();

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('fires exactly one request after the 250 ms debounce despite rapid typing', async () => {
    const fetchMock = vi.fn((url: string) => {
      void url;
      return Promise.resolve(jsonResponse({ results: [ALPHA] }));
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<Harness />);

    const input = combobox();
    fireEvent.change(input, { target: { value: 'r' } });
    fireEvent.change(input, { target: { value: 're' } });
    fireEvent.change(input, { target: { value: 'ret' } });
    expect(fetchMock).not.toHaveBeenCalled(); // still within the debounce window

    await settleDebounce();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('q=ret');
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
    await settleDebounce(); // dispatches request #1 (Alpha), now in flight

    fireEvent.change(input, { target: { value: 'ab' } });
    await settleDebounce(); // dispatches request #2 (Beta), now in flight

    // Resolve the NEWER request first, then the older/stale one.
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

  it('renders the loading state while a request is in flight', async () => {
    const deferred: Array<(response: Response) => void> = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(() => new Promise<Response>((resolve) => deferred.push(resolve))),
    );
    render(<Harness />);

    fireEvent.change(combobox(), { target: { value: 'ret' } });
    await settleDebounce();

    expect(screen.getByText(CHARGE_SEARCH_COPY.loading)).toBeInTheDocument();

    await act(async () => {
      deferred[0]?.(jsonResponse({ results: [ALPHA] }));
      await vi.advanceTimersByTimeAsync(0);
    });
  });

  it('renders display name, statute, and matched alias; a mouse click commits and closes', async () => {
    const onCommit = vi.fn();
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(jsonResponse({ results: [ALPHA, BETA] }))),
    );
    render(<Harness onCommit={onCommit} />);

    fireEvent.change(combobox(), { target: { value: 'charge' } });
    await settleDebounce();

    expect(screen.getByText(ALPHA.displayName)).toBeInTheDocument();
    expect(screen.getByText(ALPHA.statuteCode!)).toBeInTheDocument();
    expect(
      screen.getByText(`${CHARGE_SEARCH_COPY.matchedAliasPrefix}${BETA.matchedAlias}`),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByText(ALPHA.displayName));

    expect(onCommit).toHaveBeenLastCalledWith(ALPHA);
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    expect(combobox().value).toBe(ALPHA.displayName);
  });

  it('tracks ARIA combobox/listbox state and aria-activedescendant', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(jsonResponse({ results: [ALPHA, BETA] }))),
    );
    render(<Harness />);
    const input = combobox();

    expect(input).toHaveAttribute('aria-expanded', 'false');

    fireEvent.change(input, { target: { value: 'charge' } });
    await settleDebounce();

    expect(input).toHaveAttribute('aria-expanded', 'true');
    const listbox = screen.getByRole('listbox');
    expect(input).toHaveAttribute('aria-controls', listbox.id);
    expect(input).not.toHaveAttribute('aria-activedescendant');

    fireEvent.keyDown(input, { key: 'ArrowDown' });
    const firstOption = screen.getAllByRole('option')[0]!;
    expect(input.getAttribute('aria-activedescendant')).toBe(firstOption.id);
    expect(firstOption).toHaveAttribute('aria-selected', 'true');
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

  it('clears the committed charge when the input is edited after a commit', async () => {
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

    expect(screen.getByText(CHARGE_SEARCH_COPY.noResult)).toBeInTheDocument();
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

    fireEvent.change(combobox(), { target: { value: 'ret' } });
    await settleDebounce();

    expect(screen.getByText(PUBLIC_ERROR_MESSAGES.RATE_LIMITED)).toBeInTheDocument();
  });

  it('renders the transport-failure copy when the request rejects', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new Error('network down'))),
    );
    render(<Harness />);

    fireEvent.change(combobox(), { target: { value: 'ret' } });
    await settleDebounce();

    expect(screen.getByText(FETCH_FAILURE_MESSAGE)).toBeInTheDocument();
  });
});
