/**
 * Charge-only result view (task 13.2, pinned decisions 1, 4, 6, 7). The
 * presentational success render: it accepts the typed `charge_only` payload and
 * composes the 13.1 display components. No data fetching lives here — the server
 * component (page.tsx) fetches and branches; this component is fully testable
 * under jsdom.
 *
 * Content order (pinned decision 6, DP-3 pinned DOM order) is achieved by DOM
 * source order — no CSS `order`. Each top-level block carries a
 * `data-testid="section-*"` so the order is asserted directly:
 *   result summary → responsible-use notice → thin-data callout (when either
 *   distribution is thin) → the two distributions → metadata aside.
 * At ≥900px the view is a two-column grid (main column + sidebar, bglad §9.2
 * adapted); below 900px it is the same DOM in a single column, the aside last.
 * The former `section-links` block and the judge-filter entry now live inside
 * the aside (DP-3); the last-refreshed line relocated there byte-identically,
 * leaving the summary with h1 → result-type → date range → coverage note
 * (honesty-apparatus overrides 1–2: responsible-use and coverage-note
 * positions are unchanged).
 *
 * Distribution order (task 35.3, pins 1–3) branches on the sentencing-index
 * display arm derived in `sentencing-index-display.ts`:
 *   - lead: the index section leads, the component-grain sentencing block
 *     renders below it under the distinct detail caption, outcome below that.
 *   - zero-sentenced: outcome leads; the ruling-4 fallback line (carrying the
 *     served conviction count) replaces the generic sentencing-unavailable
 *     notice in the sentencing slot.
 *   - absent: today's post-Phase-33 conditional order, structurally unchanged
 *     (33.2 pinned decision 4): sentencing leads when `sentencing.available`,
 *     else outcome leads with the notice below.
 * Every branch consumes API booleans/arrays only — no counts or thresholds
 * are evaluated here.
 *
 * Every count, percentage, sample size, date, and label renders through the
 * 11.4 formatters (pinned decision 7); the page computes no analytics.
 */
import { SENTENCING_DETAIL_CAPTION } from '@pca/shared';
import type { ChargeOnlyResultSuccess } from '@pca/shared';
import {
  formatRecordsLabel,
  formatResultTypeLabel,
  formatSentenceComponentsLabel,
  formatZeroSentencedFallback,
} from '../lib/formatters';
import { resolveChargeSentencingIndexDisplay } from '../lib/sentencing-index-display';
import { DateRangeLabel } from './DateRangeLabel';
import { ResponsibleUseNotice } from './ResponsibleUseNotice';
import { ThinDataCallout } from './ThinDataCallout';
import { DistributionSection } from './DistributionSection';
import { SentencingUnavailableNotice } from './SentencingUnavailableNotice';
import { JudgeDisclosure } from './JudgeDisclosure';
import { JudgeFilterEntry } from './JudgeFilterEntry';
import { ResultMetadataAside } from './ResultMetadataAside';
import { SampleSizeLabel } from './SampleSizeLabel';
import { SentencingIndexSection } from './SentencingIndexSection';
import { CHARGE_RESULT_COPY } from './charge-result-copy';
import { RESULT_DISPLAY_COPY } from './result-display-copy';

interface ChargeOnlyResultViewProps {
  data: ChargeOnlyResultSuccess;
}

export function ChargeOnlyResultView({ data }: ChargeOnlyResultViewProps) {
  const { charge, outcomes, sentencing, links } = data;
  const indexDisplay = resolveChargeSentencingIndexDisplay(data.sentencingIndex);
  // One page-level thin-data callout slot; each distribution also shows its own
  // precise thin-data badge inside its section. Pure OR over API booleans.
  const showThinDataCallout =
    outcomes.thinData ||
    (sentencing.available && sentencing.thinData) ||
    (data.sentencingIndex.available && data.sentencingIndex.summary.thinData);

  const outcomeBlock = (
    <div data-testid="section-outcome" className="overflow-x-auto">
      <DistributionSection
        kind="outcome"
        rows={outcomes.rows}
        sampleSize={outcomes.sampleSize}
        thinData={outcomes.thinData}
      />
    </div>
  );
  const sentencingBlock = (caption?: string) => (
    <div data-testid="section-sentencing" className="overflow-x-auto">
      {sentencing.available ? (
        <DistributionSection
          kind="sentencing"
          rows={sentencing.rows}
          sampleSize={sentencing.sampleSize}
          thinData={sentencing.thinData}
          caption={caption}
        />
      ) : (
        <SentencingUnavailableNotice methodologyHref={links.methodology} />
      )}
    </div>
  );

  // The three index arms (35.3 pins 1–3), exhaustively switched: a new arm
  // must add a case rather than fall through.
  const distributionBlocks = (() => {
    switch (indexDisplay.kind) {
      case 'lead':
        return (
          <>
            <div data-testid="section-sentencing-index" className="overflow-x-auto">
              <SentencingIndexSection
                summary={indexDisplay.index.summary}
                categories={indexDisplay.index.categories}
                grades={indexDisplay.index.grades}
              />
            </div>
            {sentencingBlock(SENTENCING_DETAIL_CAPTION)}
            {outcomeBlock}
          </>
        );
      case 'zero-sentenced':
        // Outcome-first; the ruling-4 fallback line (served conviction count)
        // replaces the generic notice in the sentencing slot (ruling Q4).
        return (
          <>
            {outcomeBlock}
            <div
              data-testid="section-sentencing-index"
              className="space-y-3 border-t-3 border-double border-ink pt-3"
            >
              <p className="text-sm text-muted">
                {formatZeroSentencedFallback(indexDisplay.index.summary.convictions)}
              </p>
            </div>
            {sentencing.available && sentencingBlock()}
          </>
        );
      case 'absent':
        // Today's post-Phase-33 page, structurally unchanged (pin 2).
        return sentencing.available ? (
          <>
            {sentencingBlock()}
            {outcomeBlock}
          </>
        ) : (
          <>
            {outcomeBlock}
            {sentencingBlock()}
          </>
        );
      default: {
        const exhaustive: never = indexDisplay;
        return exhaustive;
      }
    }
  })();

  return (
    // section-counter-reset scopes the Roman-numeral markers the two
    // DistributionSection captions render via CSS counters (DP-2). The root is
    // a single column below 900px and the bglad §9.2 grid at desktop+: main
    // column against a 288px sidebar (320px at wide), 32px column gap (40px at
    // wide), items-start so the sticky aside doesn't stretch.
    <div className="section-counter-reset flex flex-col gap-7 tablet:gap-8 desktop:grid desktop:grid-cols-[minmax(0,1fr)_var(--sidebar-width-compact)] desktop:items-start desktop:gap-x-8 wide:grid-cols-[minmax(0,1fr)_var(--sidebar-width)] wide:gap-x-10">
      <div className="flex min-w-0 flex-col gap-7 tablet:gap-8 desktop:gap-10">
        <section data-testid="section-summary" className="space-y-2">
          <h1>{charge.displayName}</h1>
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

        {distributionBlocks}
      </div>

      <ResultMetadataAside
        lastRefreshed={data.lastRefreshed}
        links={links}
        aggregateRunId={data.aggregateRunId}
        actions={
          // DP-3 disclosure wraps the DP-2 entry from the OUTSIDE — the
          // entry's ARIA, testid, strings, and routing are byte-identical.
          <JudgeDisclosure>
            <JudgeFilterEntry chargeSlug={charge.slug} />
          </JudgeDisclosure>
        }
      >
        {/* Sample-size pairs per available distribution (bglad §14.4 pair
            grammar): one-word context label over the existing SampleSizeLabel
            value line. Real content in both places by design — the section
            headers keep their own labels; nothing is aria-hidden. */}
        <dl className="flex flex-col gap-4">
          <div>
            <dt className="text-xs font-semibold tracking-[.10em] text-faint uppercase">
              {CHARGE_RESULT_COPY.asideOutcomesLabel}
            </dt>
            <dd className="mt-1">
              <SampleSizeLabel label={formatRecordsLabel(outcomes.sampleSize)} />
            </dd>
          </div>
          {sentencing.available && (
            <div>
              <dt className="text-xs font-semibold tracking-[.10em] text-faint uppercase">
                {CHARGE_RESULT_COPY.asideSentencingLabel}
              </dt>
              <dd className="mt-1">
                <SampleSizeLabel label={formatSentenceComponentsLabel(sentencing.sampleSize)} />
              </dd>
            </div>
          )}
        </dl>
      </ResultMetadataAside>
    </div>
  );
}
