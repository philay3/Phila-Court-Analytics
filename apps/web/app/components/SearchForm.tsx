'use client';

/*
 * Homepage search surface. Task 12.1 shipped the layout; 12.2 added the
 * interactive charge path; task 12.3 adds the optional judge path and completes
 * the submission routing:
 *   - committedCharge / committedJudge: the staged selections (WAI-ARIA
 *     comboboxes in <ChargeSearchInput> / <JudgeSearchInput>). Selecting a
 *     suggestion COMMITS it; it does not navigate. Editing an input clears that
 *     input's commit.
 *   - submit (single handler, pinned decision 3):
 *       · no charge, no judge      → no navigation; charge hint shown
 *       · charge, no judge         → /charges/[chargeSlug]
 *       · charge + judge           → /charges/[chargeSlug]/judge/[judgeSlug]
 *       · judge, no charge         → no navigation; charge hint shown; the
 *                                    judge commit is preserved (not cleared)
 *     Free-text submission is impossible by construction (no committed charge,
 *     no push). The judge input never blocks or invalidates submission.
 */

import { useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import type { ChargeSearchResult, JudgeSearchResult } from '@pca/shared';
import { HOME_COPY } from './home-copy';
import { CHARGE_SEARCH_COPY } from './charge-search-copy';
import { ChargeSearchInput } from './ChargeSearchInput';
import { JudgeSearchInput } from './JudgeSearchInput';

export function SearchForm() {
  const router = useRouter();
  const [committedCharge, setCommittedCharge] = useState<ChargeSearchResult | null>(null);
  const [committedJudge, setCommittedJudge] = useState<JudgeSearchResult | null>(null);
  const [showHint, setShowHint] = useState(false);

  function handleChargeCommitChange(charge: ChargeSearchResult | null) {
    setCommittedCharge(charge);
    if (charge !== null) {
      setShowHint(false);
    }
  }

  function handleJudgeCommitChange(judge: JudgeSearchResult | null) {
    // The judge is optional and never affects the hint or blocks submission;
    // it is simply staged (or cleared on edit) for the submit handler to read.
    setCommittedJudge(judge);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (committedCharge !== null) {
      setShowHint(false);
      if (committedJudge !== null) {
        router.push(`/charges/${committedCharge.slug}/judge/${committedJudge.slug}`);
        return;
      }
      router.push(`/charges/${committedCharge.slug}`);
      return;
    }
    // No committed charge: never navigate; prompt choosing a charge suggestion.
    // Any committed judge is preserved (committedJudge is left untouched).
    setShowHint(true);
  }

  return (
    <section aria-labelledby="search-heading" className="mt-8">
      <h2 id="search-heading" className="sr-only">
        {HOME_COPY.searchHeading}
      </h2>

      <form noValidate onSubmit={handleSubmit} className="flex flex-col gap-4">
        {/* Civic Atlas segmented search card (task DP-2): one 2px ink card,
            stacked on mobile, three-column grid on md+, 1px tan internal
            separators. Labels are the frozen HOME_COPY strings, CSS-cased
            into caps micro-headers. Region order and all ARIA wiring are
            unchanged from the 12.x layout. */}
        <div className="border-2 border-ink bg-card md:grid md:grid-cols-[1fr_18rem_11rem]">
          {/* Charge region — visually PRIMARY */}
          <div className="border-b border-rule p-5 md:border-r md:border-b-0">
            <label
              htmlFor="charge-search"
              className="block text-xs font-semibold tracking-[.12em] text-ink uppercase"
            >
              {HOME_COPY.chargeLabel}
            </label>
            <p id="charge-search-help" className="mt-1 text-sm text-muted">
              {HOME_COPY.chargeHelp}
            </p>
            {/* Task 12.2: the disabled 12.1 placeholder is replaced by the charge
                combobox. The id and aria-describedby wiring are preserved. */}
            <ChargeSearchInput
              id="charge-search"
              describedById="charge-search-help"
              committedCharge={committedCharge}
              onCommitChange={handleChargeCommitChange}
            />
          </div>

          {/* Judge region — visually SECONDARY, optional */}
          <div className="border-b border-rule p-5 md:border-r md:border-b-0">
            <label
              htmlFor="judge-search"
              className="block text-xs font-semibold tracking-[.12em] text-faint uppercase"
            >
              {HOME_COPY.judgeLabel}
            </label>
            <p id="judge-search-help" className="mt-1 text-sm text-muted">
              {HOME_COPY.judgeHelp}
            </p>
            {/* Task 12.3: the disabled 12.1 placeholder is replaced by the judge
                combobox. The id and aria-describedby wiring are preserved. */}
            <JudgeSearchInput
              id="judge-search"
              describedById="judge-search-help"
              committedJudge={committedJudge}
              onCommitChange={handleJudgeCommitChange}
            />
          </div>

          <div className="flex items-stretch p-4 md:items-end">
            <button
              type="submit"
              className="min-h-11 w-full bg-ink px-5 py-3 text-sm font-semibold tracking-[.08em] text-card uppercase hover:bg-ink-hover"
            >
              {CHARGE_SEARCH_COPY.submitButton}
            </button>
          </div>
        </div>

        {showHint && (
          <p role="alert" className="text-sm text-muted">
            {CHARGE_SEARCH_COPY.submitHint}
          </p>
        )}
      </form>
    </section>
  );
}
