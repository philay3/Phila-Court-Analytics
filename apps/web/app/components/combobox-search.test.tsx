import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { useComboboxSearch, type ComboboxItem } from './combobox-search.js';
import type { PublicApiResult } from '../lib/public-api-client.js';

/*
 * Dedicated tests for the shared combobox mechanics (task 12.3). These exercise
 * the hook directly through a minimal generic harness — independent of the
 * charge/judge rendering — so the debounce, minimum-length gate, sequence
 * guard, staged commit, and keyboard handling are covered once at the source.
 */

const DEBOUNCE_MS = 250;

interface Item extends ComboboxItem {
  id: string;
  slug: string;
  displayName: string;
  matchedAlias?: string;
}

const ALPHA: Item = { id: 'a', slug: 'alpha', displayName: 'Alpha' };
const BETA: Item = { id: 'b', slug: 'beta', displayName: 'Beta' };

/** A minimal combobox that renders the hook's output for assertions. */
function Harness({
  search,
  onCommit,
}: {
  search: (q: string) => Promise<PublicApiResult<{ results: Item[] }>>;
  onCommit?: (item: Item | null) => void;
}) {
  const [committed, setCommitted] = useState<Item | null>(null);
  const cb = useComboboxSearch<Item>({
    committed,
    onCommitChange: (item) => {
      onCommit?.(item);
      setCommitted(item);
    },
    search,
  });
  return (
    <div>
      <input
        role="combobox"
        aria-expanded={cb.showList}
        aria-controls={cb.listboxId}
        aria-activedescendant={cb.activeDescendant}
        value={cb.query}
        onChange={(event) => cb.handleChange(event.target.value)}
        onKeyDown={cb.handleKeyDown}
      />
      {cb.showList && (
        <ul id={cb.listboxId} role="listbox">
          {cb.results.map((item, index) => (
            <li
              key={item.id}
              id={cb.optionId(index)}
              role="option"
              aria-selected={index === cb.activeIndex}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => cb.commit(item)}
            >
              {item.displayName}
            </li>
          ))}
        </ul>
      )}
      {cb.showLoading && <span>loading</span>}
      {cb.showNoResult && <span>no-result</span>}
      {cb.showError && cb.errorMessage !== null && <span>{cb.errorMessage}</span>}
    </div>
  );
}

function ok(results: Item[]): PublicApiResult<{ results: Item[] }> {
  return { ok: true, data: { results } };
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
  vi.restoreAllMocks();
});

describe('useComboboxSearch', () => {
  it('fires no request below SEARCH_Q_MIN_LENGTH (whitespace only)', async () => {
    const search = vi.fn(() => Promise.resolve(ok([])));
    render(<Harness search={search} />);

    fireEvent.change(combobox(), { target: { value: '   ' } });
    await settleDebounce();

    expect(search).not.toHaveBeenCalled();
  });

  it('debounces rapid typing into one request after 250 ms', async () => {
    const search = vi.fn(() => Promise.resolve(ok([ALPHA])));
    render(<Harness search={search} />);
    const input = combobox();

    fireEvent.change(input, { target: { value: 'a' } });
    fireEvent.change(input, { target: { value: 'al' } });
    fireEvent.change(input, { target: { value: 'alp' } });
    expect(search).not.toHaveBeenCalled();

    await settleDebounce();

    expect(search).toHaveBeenCalledTimes(1);
    expect(search).toHaveBeenLastCalledWith('alp');
  });

  it('never lets a stale response overwrite a newer query', async () => {
    const deferred: Array<(value: PublicApiResult<{ results: Item[] }>) => void> = [];
    const search = vi.fn(
      () => new Promise<PublicApiResult<{ results: Item[] }>>((resolve) => deferred.push(resolve)),
    );
    render(<Harness search={search} />);
    const input = combobox();

    fireEvent.change(input, { target: { value: 'a' } });
    await settleDebounce();
    fireEvent.change(input, { target: { value: 'ab' } });
    await settleDebounce();

    // Resolve the NEWER request first, then the older/stale one.
    await act(async () => {
      deferred[1]?.(ok([BETA]));
      await vi.advanceTimersByTimeAsync(0);
    });
    await act(async () => {
      deferred[0]?.(ok([ALPHA]));
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(screen.getByText(BETA.displayName)).toBeInTheDocument();
    expect(screen.queryByText(ALPHA.displayName)).not.toBeInTheDocument();
  });

  it('ArrowDown activates an option and Enter commits it', async () => {
    const onCommit = vi.fn();
    render(<Harness search={() => Promise.resolve(ok([ALPHA, BETA]))} onCommit={onCommit} />);
    const input = combobox();

    fireEvent.change(input, { target: { value: 'al' } });
    await settleDebounce();

    fireEvent.keyDown(input, { key: 'ArrowDown' });
    const firstOption = screen.getAllByRole('option')[0]!;
    expect(input.getAttribute('aria-activedescendant')).toBe(firstOption.id);

    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onCommit).toHaveBeenLastCalledWith(ALPHA);
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    expect(input.value).toBe(ALPHA.displayName);
  });

  it('closes on Escape and clears on a second Escape', async () => {
    render(<Harness search={() => Promise.resolve(ok([ALPHA]))} />);
    const input = combobox();

    fireEvent.change(input, { target: { value: 'al' } });
    await settleDebounce();
    expect(screen.getByRole('listbox')).toBeInTheDocument();

    fireEvent.keyDown(input, { key: 'Escape' });
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    expect(input.value).toBe('al');

    fireEvent.keyDown(input, { key: 'Escape' });
    expect(input.value).toBe('');
  });
});
