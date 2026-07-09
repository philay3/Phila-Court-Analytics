'use client';

/*
 * Homepage search surface. Task 12.1 shipped this as a layout-only server
 * component; task 12.2 makes it a client component that owns the interactive
 * charge path:
 *   - committedCharge: the staged selection (WAI-ARIA combobox in
 *     <ChargeSearchInput>). Selecting a suggestion COMMITS a charge; it does
 *     not navigate. Editing the input clears the commit.
 *   - submit: with a committed charge, navigate to /charges/[slug] via the
 *     Next router (both the Enter path and the visible submit button run this
 *     one handler). With no committed charge, do not navigate — show the hint.
 *     Free-text submission is impossible by construction (no charge, no push).
 *
 * The judge region remains the DISABLED presentational placeholder from 12.1,
 * visually unchanged, with its `MOUNT: task 12.3` point preserved. Task 12.3
 * extends this same submit for the judge path.
 */

import { useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import type { ChargeSearchResult } from '@pca/shared';
import { HOME_COPY } from './home-copy';
import { CHARGE_SEARCH_COPY } from './charge-search-copy';
import { ChargeSearchInput } from './ChargeSearchInput';

export function SearchForm() {
  const router = useRouter();
  const [committedCharge, setCommittedCharge] = useState<ChargeSearchResult | null>(null);
  const [showHint, setShowHint] = useState(false);

  function handleCommitChange(charge: ChargeSearchResult | null) {
    setCommittedCharge(charge);
    if (charge !== null) {
      setShowHint(false);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (committedCharge !== null) {
      setShowHint(false);
      router.push(`/charges/${committedCharge.slug}`);
      return;
    }
    // No committed charge: never navigate; prompt choosing a suggestion.
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
            onCommitChange={handleCommitChange}
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
          {/* MOUNT: task 12.3 replaces this disabled placeholder with
              <JudgeSearchInput id="judge-search" />. Keep the id and the
              aria-describedby wiring. */}
          <input
            id="judge-search"
            type="text"
            disabled
            placeholder={HOME_COPY.judgePlaceholder}
            aria-describedby="judge-search-help"
            className="mt-3 w-full rounded-md border border-line bg-canvas px-4 py-2.5 text-base text-ink placeholder:text-muted disabled:cursor-not-allowed disabled:opacity-70"
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
