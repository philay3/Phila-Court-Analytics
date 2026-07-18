/**
 * Charge-only result view (task 13.2, pinned decisions 1, 4, 6, 7). The
 * presentational success render: it accepts the typed `charge_only` payload and
 * composes the 13.1 display components. No data fetching lives here — the server
 * component (page.tsx) fetches and branches; this component is fully testable
 * under jsdom.
 *
 * Mobile content order (pinned decision 6) is achieved by DOM source order in a
 * single-column, mobile-first layout — no CSS `order`. Each top-level block
 * carries a `data-testid="section-*"` so the order is asserted directly:
 *   result summary → responsible-use notice → thin-data callout (when either
 *   distribution is thin) → the two distributions → definitions/methodology
 *   links → judge-filter entry point.
 *
 * Distribution order is CONDITIONAL on the API `sentencing.available` flag
 * (task 33.2 pinned decision 4): where sentencing data exists the sentencing
 * block leads and the outcome block is demoted below it; on the
 * sentencing-unavailable arm the outcome block leads and the sentencing slot
 * below renders the existing callout. The branch consumes the API boolean
 * only — no counts or thresholds are evaluated here.
 *
 * Every count, percentage, sample size, date, and label renders through the
 * 11.4 formatters (pinned decision 7); the page computes no analytics.
 */
import Link from 'next/link';
import type { ChargeOnlyResultSuccess } from '@pca/shared';
import { formatLastRefreshed, formatResultTypeLabel } from '../lib/formatters';
import { DateRangeLabel } from './DateRangeLabel';
import { ResponsibleUseNotice } from './ResponsibleUseNotice';
import { ThinDataCallout } from './ThinDataCallout';
import { DistributionSection } from './DistributionSection';
import { SentencingUnavailableNotice } from './SentencingUnavailableNotice';
import { JudgeFilterEntry } from './JudgeFilterEntry';
import { CHARGE_RESULT_COPY } from './charge-result-copy';
import { RESULT_DISPLAY_COPY } from './result-display-copy';

interface ChargeOnlyResultViewProps {
  data: ChargeOnlyResultSuccess;
}

const LINK_CLASS = 'text-accent hover:text-accent-hover hover:underline';

export function ChargeOnlyResultView({ data }: ChargeOnlyResultViewProps) {
  const { charge, outcomes, sentencing, links } = data;
  // One page-level thin-data callout slot; each distribution also shows its own
  // precise thin-data badge inside DistributionSection.
  const showThinDataCallout = outcomes.thinData || (sentencing.available && sentencing.thinData);

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
  const sentencingBlock = (
    <div data-testid="section-sentencing" className="overflow-x-auto">
      {sentencing.available ? (
        <DistributionSection
          kind="sentencing"
          rows={sentencing.rows}
          sampleSize={sentencing.sampleSize}
          thinData={sentencing.thinData}
        />
      ) : (
        <SentencingUnavailableNotice methodologyHref={links.methodology} />
      )}
    </div>
  );

  return (
    // section-counter-reset scopes the Roman-numeral markers the two
    // DistributionSection captions render via CSS counters (DP-2).
    <div className="section-counter-reset flex flex-col gap-8">
      <section data-testid="section-summary" className="space-y-2">
        <h1>{charge.displayName}</h1>
        <p className="text-base font-semibold text-ink">{formatResultTypeLabel(data.resultType)}</p>
        <DateRangeLabel range={data.dateRange} />
        <p className="text-sm text-muted">
          {CHARGE_RESULT_COPY.lastRefreshedLabel}: {formatLastRefreshed(data.lastRefreshed)}
        </p>
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

      {sentencing.available ? (
        <>
          {sentencingBlock}
          {outcomeBlock}
        </>
      ) : (
        <>
          {outcomeBlock}
          {sentencingBlock}
        </>
      )}

      <p data-testid="section-links" className="flex flex-wrap gap-4">
        <Link href={links.methodology} className={LINK_CLASS}>
          {CHARGE_RESULT_COPY.methodologyLinkText}
        </Link>
        <Link href={links.definitions} className={LINK_CLASS}>
          {CHARGE_RESULT_COPY.definitionsLinkText}
        </Link>
      </p>

      <JudgeFilterEntry chargeSlug={charge.slug} />
    </div>
  );
}
