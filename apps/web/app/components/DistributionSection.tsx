/**
 * Generic distribution section (task 13.1). One reusable component for both the
 * outcome and sentencing distributions of a result: a semantic table (the
 * accessible source of truth) paired with presentational, aria-hidden
 * horizontal bars. Tasks 13.2/13.3 compose it; this task ships components only.
 *
 * Pinned decisions honoured here:
 *   1. Row order is server-authoritative. `rows` render in the exact order the
 *      API served them (verified: the result services sort to taxonomy
 *      sortOrder before serving). There is NO client-side sort.
 *   2. Per-row definition links use the shared `definitionAnchor` helper.
 *   3. Bars are presentational supplements: each fill width derives ONLY from
 *      the API `percentage`, never from counts. The bar block is aria-hidden;
 *      the table is its accessible equivalent and carries every value the bars
 *      show. Each bar row still shows its label and value as visible text.
 *   4. Props are typed from `@pca/shared` response types; the only local type
 *      is the presentational `DistributionKind` discriminator.
 *
 * The thin-data BADGE is embedded here (adjacent to the sample size) when the
 * distribution is thin. The thin-data CALLOUT is deliberately NOT rendered here
 * — it ships standalone so 13.2/13.3 can place it at page level.
 *
 * Display groups (pre-recording session, pinned decision 3): outcome sections
 * pass the two pinned groups via `groups`; served rows are partitioned into
 * CONSECUTIVE RUNS by membership, and a run belonging to a group renders under
 * its shared heading in both the table (a scope="rowgroup" header row opening
 * the run's tbody) and the bar stack. Pure presentation: rows keep exactly the
 * served order (pinned decision 1 stands), each row keeps its own served
 * percentage, and no summed or derived figures exist. Without `groups` the
 * render is a single ungrouped run — the sentencing sections are unchanged.
 */
import { useId } from 'react';
import type {
  OutcomeDistributionEntry,
  SampleSize,
  SentencingDistributionEntry,
  ThinDataStatus,
} from '@pca/shared';
import {
  formatCount,
  formatPercentage,
  formatRecordsLabel,
  formatSentenceComponentsLabel,
} from '../lib/formatters';
import { definitionAnchor, type DistributionKind } from '../lib/definition-anchor';
import { categoryFillClass } from './category-fill';
import type { DistributionRowGroup } from './outcome-display-groups';
import { RESULT_DISPLAY_COPY } from './result-display-copy';
import { SampleSizeLabel } from './SampleSizeLabel';
import { ThinDataBadge } from './ThinDataBadge';

/** A row from either distribution; both shapes share every displayed field. */
type DistributionRow = OutcomeDistributionEntry | SentencingDistributionEntry;

interface DistributionSectionProps {
  /** Which distribution this is — selects captions/headers and anchor prefix. */
  kind: DistributionKind;
  /** Rows exactly as served by the API (already in taxonomy order). */
  rows: readonly DistributionRow[];
  /** This distribution's sample size (sentencing's is independent of outcome). */
  sampleSize: SampleSize;
  /** This distribution's API thin-data flag. */
  thinData: ThinDataStatus;
  /**
   * Caption override (task 35.3, pin 11): when the sentencing block renders
   * alongside the index it carries the distinct detail caption; on the
   * absent arm the default captions render byte-identically to today.
   */
  caption?: string;
  /**
   * Visual-only display groups (pre-recording pin 3). Outcome sections pass
   * the pinned pairs; sentencing sections pass nothing. Membership selects
   * consecutive served rows under a shared heading — never an order change.
   */
  groups?: readonly DistributionRowGroup[];
}

interface RowSegment {
  /** The group whose heading spans this run, or null for ungrouped rows. */
  group: DistributionRowGroup | null;
  rows: DistributionRow[];
}

/**
 * Partitions served rows into consecutive runs by group membership. A pure
 * forward walk: rows stay in exactly the served order (pinned decision 1 —
 * grouping is visual only), and a heading renders when at least one member
 * row is present because a run exists iff it has a row. Hypothetical
 * non-adjacent members would open a second run under the same heading rather
 * than be moved together.
 */
function segmentRows(
  rows: readonly DistributionRow[],
  groups: readonly DistributionRowGroup[],
): RowSegment[] {
  const segments: RowSegment[] = [];
  for (const row of rows) {
    const group = groups.find((entry) => entry.memberCodes.includes(row.categoryCode)) ?? null;
    const current = segments[segments.length - 1];
    if (current !== undefined && current.group === group) {
      current.rows.push(row);
    } else {
      segments.push({ group, rows: [row] });
    }
  }
  return segments;
}

function captionFor(kind: DistributionKind): string {
  return kind === 'outcome'
    ? RESULT_DISPLAY_COPY.outcomeCaption
    : RESULT_DISPLAY_COPY.sentencingCaption;
}

/**
 * Reconciled sample labels (task 35.3, pin 11): each block names the unit its
 * sample counts — outcome blocks count records, the component-grain
 * sentencing block counts sentence components.
 */
function sampleLabelFor(kind: DistributionKind, sampleSize: SampleSize): string {
  return kind === 'outcome'
    ? formatRecordsLabel(sampleSize)
    : formatSentenceComponentsLabel(sampleSize);
}

function categoryHeaderFor(kind: DistributionKind): string {
  return kind === 'outcome'
    ? RESULT_DISPLAY_COPY.outcomeCategoryHeader
    : RESULT_DISPLAY_COPY.sentencingCategoryHeader;
}

export function DistributionSection({
  kind,
  rows,
  sampleSize,
  thinData,
  caption: captionOverride,
  groups,
}: DistributionSectionProps) {
  const captionId = useId();
  const caption = captionOverride ?? captionFor(kind);
  const categoryHeader = categoryHeaderFor(kind);
  // Without groups this is one ungrouped run — the pre-groups render exactly.
  const segments = segmentRows(rows, groups ?? []);

  return (
    <section
      aria-labelledby={captionId}
      className="space-y-3 border-t-3 border-double border-ink pt-3"
    >
      {/* Section metadata, right-aligned on the header line (Civic Atlas). */}
      <div className="flex flex-wrap items-center justify-end gap-3">
        <SampleSizeLabel label={sampleLabelFor(kind, sampleSize)} />
        <ThinDataBadge thin={thinData} />
      </div>

      <table className="w-full border-collapse text-left text-sm">
        <caption
          id={captionId}
          className="section-counter mb-2 text-left font-serif text-base font-semibold text-ink"
        >
          {caption}
        </caption>
        <thead>
          <tr>
            <th
              scope="col"
              className="border-b border-ink py-2 pr-4 text-xs font-semibold tracking-[.10em] text-faint uppercase"
            >
              {categoryHeader}
            </th>
            <th
              scope="col"
              className="border-b border-ink py-2 pr-4 text-xs font-semibold tracking-[.10em] text-faint uppercase"
            >
              {RESULT_DISPLAY_COPY.countHeader}
            </th>
            <th
              scope="col"
              className="border-b border-ink py-2 text-xs font-semibold tracking-[.10em] text-faint uppercase"
            >
              {RESULT_DISPLAY_COPY.percentageHeader}
            </th>
          </tr>
        </thead>
        {segments.map((segment, segmentIndex) => (
          // One tbody per run so a grouped run's heading is a true rowgroup
          // header (scope="rowgroup" spans exactly its tbody, nothing more).
          <tbody key={`segment-${segmentIndex}`}>
            {segment.group !== null && (
              <tr>
                <th
                  scope="rowgroup"
                  colSpan={3}
                  className="border-b border-hairline pt-3 pb-1 pr-4 text-xs font-semibold tracking-[.10em] text-faint uppercase"
                >
                  {segment.group.heading}
                </th>
              </tr>
            )}
            {segment.rows.map((row) => (
              <tr key={row.categoryCode}>
                <th scope="row" className="border-b border-hairline py-2 pr-4 font-normal text-ink">
                  <span className="font-serif">{row.displayName}</span>{' '}
                  <a
                    href={definitionAnchor(kind, row.categoryCode)}
                    aria-label={`${RESULT_DISPLAY_COPY.definitionLinkLabelPrefix}${row.displayName}`}
                    className="text-accent underline hover:text-accent-hover"
                  >
                    {RESULT_DISPLAY_COPY.definitionLinkText}
                  </a>
                </th>
                <td className="border-b border-hairline py-2 pr-4 text-body">
                  {formatCount(row.count)}
                </td>
                <td className="border-b border-hairline py-2 text-body">
                  {formatPercentage(row.percentage)}
                </td>
              </tr>
            ))}
          </tbody>
        ))}
      </table>

      {/*
       * Presentational bars (pinned decision 3). aria-hidden so assistive tech
       * reads the table instead; each fill width comes straight from the API
       * percentage — the fixed 0-100 axis (pinned decision A2) means the raw
       * served percentage IS the axis position, no scaling arithmetic. All
       * chart chrome (ticks, gridlines, fills) lives inside this hidden block.
       * Visible label + value text keeps meaning off color/hover.
       */}
      <div aria-hidden="true" className="space-y-2 pt-1">
        {/* Fixed 0-100 axis: tick labels every 20%, gridlines every 10% (the
            chart-track gradient). Numerals are axis geometry, not copy. */}
        <div className="relative h-4 text-[11px] font-semibold text-faint">
          {AXIS_TICKS.map((tick) => (
            <span
              key={tick}
              className={`absolute ${
                tick === 0 ? '' : tick === 100 ? '-translate-x-full' : '-translate-x-1/2'
              }`}
              style={{ left: `${tick}%` }}
            >
              {tick}
            </span>
          ))}
        </div>
        {segments.map((segment, segmentIndex) => (
          <div key={`segment-${segmentIndex}`} className="space-y-2">
            {/* Mirror of the table's rowgroup heading (pin 3: both places). */}
            {segment.group !== null && (
              <div className="pt-1 text-xs font-semibold tracking-[.10em] text-faint uppercase">
                {segment.group.heading}
              </div>
            )}
            {segment.rows.map((row) => {
              const thinBar = thinData ? ' border border-dashed border-ink opacity-[0.72]' : '';
              return (
                <div key={row.categoryCode} className="space-y-1">
                  <div className="flex justify-between gap-4 text-sm text-body">
                    <span className="font-serif">{row.displayName}</span>
                    <span className="text-xs font-semibold text-ink">
                      {formatCount(row.count)} · {formatPercentage(row.percentage)}
                    </span>
                  </div>
                  <div className="chart-track h-4 w-full overflow-hidden">
                    <div
                      data-testid={`distribution-bar-fill-${row.categoryCode}`}
                      className={`h-full ${categoryFillClass(kind, row.categoryCode)}${thinBar}`}
                      style={{ width: `${row.percentage}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </section>
  );
}

/** 0-100 axis tick positions (labels every 20%; gridlines every 10% via CSS). */
const AXIS_TICKS = [0, 20, 40, 60, 80, 100] as const;
