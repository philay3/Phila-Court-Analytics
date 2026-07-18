/**
 * Data-coverage page presentational views (task 14.2). No data fetching lives
 * here — the server component (page.tsx) fetches via the 11.2 client and
 * branches; these components are fully testable under jsdom.
 *
 * Pinned behaviour:
 *   - The always-present top-level fields (`jurisdiction`, `courtScope`,
 *     `plannedDataStart`) and the `knownLimitations` list render in BOTH
 *     coverage arms. The seeded-data disclosure lives in `knownLimitations`, so
 *     it must stay visible whether or not a published run exists.
 *   - `knownLimitations` entries render VERBATIM and in served order — one
 *     `<li>` per entry, no paraphrase, no reordering, no re-composition into
 *     prose. This is the single rendering of that content in web code.
 *   - The available arm renders the coverage figures; the unavailable arm
 *     renders the served `coverage.message` verbatim in place of them. The view
 *     never invents an unavailable message.
 *   - Every date/count renders through the 11.4 formatters — no inline
 *     formatting: `plannedDataStart` via `formatDateOnly`, the data window via
 *     `formatDateRange`, `lastRefreshed` via `formatLastRefreshed`, counts via
 *     `formatCount`.
 *   - Single-column, mobile-first, semantic heading hierarchy: h1 → h2 per
 *     section.
 *
 * The error body is a shared @pca/shared constant selected upstream by failure
 * arm (see data-coverage-failure.ts); it is never composed here.
 */
import type { DataCoverageResponse } from '@pca/shared';
import {
  formatCount,
  formatDateOnly,
  formatDateRange,
  formatLastRefreshed,
} from '../lib/formatters';
import { DATA_COVERAGE_COPY } from './data-coverage-copy';

interface LabeledRowProps {
  label: string;
  value: string;
  /**
   * Presentational only (DP-2): 'stat' renders the row as a bordered
   * Civic Atlas stat card (caps label over a large serif figure); 'row'
   * is the register-row default. Strings and values are untouched either
   * way, and DOM order inside the <dl> is unchanged.
   */
  variant?: 'row' | 'stat';
}

function LabeledRow({ label, value, variant = 'row' }: LabeledRowProps) {
  if (variant === 'stat') {
    return (
      <div className="border-2 border-ink bg-card p-4">
        <dt className="text-xs font-semibold tracking-[.10em] text-faint uppercase">{label}</dt>
        <dd className="mt-1 font-serif text-3xl font-semibold text-ink">{value}</dd>
      </div>
    );
  }
  return (
    <div className="space-y-1 border-b border-hairline pb-3 tablet:col-span-3 tablet:grid tablet:grid-cols-[185px_1fr] tablet:gap-x-4 tablet:space-y-0">
      <dt className="text-sm font-semibold text-ink">{label}</dt>
      <dd className="text-body">{value}</dd>
    </div>
  );
}

interface DataCoverageViewProps {
  data: DataCoverageResponse;
}

export function DataCoverageView({ data }: DataCoverageViewProps) {
  const { coverage } = data;

  return (
    <div className="section-counter-reset flex flex-col gap-10 desktop:gap-12">
      <header>
        <h1>{DATA_COVERAGE_COPY.heading}</h1>
      </header>

      <section className="space-y-4">
        <dl className="space-y-4">
          <LabeledRow label={DATA_COVERAGE_COPY.jurisdictionLabel} value={data.jurisdiction} />
          <LabeledRow label={DATA_COVERAGE_COPY.courtScopeLabel} value={data.courtScope} />
          <LabeledRow
            label={DATA_COVERAGE_COPY.dataStartLabel}
            value={formatDateOnly(data.plannedDataStart)}
          />
        </dl>
      </section>

      {coverage.available ? (
        <section className="space-y-4">
          <h2 className="section-counter border-t-3 border-double border-ink pt-2 text-sm font-semibold tracking-[.12em] text-ink uppercase">
            {DATA_COVERAGE_COPY.currentCoverageHeading}
          </h2>
          {/* 3-across is a layout, not a utility row: it engages at the 900px
              principal switch, not at tablet (DP-3 migration ruling). */}
          <dl className="space-y-4 desktop:grid desktop:grid-cols-3 desktop:gap-4 desktop:space-y-0">
            <LabeledRow
              label={DATA_COVERAGE_COPY.dataWindowLabel}
              value={formatDateRange({ start: coverage.dataStart, end: coverage.dataEnd })}
            />
            <LabeledRow
              label={DATA_COVERAGE_COPY.lastRefreshedLabel}
              value={formatLastRefreshed(coverage.lastRefreshed)}
            />
            <LabeledRow
              label={DATA_COVERAGE_COPY.aggregateRunLabel}
              value={coverage.aggregateRunId}
            />
            <LabeledRow
              label={DATA_COVERAGE_COPY.taxonomyVersionLabel}
              value={coverage.taxonomyVersion}
            />
            <LabeledRow
              variant="stat"
              label={DATA_COVERAGE_COPY.chargesWithOutcomeAggregatesLabel}
              value={formatCount(coverage.counts.chargesWithOutcomeAggregates)}
            />
            <LabeledRow
              variant="stat"
              label={DATA_COVERAGE_COPY.chargesWithSentencingAggregatesLabel}
              value={formatCount(coverage.counts.chargesWithSentencingAggregates)}
            />
            <LabeledRow
              variant="stat"
              label={DATA_COVERAGE_COPY.judgeChargePairsLabel}
              value={formatCount(coverage.counts.judgeChargePairs)}
            />
          </dl>
        </section>
      ) : (
        <section>
          <p role="status" className="text-muted">
            {coverage.message}
          </p>
        </section>
      )}

      <section className="space-y-4">
        <h2 className="section-counter border-t-3 border-double border-ink pt-2 text-sm font-semibold tracking-[.12em] text-ink uppercase">
          {DATA_COVERAGE_COPY.knownLimitationsHeading}
        </h2>
        <ul
          data-testid="known-limitations"
          className="list-decimal space-y-2 pl-5 leading-relaxed text-body marker:font-semibold marker:text-faint"
        >
          {data.knownLimitations.map((limitation, index) => (
            // Served strings are the content; index keys are acceptable because
            // the list is render-once and never reordered client-side.
            <li key={index}>{limitation}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}

interface DataCoverageErrorStateProps {
  /** User-facing message, pre-selected from @pca/shared constants by failure arm. */
  message: string;
}

export function DataCoverageErrorState({ message }: DataCoverageErrorStateProps) {
  return (
    <div className="space-y-4">
      <h1>{DATA_COVERAGE_COPY.errorHeading}</h1>
      <p role="alert" className="text-muted">
        {message}
      </p>
    </div>
  );
}
