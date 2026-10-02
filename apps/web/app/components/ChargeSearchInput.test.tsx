import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import {
  FETCH_FAILURE_MESSAGE,
  PUBLIC_ERROR_MESSAGES,
  SEARCH_INDEX_DATA_PATH,
  type ChargeMatch,
  type SearchIndexAvailable,
} from '@pca/shared';
import { ChargeSearchInput } from './ChargeSearchInput.js';
import { CHARGE_SEARCH_COPY } from './charge-search-copy.js';
import { resetStaticDataCache } from '../lib/static-data.js';

const DEBOUNCE_MS = 250;

// Invented index entries (never real roster data). "Beta Offense" matches the
// query "charge" only through its alias, so the alias line renders for it.
const INDEX: SearchIndexAvailable = {
  available: true,
  aggregateRunId: '11111111-1111-4111-8111-111111111111',
  taxonomyVersion: '1.0.0',
  lastRefreshed: '2026-01-01T00:00:00.000Z',
  charges: [
    { slug: 'alpha-charge', displayName: 'Alpha Charge', statuteCode: '18 § 1111', aliases: [] },
    { slug: 'beta-offense', displayName: 'Beta Offense', aliases: ['b-charge'] },
  ],
  judges: [],
  pairs: [],
};
const ALPHA_MATCH: ChargeMatch = {
  slug: 'alpha-charge',
  displayName: 'Alpha Charge',
  statuteCode: '18 § 1111',
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

/** A parent harness mirroring SearchForm's committed-charge ownership. */
function Harness({ onCommit }: { onCommit?: (charge: ChargeMatch | null) => void }) {
  const [committed, setCommitted] = useState<ChargeMatch | null>(null);
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
  resetStaticDataCache();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  resetStaticDataCache();
});

describe('ChargeSearchInput (client-side over the index file)', () => {
  it('fires no request when the trimmed query is below SEARCH_Q_MIN_LENGTH', async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(INDEX)));
    vi.stubGlobal('fetch', fetchMock);
    render(<Harness />);

    fireEvent.change(combobox(), { target: { value: '   ' } });
    await settleDebounce();

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('loads the index file exactly once, after the 250 ms debounce, and never the API', async () => {
    const fetchMock = vi.fn<(url: string | URL) => Promise<Response>>(() =>
      Promise.resolve(jsonResponse(INDEX)),
    );
    vi.stubGlobal('fetch', fetchMock);
    render(<Harness />);

    const input = combobox();
    fireEvent.change(input, { target: { value: 'a' } });
    fireEvent.change(input, { target: { value: 'al' } });
    fireEvent.change(input, { target: { value: 'alp' } });
    expect(fetchMock).not.toHaveBeenCalled(); // still within the debounce window

    await settleDebounce();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe(SEARCH_INDEX_DATA_PATH);

    // Further queries match locally: no second request.
    fireEvent.change(input, { target: { value: 'beta' } });
    await settleDebounce();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.getByText('Beta Offense')).toBeInTheDocument();
  });

  it('never lets an earlier query overwrite a newer one when the index arrives late', async () => {
    const deferred: Array<(response: Response) => void> = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(() => new Promise<Response>((resolve) => deferred.push(resolve))),
    );
    render(<Harness />);
    const input = combobox();

    fireEvent.change(input, { target: { value: 'alpha' } });
    await settleDebounce(); // search #1 awaits the index
    fireEvent.change(input, { target: { value: 'beta' } });
    await settleDebounce(); // search #2 awaits the same index promise

    await act(async () => {
      deferred[0]?.(jsonResponse(INDEX));
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(screen.getByText('Beta Offense')).toBeInTheDocument();
    expect(screen.queryByText('Alpha Charge')).not.toBeInTheDocument();
  });

  it('renders the loading state while the index is in flight', async () => {
    const deferred: Array<(response: Response) => void> = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(() => new Promise<Response>((resolve) => deferred.push(resolve))),
    );
    render(<Harness />);

    fireEvent.change(combobox(), { target: { value: 'alp' } });
    await settleDebounce();

    expect(screen.getByText(CHARGE_SEARCH_COPY.loading)).toBeInTheDocument();

    await act(async () => {
      deferred[0]?.(jsonResponse(INDEX));
      await vi.advanceTimersByTimeAsync(0);
    });
  });

  it('renders display name, statute, and matched alias; a mouse click commits and closes', async () => {
    const onCommit = vi.fn();
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(jsonResponse(INDEX))),
    );
    render(<Harness onCommit={onCommit} />);

    fireEvent.change(combobox(), { target: { value: 'charge' } });
    await settleDebounce();

    expect(screen.getByText('Alpha Charge')).toBeInTheDocument();
    expect(screen.getByText('18 § 1111')).toBeInTheDocument();
    expect(
      screen.getByText(`${CHARGE_SEARCH_COPY.matchedAliasPrefix}b-charge`),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByText('Alpha Charge'));

    expect(onCommit).toHaveBeenLastCalledWith(ALPHA_MATCH);
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    expect(combobox().value).toBe('Alpha Charge');
  });

  it('tracks ARIA combobox/listbox state and aria-activedescendant', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(jsonResponse(INDEX))),
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
      vi.fn(() => Promise.resolve(jsonResponse(INDEX))),
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
      vi.fn(() => Promise.resolve(jsonResponse(INDEX))),
    );
    render(<Harness onCommit={onCommit} />);
    const input = combobox();

    fireEvent.change(input, { target: { value: 'alpha' } });
    await settleDebounce();
    fireEvent.click(screen.getByText('Alpha Charge'));
    expect(onCommit).toHaveBeenLastCalledWith(ALPHA_MATCH);

    fireEvent.change(input, { target: { value: 'Alpha Charge extra' } });
    expect(onCommit).toHaveBeenLastCalledWith(null);
  });

  it('renders the no-result copy for a valid query with zero suggestions', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(jsonResponse(INDEX))),
    );
    render(<Harness />);

    fireEvent.change(combobox(), { target: { value: 'zzzzz' } });
    await settleDebounce();

    expect(screen.getByText(CHARGE_SEARCH_COPY.noResult)).toBeInTheDocument();
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  });

  it('renders the shared error-message copy when the index file answers an error envelope', async () => {
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

    fireEvent.change(combobox(), { target: { value: 'alp' } });
    await settleDebounce();

    expect(screen.getByText(PUBLIC_ERROR_MESSAGES.RATE_LIMITED)).toBeInTheDocument();
  });

  it('renders the transport-failure copy when the index request rejects, then retries on the next query', async () => {
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(() => Promise.reject(new Error('network down')))
      .mockImplementation(() => Promise.resolve(jsonResponse(INDEX)));
    vi.stubGlobal('fetch', fetchMock);
    render(<Harness />);

    fireEvent.change(combobox(), { target: { value: 'alp' } });
    await settleDebounce();
    expect(screen.getByText(FETCH_FAILURE_MESSAGE)).toBeInTheDocument();

    fireEvent.change(combobox(), { target: { value: 'alph' } });
    await settleDebounce();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(screen.getByText('Alpha Charge')).toBeInTheDocument();
  });
});
