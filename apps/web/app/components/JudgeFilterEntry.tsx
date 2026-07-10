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
 * content, and its help copy states that judge-specific data is not available
 * for every charge/judge pair (guard-passing language in charge-result-copy).
 */
import { useState } from 'react';
import { useRouter } from 'next/navigation';
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
      className="rounded-lg border border-line p-4"
    >
      <h2 id="judge-filter-heading" className="text-base font-medium text-ink">
        {CHARGE_RESULT_COPY.judgeFilterHeading}
      </h2>
      <label htmlFor="judge-filter-input" className="mt-2 block text-sm font-medium text-ink">
        {CHARGE_RESULT_COPY.judgeFilterLabel}
      </label>
      <p id="judge-filter-help" className="mt-1 text-sm text-muted">
        {CHARGE_RESULT_COPY.judgeFilterHelp}
      </p>
      <JudgeSearchInput
        id="judge-filter-input"
        describedById="judge-filter-help"
        committedJudge={committedJudge}
        onCommitChange={handleCommitChange}
      />
    </section>
  );
}
