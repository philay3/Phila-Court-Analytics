/**
 * Judge-specific result view (task 13.3, pinned decisions 1, 2, 3, 5, 6). The
 * presentational success render: it accepts the typed `judge_specific` payload
 * and composes the 13.1 display components TWICE per distribution type — one
 * "Judge-specific result" section and one "Philadelphia-wide baseline" section
 * (pinned decision 1: NO merged side-by-side comparison component). No data
 * fetching lives here; the server component (page.tsx) fetches and branches.
 *
 * Four independent distribution slots (pinned decision 3): judge outcome, judge
 * sentencing, baseline outcome, baseline sentencing. Each renders through the
 * shared `DistributionSection` with its own sample size and thin-data state, and
 * each sentencing slot independently falls back to `SentencingUnavailableNotice`
 * when its `available === false` arm is present — a missing sentencing slot
 * never fails the page.
 *
 * Content order (pinned decision 6, DP-3 pinned DOM order) is DOM source
 * order, no CSS `order`. Leaf blocks carry `data-testid`s so the order is
 * asserted directly:
 *   summary → responsible-use → thin-data → judge slots → baseline slots →
 *   metadata aside.
 * The two section HEADINGS ("Judge-specific result", "Philadelphia-wide
 * baseline") wrap their two slots without their own `section-*` testid, so the
 * leaf order matches the pinned order one-for-one. At ≥900px the view is a
 * two-column grid (main column + sidebar, bglad §9.2 adapted; scope-major
 * structure untouched per structure override 3); below 900px it is the same
 * DOM in a single column, the aside last. The former `section-links` block
 * dissolved into the aside (remove-filter link as the aside action); the
 * last-refreshed line relocated there byte-identically. No aside sample sizes
 * on this view — they stay in the scope-section headers only (DP-3).
 *
 * Slot order WITHIN each scope is conditional on that scope's API
 * `sentencing.available` flag (task 33.2 pinned decisions 3–4): available →
 * sentencing above outcome; unavailable → outcome first with the callout in
 * the sentencing slot below. The page stays scope-major, each scope branches
 * independently (mixed combinations are expected), and the branch consumes
 * the API boolean only.
 *
 * Every count, percentage, sample size, date, and label renders through the
 * 11.4 formatters; the page computes no analytics.
 */
import { useId } from 'react';
import Link from 'next/link';
import type { JudgeSpecificResultSuccess, ResultDistributions } from '@pca/shared';
import { formatResultTypeLabel } from '../lib/formatters';
import { DateRangeLabel } from './DateRangeLabel';
import { ResponsibleUseNotice } from './ResponsibleUseNotice';
import { ThinDataCallout } from './ThinDataCallout';
import { DistributionSection } from './DistributionSection';
import { SentencingUnavailableNotice } from './SentencingUnavailableNotice';
import { ResultMetadataAside } from './ResultMetadataAside';
import { JUDGE_RESULT_COPY } from './judge-result-copy';
import { RESULT_DISPLAY_COPY } from './result-display-copy';

interface JudgeSpecificResultViewProps {
  data: JudgeSpecificResultSuccess;
}

const LINK_CLASS = 'text-accent hover:text-accent-hover hover:underline';

export function JudgeSpecificResultView({ data }: JudgeSpecificResultViewProps) {
  const { charge, judge, judgeSpecific, baseline, links } = data;
  const judgeHeadingId = useId();
  const baselineHeadingId = useId();

  // Page-level thin-data callout slot: a PURE OR over the API-provided
  // thin-data booleans of the four rendered distributions — no counts, sample
  // sizes, or thresholds are evaluated here. It SUPPLEMENTS the per-slot badges
  // that DistributionSection still renders inside each distribution.
  const showThinDataCallout = [
    judgeSpecific.outcomes.thinData,
    judgeSpecific.sentencing.available && judgeSpecific.sentencing.thinData,
    baseline.outcomes.thinData,
    baseline.sentencing.available && baseline.sentencing.thinData,
  ].some(Boolean);

  return (
    // section-counter-reset scopes the Roman-numeral markers the four
    // DistributionSection captions render via CSS counters (DP-2). The root is
    // a single column below 900px and the bglad §9.2 grid at desktop+ (same
    // frame as ChargeOnlyResultView); the two-column frame simply wraps the
    // existing scope-major structure (structure override 3).
    <div className="section-counter-reset flex flex-col gap-7 tablet:gap-8 desktop:grid desktop:grid-cols-[minmax(0,1fr)_var(--sidebar-width-compact)] desktop:items-start desktop:gap-x-8 wide:grid-cols-[minmax(0,1fr)_var(--sidebar-width)] wide:gap-x-10">
      <div className="flex min-w-0 flex-col gap-7 tablet:gap-8 desktop:gap-10">
        <section data-testid="section-summary" className="space-y-2">
          <h1>{charge.displayName}</h1>
          <p className="text-base font-semibold text-ink">{judge.displayName}</p>
          <p className="text-base font-semibold text-ink">
            {formatResultTypeLabel(data.resultType)}
          </p>
          <DateRangeLabel range={data.dateRange} />
          <p className="text-sm text-muted">{RESULT_DISPLAY_COPY.coverageNote}</p>
        </section>

        <div data-testid="section-responsible-use">
          <ResponsibleUseNotice />
        </div>

        {showThinDataCallout && (
          <div data-testid="section-thin-data">
            <ThinDataCallout thin={showThinDataCallout} />
          </div>
        )}

        <section aria-labelledby={judgeHeadingId} className="flex flex-col gap-6">
          <h2 id={judgeHeadingId} className="font-serif text-lg font-semibold text-ink">
            {JUDGE_RESULT_COPY.sectionJudgeSpecificHeading}
          </h2>
          <ScopeSlots
            scope={judgeSpecific}
            methodologyHref={links.methodology}
            outcomeTestId="section-judge-outcome"
            sentencingTestId="section-judge-sentencing"
          />
        </section>

        <section aria-labelledby={baselineHeadingId} className="flex flex-col gap-6">
          <h2 id={baselineHeadingId} className="font-serif text-lg font-semibold text-ink">
            {JUDGE_RESULT_COPY.sectionBaselineHeading}
          </h2>
          <ScopeSlots
            scope={baseline}
            methodologyHref={links.methodology}
            outcomeTestId="section-baseline-outcome"
            sentencingTestId="section-baseline-sentencing"
          />
        </section>
      </div>

      <ResultMetadataAside
        lastRefreshed={data.lastRefreshed}
        links={links}
        actions={
          <p>
            <Link href={`/charges/${charge.slug}`} className={LINK_CLASS}>
              {JUDGE_RESULT_COPY.removeFilterLinkText}
            </Link>
          </p>
        }
      />
    </div>
  );
}

interface ScopeSlotsProps {
  /** One scope's distributions (judge-specific or baseline). */
  scope: ResultDistributions;
  /** Methodology href for a sentencing-unavailable slot's link. */
  methodologyHref: string;
  outcomeTestId: string;
  sentencingTestId: string;
}

/**
 * The outcome + sentencing slots for a single scope. Both scopes reuse this so
 * the judge and baseline sections are structurally identical (pinned decision
 * 1). The sentencing slot renders the 13.1 distribution when available, else the
 * 13.2 sentencing-unavailable callout — independently of the other scope.
 * Slot order follows this scope's `sentencing.available` flag (task 33.2
 * pinned decision 4): sentencing leads when available, outcome leads on the
 * unavailable arm.
 */
function ScopeSlots({ scope, methodologyHref, outcomeTestId, sentencingTestId }: ScopeSlotsProps) {
  const outcomeSlot = (
    <div data-testid={outcomeTestId} className="overflow-x-auto">
      <DistributionSection
        kind="outcome"
        rows={scope.outcomes.rows}
        sampleSize={scope.outcomes.sampleSize}
        thinData={scope.outcomes.thinData}
      />
    </div>
  );
  const sentencingSlot = (
    <div data-testid={sentencingTestId} className="overflow-x-auto">
      {scope.sentencing.available ? (
        <DistributionSection
          kind="sentencing"
          rows={scope.sentencing.rows}
          sampleSize={scope.sentencing.sampleSize}
          thinData={scope.sentencing.thinData}
        />
      ) : (
        <SentencingUnavailableNotice methodologyHref={methodologyHref} />
      )}
    </div>
  );

  return scope.sentencing.available ? (
    <>
      {sentencingSlot}
      {outcomeSlot}
    </>
  ) : (
    <>
      {outcomeSlot}
      {sentencingSlot}
    </>
  );
}
