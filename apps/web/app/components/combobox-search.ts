'use client';

/*
 * Shared combobox search mechanics (task 12.3). Extracted verbatim from the
 * task-12.2 ChargeSearchInput so both ChargeSearchInput and JudgeSearchInput
 * consume ONE implementation of the debounce, minimum-length gate, monotonic
 * sequence guard, staged commit-on-select, keyboard handling, and ARIA id
 * wiring. The rendering (which suggestion fields to show, placeholder, copy)
 * stays in each consumer, so ChargeSearchInput's output is byte-identical.
 *
 * State model (unchanged from 12.2):
 *   - The committed selection lives in the PARENT and is passed in as
 *     `committed`; the hook reports changes via `onCommitChange`. Selecting a
 *     suggestion commits it; editing the input after a commit clears it.
 *   - Query text, the suggestion list, request status, the active option, and
 *     the Escape-closed flag are local to the hook.
 *
 * Stale-response protection: the `search` function takes no AbortSignal (the
 * client lives in the out-of-scope app/lib module), so a monotonic sequence
 * ref tags each dispatch; a response applies only if its sequence is still the
 * latest. commit/clear and dropping below the minimum also bump the sequence,
 * so a late response can never reopen a closed list.
 *
 * Copy discipline (task 12.3): this module imports no copy modules and holds no
 * user-visible string literals. Error text is produced only from the
 * @pca/shared error constants below and rendered by the consuming components.
 */

import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';
import { PUBLIC_ERROR_MESSAGES, FETCH_FAILURE_MESSAGE, SEARCH_Q_MIN_LENGTH } from '@pca/shared';
import type { PublicApiResult } from '../lib/public-api-client';

// Debounce window in milliseconds (pinned decision 3). A component timing
// constant, not user-facing copy — no @pca/shared literal governs it.
const DEBOUNCE_MS = 250;

type RequestStatus = 'idle' | 'loading' | 'done' | 'error';

/**
 * The minimal identity shape every search result shares (charge and judge).
 * The hook needs only `displayName` (to detect a query reflecting a commit);
 * consumers read the other fields when rendering options.
 */
export interface ComboboxItem {
  id: string;
  slug: string;
  displayName: string;
  matchedAlias?: string;
}

interface UseComboboxSearchParams<T extends ComboboxItem> {
  /** The selection currently committed into parent form state, or null. */
  committed: T | null;
  /** Report a commit (item) or a clear (null) to the parent. */
  onCommitChange: (item: T | null) => void;
  /** Typed client call for this combobox (searchCharges / searchJudges). */
  search: (q: string) => Promise<PublicApiResult<{ results: T[] }>>;
}

export interface UseComboboxSearch<T extends ComboboxItem> {
  query: string;
  results: T[];
  activeIndex: number;
  errorMessage: string | null;
  showList: boolean;
  showLoading: boolean;
  showNoResult: boolean;
  showError: boolean;
  activeDescendant: string | undefined;
  listboxId: string;
  statusId: string;
  instructionsId: string;
  optionId: (index: number) => string;
  handleChange: (value: string) => void;
  handleKeyDown: (event: KeyboardEvent<HTMLInputElement>) => void;
  commit: (item: T) => void;
}

export function useComboboxSearch<T extends ComboboxItem>({
  committed,
  onCommitChange,
  search,
}: UseComboboxSearchParams<T>): UseComboboxSearch<T> {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<T[]>([]);
  const [status, setStatus] = useState<RequestStatus>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [listClosed, setListClosed] = useState(false);

  // Latest-dispatch sequence: a resolved response applies only when it matches.
  const seqRef = useRef(0);

  // Collision-proof id base so a second combobox (12.3 judge) cannot clash.
  const uid = useId();
  const listboxId = `${uid}-listbox`;
  const statusId = `${uid}-status`;
  const instructionsId = `${uid}-instructions`;
  const optionId = (index: number) => `${uid}-option-${index}`;

  const trimmed = query.trim();
  // The query reflects the committed selection (just committed, or untouched):
  // suppress searching so committing does not immediately re-query its own name.
  const reflectsCommitted = committed !== null && query === committed.displayName;

  useEffect(() => {
    // Below the minimum or reflecting a commit: no request. The clearing for a
    // sub-minimum query happens in handleChange (an event handler), so the
    // effect body never calls setState synchronously.
    if (reflectsCommitted || trimmed.length < SEARCH_Q_MIN_LENGTH) {
      return;
    }

    const seq = (seqRef.current += 1);
    const timer = setTimeout(() => {
      setStatus('loading');
      void search(trimmed).then((result) => {
        // Discard a stale response that a newer dispatch has superseded.
        if (seq !== seqRef.current) {
          return;
        }
        if (result.ok) {
          setResults(result.data.results);
          setActiveIndex(-1);
          setListClosed(false);
          setErrorMessage(null);
          setStatus('done');
          return;
        }
        const message =
          result.error.kind === 'api_error'
            ? PUBLIC_ERROR_MESSAGES[result.error.code]
            : FETCH_FAILURE_MESSAGE;
        setResults([]);
        setActiveIndex(-1);
        setErrorMessage(message);
        setStatus('error');
      });
    }, DEBOUNCE_MS);

    return () => clearTimeout(timer);
  }, [trimmed, reflectsCommitted, search]);

  const showList = status !== 'error' && !listClosed && results.length > 0;
  const showLoading = status === 'loading' && !reflectsCommitted;
  const showNoResult =
    status === 'done' &&
    results.length === 0 &&
    trimmed.length >= SEARCH_Q_MIN_LENGTH &&
    !reflectsCommitted;
  const showError = status === 'error';
  const activeDescendant = showList && activeIndex >= 0 ? optionId(activeIndex) : undefined;

  function commit(item: T) {
    // Invalidate any in-flight request so a late response cannot reopen the list.
    seqRef.current += 1;
    onCommitChange(item);
    setQuery(item.displayName);
    setResults([]);
    setActiveIndex(-1);
    setListClosed(false);
    setStatus('idle');
    setErrorMessage(null);
  }

  function clearAll() {
    seqRef.current += 1;
    onCommitChange(null);
    setQuery('');
    setResults([]);
    setActiveIndex(-1);
    setListClosed(false);
    setStatus('idle');
    setErrorMessage(null);
  }

  function handleChange(value: string) {
    setQuery(value);
    setListClosed(false);
    // Any edit after a commit invalidates the committed selection.
    if (committed !== null) {
      onCommitChange(null);
    }
    if (value.trim().length < SEARCH_Q_MIN_LENGTH) {
      // Dropped below the minimum: invalidate any in-flight request and clear
      // suggestions/state here rather than in the effect body.
      seqRef.current += 1;
      setResults([]);
      setActiveIndex(-1);
      setStatus('idle');
      setErrorMessage(null);
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    switch (event.key) {
      case 'ArrowDown': {
        if (results.length === 0) {
          return;
        }
        event.preventDefault();
        if (listClosed) {
          setListClosed(false);
          setActiveIndex(0);
        } else {
          setActiveIndex((prev) => (prev + 1) % results.length);
        }
        return;
      }
      case 'ArrowUp': {
        if (results.length === 0) {
          return;
        }
        event.preventDefault();
        if (listClosed) {
          setListClosed(false);
          setActiveIndex(results.length - 1);
        } else {
          setActiveIndex((prev) => (prev <= 0 ? results.length - 1 : prev - 1));
        }
        return;
      }
      case 'Enter': {
        if (showList) {
          // Open list: Enter belongs to the list, never the form.
          event.preventDefault();
          const active = results[activeIndex];
          // Open with no active option commits nothing and does not submit.
          if (active) {
            commit(active);
          }
        }
        // List closed: let Enter fall through to submit the form.
        return;
      }
      case 'Escape': {
        event.preventDefault();
        if (showList) {
          // First Escape closes the open list.
          setListClosed(true);
          setActiveIndex(-1);
        } else {
          // Second Escape (list already closed) clears input and committed state.
          clearAll();
        }
        return;
      }
      case 'Tab': {
        // Tab closes the list but must not trap focus.
        setListClosed(true);
        setActiveIndex(-1);
        return;
      }
      default:
        return;
    }
  }

  return {
    query,
    results,
    activeIndex,
    errorMessage,
    showList,
    showLoading,
    showNoResult,
    showError,
    activeDescendant,
    listboxId,
    statusId,
    instructionsId,
    optionId,
    handleChange,
    handleKeyDown,
    commit,
  };
}
