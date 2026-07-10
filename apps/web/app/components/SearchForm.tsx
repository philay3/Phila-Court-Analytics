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

      <form noValidate onSubmit={handleSubmit} className="flex flex-col gap-6">
        {/* Charge region — visually PRIMARY */}
        <div className="rounded-lg border border-line bg-surface p-5">
          <label htmlFor="charge-search" className="block text-lg font-semibold text-ink">
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
        <div className="rounded-lg border border-line p-4">
          <label htmlFor="judge-search" className="block text-base font-medium text-ink">
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

        {showHint && (
          <p role="alert" className="text-sm text-muted">
            {CHARGE_SEARCH_COPY.submitHint}
          </p>
        )}

        <button
          type="submit"
          className="rounded-md bg-accent px-5 py-3 text-base font-semibold text-canvas hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          {CHARGE_SEARCH_COPY.submitButton}
        </button>
      </form>
    </section>
  );
}
