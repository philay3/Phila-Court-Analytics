'use client';

/*
 * Charge autocomplete input (task 12.2; client-side since task STATIC-2b). A
 * WAI-ARIA combobox that debounces queries, renders suggestions in a listbox,
 * and COMMITS a selected charge into the parent form's state without
 * navigating. Navigation happens on form submit (see SearchForm), not here.
 *
 * Search no longer calls the API: the index file (`/data/search-index.json`,
 * written by the static build) is loaded once on first interaction and the
 * shared `matchCharges` reproduces the endpoint's ranking locally (pin 6).
 * The combobox mechanics — debounce, minimum-length gate, sequence guard,
 * staged commit, keyboard handling, ARIA id wiring — live in the shared
 * useComboboxSearch hook, consumed here and by JudgeSearchInput. This
 * component owns only the charge-specific rendering (statute + alias).
 */

import { matchCharges, type ChargeMatch } from '@pca/shared';
import type { PublicApiResult } from '../lib/public-api-client';
import { loadSearchIndex } from '../lib/static-data';
import { useComboboxSearch } from './combobox-search';
import { HOME_COPY } from './home-copy';
import { CHARGE_SEARCH_COPY } from './charge-search-copy';

/** The combobox's search: load the index once, then match locally. */
async function matchChargesFromIndex(
  q: string,
): Promise<PublicApiResult<{ results: ChargeMatch[] }>> {
  const index = await loadSearchIndex();
  if (!index.ok) {
    return index;
  }
  return { ok: true, data: { results: matchCharges(index.data, q) } };
}

interface ChargeSearchInputProps {
  /** Input element id — matches the label's htmlFor in SearchForm. */
  id: string;
  /** id of the help paragraph the input is described by. */
  describedById: string;
  /** The charge currently committed into form state, or null. */
  committedCharge: ChargeMatch | null;
  /** Report a commit (charge) or a clear (null) to the parent. */
  onCommitChange: (charge: ChargeMatch | null) => void;
}

export function ChargeSearchInput({
  id,
  describedById,
  committedCharge,
  onCommitChange,
}: ChargeSearchInputProps) {
  const {
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
  } = useComboboxSearch<ChargeMatch>({
    committed: committedCharge,
    onCommitChange,
    search: matchChargesFromIndex,
  });

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
        className="mt-3 min-h-11 w-full bg-card px-1 py-2 font-serif text-lg text-ink placeholder:text-muted"
      />

      <span id={instructionsId} className="sr-only">
        {CHARGE_SEARCH_COPY.listInstructions}
      </span>

      {showList && (
        <ul
          id={listboxId}
          role="listbox"
          className="absolute z-10 mt-1 w-full overflow-hidden border border-ink bg-card"
        >
          {results.map((charge, index) => (
            <li
              key={charge.slug}
              id={optionId(index)}
              role="option"
              aria-selected={index === activeIndex}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => commit(charge)}
              className={`min-h-11 cursor-pointer px-4 py-2.5 ${index === activeIndex ? 'bg-band' : ''}`}
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
