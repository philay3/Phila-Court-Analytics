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
 *   distribution is thin) → outcome distribution → sentencing distribution →
 *   definitions/methodology links → judge-filter entry point.
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

interface ChargeOnlyResultViewProps {
  data: ChargeOnlyResultSuccess;
}

const LINK_CLASS =
  'text-accent hover:underline focus-visible:rounded-xs focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent';

export function ChargeOnlyResultView({ data }: ChargeOnlyResultViewProps) {
  const { charge, outcomes, sentencing, links } = data;
  // One page-level thin-data callout slot; each distribution also shows its own
  // precise thin-data badge inside DistributionSection.
  const showThinDataCallout = outcomes.thinData || (sentencing.available && sentencing.thinData);

  return (
    <div className="flex flex-col gap-8">
      <section data-testid="section-summary" className="space-y-2">
        <h1>{charge.displayName}</h1>
        <p className="text-base font-semibold text-ink">{formatResultTypeLabel(data.resultType)}</p>
        <DateRangeLabel range={data.dateRange} />
        <p className="text-sm text-muted">
          {CHARGE_RESULT_COPY.lastRefreshedLabel}: {formatLastRefreshed(data.lastRefreshed)}
        </p>
      </section>

      <div data-testid="section-responsible-use">
        <ResponsibleUseNotice />
      </div>

      {showThinDataCallout && (
        <div data-testid="section-thin-data">
          <ThinDataCallout thin={showThinDataCallout} />
        </div>
      )}

      <div data-testid="section-outcome" className="overflow-x-auto">
        <DistributionSection
          kind="outcome"
          rows={outcomes.rows}
          sampleSize={outcomes.sampleSize}
          thinData={outcomes.thinData}
        />
      </div>

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
