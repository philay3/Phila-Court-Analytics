'use client';

/*
 * Judge autocomplete input (task 12.3; client-side and scoped since task
 * STATIC-2b). A WAI-ARIA combobox that debounces queries, renders suggestions
 * in a listbox, and COMMITS a selected judge into the parent form's state
 * without navigating. Navigation happens on form submit (see SearchForm) or,
 * on a charge page, as a `?judge=` update (see JudgeFilterEntry).
 *
 * The parent supplies the judges this input may offer (pin 4: only judges
 * with results for the chosen charge — never a dead end); `null` means no
 * charge is chosen yet and the input is disabled. Matching runs locally with
 * the shared `matchJudges`, reproducing the retired endpoint's ranking (pin 6).
 * Mechanics are shared with ChargeSearchInput via useComboboxSearch; this
 * component renders only the judge-specific option (display name + alias).
 */

import { useMemo } from 'react';
import { matchJudges, type JudgeMatch, type SearchIndexJudge } from '@pca/shared';
import type { PublicApiResult } from '../lib/public-api-client';
import { useComboboxSearch } from './combobox-search';
import { HOME_COPY } from './home-copy';
import { JUDGE_SEARCH_COPY } from './judge-search-copy';

interface JudgeSearchInputProps {
  /** Input element id — matches the label's htmlFor in SearchForm. */
  id: string;
  /** id of the help paragraph the input is described by. */
  describedById: string;
  /** The judges this input may offer; null = no charge chosen yet (disabled). */
  judges: readonly SearchIndexJudge[] | null;
  /** The judge currently committed into form state, or null. */
  committedJudge: JudgeMatch | null;
  /** Report a commit (judge) or a clear (null) to the parent. */
  onCommitChange: (judge: JudgeMatch | null) => void;
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
  judges,
  committedJudge,
  onCommitChange,
  bordered = false,
}: JudgeSearchInputProps) {
  const search = useMemo(
    () =>
      async (q: string): Promise<PublicApiResult<{ results: JudgeMatch[] }>> => ({
        ok: true,
        data: { results: matchJudges({ judges: judges ?? [] }, q) },
      }),
    [judges],
  );
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
  } = useComboboxSearch<JudgeMatch>({
    committed: committedJudge,
    onCommitChange,
    search,
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
        disabled={judges === null}
        onChange={(event) => handleChange(event.target.value)}
        onKeyDown={handleKeyDown}
        className={`mt-3 min-h-11 w-full bg-card py-2 font-serif text-lg text-ink placeholder:text-muted disabled:text-faint ${
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
              key={judge.slug}
              id={optionId(index)}
              role="option"
              aria-selected={index === activeIndex}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => commit(judge)}
              className={`min-h-11 cursor-pointer px-4 py-2.5 ${index === activeIndex ? 'bg-band' : ''}`}
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
