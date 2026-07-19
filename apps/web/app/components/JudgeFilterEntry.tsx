'use client';

/**
 * Judge-filter entry point (task 13.2, pinned decision 5). Reuses the 12.3
 * `JudgeSearchInput` combobox in an "add a judge" section on the charge-only
 * result page. Selecting a judge COMMITS it (the combobox never navigates on
 * its own) and this component then routes to the judge-specific result page:
 * `/charges/[chargeSlug]/judge/[judgeSlug]` (that page lands in 13.3 — shipping
 * the route target now is intended).
 *
 * The section is purely additive: it never blocks or gates the charge-only
 * content, and its help copy is the sanctioned shared JUDGE_FILTER_HELP_MESSAGE
 * (DP-5), rendered byte-identically with the homepage disclosure.
 */
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { JUDGE_FILTER_HELP_MESSAGE } from '@pca/shared';
import type { JudgeSearchResult } from '@pca/shared';
import { JudgeSearchInput } from './JudgeSearchInput';
import { CHARGE_RESULT_COPY } from './charge-result-copy';

interface JudgeFilterEntryProps {
  /** The charge slug this result page is for; the routing target base. */
  chargeSlug: string;
}

export function JudgeFilterEntry({ chargeSlug }: JudgeFilterEntryProps) {
  const router = useRouter();
  const [committedJudge, setCommittedJudge] = useState<JudgeSearchResult | null>(null);

  function handleCommitChange(judge: JudgeSearchResult | null) {
    setCommittedJudge(judge);
    // A selection (non-null commit) routes to the judge-specific result; an
    // edit that clears the commit (null) simply stages nothing and never routes.
    if (judge !== null) {
      router.push(`/charges/${chargeSlug}/judge/${judge.slug}`);
    }
  }

  return (
    <section
      aria-labelledby="judge-filter-heading"
      data-testid="section-judge-filter"
      className="border border-rule bg-card p-4"
    >
      <h2 id="judge-filter-heading" className="font-serif text-base font-semibold text-ink">
        {CHARGE_RESULT_COPY.judgeFilterHeading}
      </h2>
      <label
        htmlFor="judge-filter-input"
        className="mt-2 block text-xs font-semibold tracking-[.12em] text-faint uppercase"
      >
        {CHARGE_RESULT_COPY.judgeFilterLabel}
      </label>
      <p id="judge-filter-help" className="mt-1 text-sm text-muted">
        {JUDGE_FILTER_HELP_MESSAGE}
      </p>
      <JudgeSearchInput
        id="judge-filter-input"
        describedById="judge-filter-help"
        committedJudge={committedJudge}
        onCommitChange={handleCommitChange}
        bordered
      />
    </section>
  );
}
