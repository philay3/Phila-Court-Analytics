'use client';

/*
 * Judge autocomplete input (task 12.3). A WAI-ARIA combobox that debounces
 * queries to GET /api/v1/public/judges/search (via the public API client),
 * renders suggestions in a listbox, and COMMITS a selected judge into the
 * parent form's state without navigating. Navigation happens on form submit
 * (see SearchForm), not here.
 *
 * The judge is OPTIONAL (pinned decision 5): the visible label carries the
 * "(optional)" wording (HOME_COPY.judgeLabel), this input never blocks or
 * invalidates submission, and its secondary py-2.5 styling matches the 12.1
 * layout. Mechanics are shared with ChargeSearchInput via useComboboxSearch;
 * this component renders only the judge-specific option (display name + alias,
 * no statute).
 */

import { type JudgeSearchResult } from '@pca/shared';
import { searchJudges } from '../lib/public-api-client';
import { useComboboxSearch } from './combobox-search';
import { HOME_COPY } from './home-copy';
import { JUDGE_SEARCH_COPY } from './judge-search-copy';

interface JudgeSearchInputProps {
  /** Input element id — matches the label's htmlFor in SearchForm. */
  id: string;
  /** id of the help paragraph the input is described by. */
  describedById: string;
  /** The judge currently committed into form state, or null. */
  committedJudge: JudgeSearchResult | null;
  /** Report a commit (judge) or a clear (null) to the parent. */
  onCommitChange: (judge: JudgeSearchResult | null) => void;
  /**
   * Presentational only (DP-2, pinned decision A3): standalone placements
   * (the judge-filter entry) keep a 1px ink border as the functional
   * boundary; inside the segmented search card the card's ink border is
   * the boundary and the input renders borderless (the default).
   */
  bordered?: boolean;
}

export function JudgeSearchInput({
  id,
  describedById,
  committedJudge,
  onCommitChange,
  bordered = false,
}: JudgeSearchInputProps) {
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
  } = useComboboxSearch<JudgeSearchResult>({
    committed: committedJudge,
    onCommitChange,
    search: searchJudges,
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
        placeholder={HOME_COPY.judgePlaceholder}
        value={query}
        onChange={(event) => handleChange(event.target.value)}
        onKeyDown={handleKeyDown}
        className={`mt-3 min-h-11 w-full bg-card py-2 font-serif text-lg text-ink placeholder:text-muted ${
          bordered ? 'border border-ink px-3' : 'px-1'
        }`}
      />

      <span id={instructionsId} className="sr-only">
        {JUDGE_SEARCH_COPY.listInstructions}
      </span>

      {showList && (
        <ul
          id={listboxId}
          role="listbox"
          className="absolute z-10 mt-1 w-full overflow-hidden border border-ink bg-card"
        >
          {results.map((judge, index) => (
            <li
              key={judge.id}
              id={optionId(index)}
              role="option"
              aria-selected={index === activeIndex}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => commit(judge)}
              className={`cursor-pointer px-4 py-2.5 ${index === activeIndex ? 'bg-canvas' : ''}`}
            >
              <span className="block text-base text-ink">{judge.displayName}</span>
              {judge.matchedAlias !== undefined && (
                <span className="block text-sm text-muted">
                  {JUDGE_SEARCH_COPY.matchedAliasPrefix}
                  {judge.matchedAlias}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      <div id={statusId} role="status" aria-live="polite" className="mt-2 text-sm text-muted">
        {showLoading && <span>{JUDGE_SEARCH_COPY.loading}</span>}
        {showNoResult && <span>{JUDGE_SEARCH_COPY.noResult}</span>}
        {showError && errorMessage !== null && <span>{errorMessage}</span>}
      </div>
    </div>
  );
}
