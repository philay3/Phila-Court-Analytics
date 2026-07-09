'use client';

/*
 * Charge autocomplete input (task 12.2). A WAI-ARIA combobox that debounces
 * queries to GET /api/v1/public/charges/search (via the public API client),
 * renders suggestions in a listbox, and COMMITS a selected charge into the
 * parent form's state without navigating. Navigation happens on form submit
 * (see SearchForm), not here.
 *
 * State model:
 *   - The committed charge lives in the PARENT (SearchForm) because both the
 *     submit action and the submit hint depend on it. This component receives
 *     it as a prop and reports changes via onCommitChange: selecting a
 *     suggestion commits a charge; editing the input after a commit clears it
 *     (onCommitChange(null)).
 *   - Query text, the suggestion list, request status, the active option, and
 *     the Escape-closed flag are local.
 *
 * Stale-response protection: searchCharges takes no AbortSignal and the client
 * lives in the out-of-scope app/lib module, so aborting is not available. A
 * monotonic sequence ref tags each dispatch; a response is applied only if its
 * sequence is still the latest, so an earlier request can never overwrite a
 * newer query's results (or error).
 */

import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';
import {
  PUBLIC_ERROR_MESSAGES,
  FETCH_FAILURE_MESSAGE,
  SEARCH_Q_MIN_LENGTH,
  type ChargeSearchResult,
} from '@pca/shared';
import { searchCharges } from '../lib/public-api-client';
import { HOME_COPY } from './home-copy';
import { CHARGE_SEARCH_COPY } from './charge-search-copy';

// Debounce window in milliseconds (pinned decision 3). A component timing
// constant, not user-facing copy — no @pca/shared literal governs it.
const DEBOUNCE_MS = 250;

type RequestStatus = 'idle' | 'loading' | 'done' | 'error';

interface ChargeSearchInputProps {
  /** Input element id — matches the label's htmlFor in SearchForm. */
  id: string;
  /** id of the help paragraph the input is described by. */
  describedById: string;
  /** The charge currently committed into form state, or null. */
  committedCharge: ChargeSearchResult | null;
  /** Report a commit (charge) or a clear (null) to the parent. */
  onCommitChange: (charge: ChargeSearchResult | null) => void;
}

export function ChargeSearchInput({
  id,
  describedById,
  committedCharge,
  onCommitChange,
}: ChargeSearchInputProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<ChargeSearchResult[]>([]);
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
  const reflectsCommitted = committedCharge !== null && query === committedCharge.displayName;

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
      void searchCharges(trimmed).then((result) => {
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
  }, [trimmed, reflectsCommitted]);

  const showList = status !== 'error' && !listClosed && results.length > 0;
  const showLoading = status === 'loading' && !reflectsCommitted;
  const showNoResult =
    status === 'done' &&
    results.length === 0 &&
    trimmed.length >= SEARCH_Q_MIN_LENGTH &&
    !reflectsCommitted;
  const showError = status === 'error';
  const activeDescendant = showList && activeIndex >= 0 ? optionId(activeIndex) : undefined;

  function commit(charge: ChargeSearchResult) {
    // Invalidate any in-flight request so a late response cannot reopen the list.
    seqRef.current += 1;
    onCommitChange(charge);
    setQuery(charge.displayName);
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
    if (committedCharge !== null) {
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

  return (
    <div className="relative">
      <input
        id={id}
        type="text"
        role="combobox"
        autoComplete="off"
        aria-autocomplete="list"
        aria-expanded={showList}
        aria-controls={listboxId}
        aria-activedescendant={activeDescendant}
        aria-describedby={`${describedById} ${instructionsId}`}
        placeholder={HOME_COPY.chargePlaceholder}
        value={query}
        onChange={(event) => handleChange(event.target.value)}
        onKeyDown={handleKeyDown}
        className="mt-3 w-full rounded-md border border-line bg-canvas px-4 py-3 text-base text-ink placeholder:text-muted"
      />

      <span id={instructionsId} className="sr-only">
        {CHARGE_SEARCH_COPY.listInstructions}
      </span>

      {showList && (
        <ul
          id={listboxId}
          role="listbox"
          className="absolute z-10 mt-1 w-full overflow-hidden rounded-md border border-line bg-surface shadow-lg"
        >
          {results.map((charge, index) => (
            <li
              key={charge.id}
              id={optionId(index)}
              role="option"
              aria-selected={index === activeIndex}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => commit(charge)}
              className={`cursor-pointer px-4 py-2.5 ${index === activeIndex ? 'bg-canvas' : ''}`}
            >
              <span className="block text-base text-ink">{charge.displayName}</span>
              {charge.statuteCode !== undefined && (
                <span className="block text-sm text-muted">{charge.statuteCode}</span>
              )}
              {charge.matchedAlias !== undefined && (
                <span className="block text-sm text-muted">
                  {CHARGE_SEARCH_COPY.matchedAliasPrefix}
                  {charge.matchedAlias}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      <div id={statusId} role="status" aria-live="polite" className="mt-2 text-sm text-muted">
        {showLoading && <span>{CHARGE_SEARCH_COPY.loading}</span>}
        {showNoResult && <span>{CHARGE_SEARCH_COPY.noResult}</span>}
        {showError && errorMessage !== null && <span>{errorMessage}</span>}
      </div>
    </div>
  );
}
