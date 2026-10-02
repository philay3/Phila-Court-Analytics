'use client';

/**
 * Judge-filter entry point (task 13.2, pinned decision 5; in-page since task
 * STATIC-2b). Reuses the 12.3 `JudgeSearchInput` combobox in an "add a judge"
 * section on the charge result page, scoped to the judges that have results
 * for THIS charge (pin 4 — the list is baked into the page at build time, so
 * there is no dead end to select). Selecting a judge COMMITS it (the combobox
 * never navigates on its own) and this component then updates the address to
 * `/charges/[chargeSlug]?judge=[judgeSlug]` with `history.pushState` — no
 * navigation; the charge page's shell reads the param and renders the
 * judge-specific result in place (pin 3).
 *
 * The section is purely additive: it never blocks or gates the charge-only
 * content, and its help copy is the sanctioned shared JUDGE_FILTER_HELP_MESSAGE
 * (DP-5), rendered byte-identically with the homepage disclosure.
 */
import { useState } from 'react';
import { JUDGE_FILTER_HELP_MESSAGE } from '@pca/shared';
import type { JudgeMatch, SearchIndexJudge } from '@pca/shared';
import { JudgeSearchInput } from './JudgeSearchInput';
import { CHARGE_RESULT_COPY } from './charge-result-copy';

interface JudgeFilterEntryProps {
  /** The charge slug this result page is for; the address base. */
  chargeSlug: string;
  /** Judges with judge-specific results for this charge (baked at build time). */
  judges: readonly SearchIndexJudge[];
}

export function JudgeFilterEntry({ chargeSlug, judges }: JudgeFilterEntryProps) {
  const [committedJudge, setCommittedJudge] = useState<JudgeMatch | null>(null);

  function handleCommitChange(judge: JudgeMatch | null) {
    setCommittedJudge(judge);
    // A selection (non-null commit) selects the judge in place; an edit that
    // clears the commit (null) simply stages nothing.
    if (judge !== null) {
      window.history.pushState(
        null,
        '',
        `/charges/${chargeSlug}?judge=${encodeURIComponent(judge.slug)}`,
      );
      try {
        window.scrollTo({ top: 0 });
      } catch {
        // Environments without layout (jsdom) have no scrolling to do.
      }
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
        judges={judges}
        committedJudge={committedJudge}
        onCommitChange={handleCommitChange}
        bordered
      />
    </section>
  );
}
