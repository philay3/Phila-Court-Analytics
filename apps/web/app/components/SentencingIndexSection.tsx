/**
 * Sentencing-index lead block (task 35.3, pins 1, 4, 5, 6, 9, 10). Renders the
 * conviction-grain sentencing index as the house bar+required-table pattern:
 * a semantic table (the accessible source of truth, caption = the conditional
 * header) paired with presentational aria-hidden bars, the wedge disclosure
 * line below the table, and — on charge pages only — the grade-mix line.
 *
 * Everything renders API-served values through the 11.4 formatters: the
 * percentages are `percentageOfSentenced` as served (bars use them directly on
 * the fixed 0-100 axis), medians arrive pre-converted to months, and the
 * grade rows keep their served dominant-first order. The frontend computes
 * nothing (pin 1); the only local lookup is category code → taxonomy display
 * name, from the same @pca/shared public-category list the API contract is
 * built on.
 *
 * Judge pages pass no `grades`, so no grade line can render at that grain
 * (ruling 2 / pin 6) — the absence is structural, not conditional copy.
 */
import { useId } from 'react';
import {
  publicSentencingCategories,
  SENTENCING_INDEX_CAPTION,
  SENTENCING_INDEX_CATEGORY_HEADER,
  SENTENCING_INDEX_COUNT_HEADER,
  SENTENCING_INDEX_MEDIAN_HEADER,
  SENTENCING_INDEX_PERCENTAGE_HEADER,
} from '@pca/shared';
import type {
  ConvictionGradeRow,
  SentencingCategoryCode,
  SentencingIndexCategoryRow,
  SentencingIndexSummary,
} from '@pca/shared';
import {
  formatCount,
  formatGradeMixLine,
  formatMedianMonths,
  formatPercentage,
  formatSentencedConvictionsLabel,
  formatWedgeDisclosure,
} from '../lib/formatters';
import { definitionAnchor } from '../lib/definition-anchor';
import { categoryFillClass } from './category-fill';
import { RESULT_DISPLAY_COPY } from './result-display-copy';
import { SampleSizeLabel } from './SampleSizeLabel';
import { ThinDataBadge } from './ThinDataBadge';

const CATEGORY_NAME_BY_CODE = new Map<string, string>(
  publicSentencingCategories.map((category) => [category.code, category.displayName]),
);

// The contract restricts codes to the public taxonomy, so the lookup cannot
// miss; the code itself is the deterministic fallback rather than a throw.
function displayNameFor(code: SentencingCategoryCode): string {
  return CATEGORY_NAME_BY_CODE.get(code) ?? code;
}

interface SentencingIndexSectionProps {
  /** The present-arm summary row (conviction denominator, wedge, thin flag). */
  summary: SentencingIndexSummary;
  /** Category rows exactly as served (already in taxonomy order). */
  categories: readonly SentencingIndexCategoryRow[];
  /** Charge pages pass the served grade mix; judge pages pass nothing. */
  grades?: readonly ConvictionGradeRow[];
}

export function SentencingIndexSection({
  summary,
  categories,
  grades,
}: SentencingIndexSectionProps) {
  const captionId = useId();
  const gradeMixLine = grades === undefined ? null : formatGradeMixLine(grades);

  return (
    <section
      aria-labelledby={captionId}
      className="space-y-3 border-t-3 border-double border-ink pt-3"
    >
      {/* Section metadata, right-aligned on the header line (Civic Atlas). */}
      <div className="flex flex-wrap items-center justify-end gap-3">
        <SampleSizeLabel label={formatSentencedConvictionsLabel(summary.sentencedConvictions)} />
        <ThinDataBadge thin={summary.thinData} />
      </div>

      <table className="w-full border-collapse text-left text-sm">
        <caption
          id={captionId}
          className="section-counter mb-2 text-left font-serif text-base font-semibold text-ink"
        >
          {SENTENCING_INDEX_CAPTION}
        </caption>
        <thead>
          <tr>
            <th
              scope="col"
              className="border-b border-ink py-2 pr-4 text-xs font-semibold tracking-[.10em] text-faint uppercase"
            >
              {SENTENCING_INDEX_CATEGORY_HEADER}
            </th>
            <th
              scope="col"
              className="border-b border-ink py-2 pr-4 text-xs font-semibold tracking-[.10em] text-faint uppercase"
            >
              {SENTENCING_INDEX_COUNT_HEADER}
            </th>
            <th
              scope="col"
              className="border-b border-ink py-2 pr-4 text-xs font-semibold tracking-[.10em] text-faint uppercase"
            >
              {SENTENCING_INDEX_PERCENTAGE_HEADER}
            </th>
            <th
              scope="col"
              className="border-b border-ink py-2 text-xs font-semibold tracking-[.10em] text-faint uppercase"
            >
              {SENTENCING_INDEX_MEDIAN_HEADER}
            </th>
          </tr>
        </thead>
        <tbody>
          {categories.map((row) => {
            const displayName = displayNameFor(row.categoryCode);
            // Duration-free categories render an empty median cell (Q7).
            const median = formatMedianMonths(row.medianMinMonths, row.medianMaxMonths);
            return (
              <tr key={row.categoryCode}>
                <th scope="row" className="border-b border-hairline py-2 pr-4 font-normal text-ink">
                  <span className="font-serif">{displayName}</span>{' '}
                  <a
                    href={definitionAnchor('sentencing', row.categoryCode)}
                    aria-label={`${RESULT_DISPLAY_COPY.definitionLinkLabelPrefix}${displayName}`}
                    className="text-accent underline hover:text-accent-hover"
                  >
                    {RESULT_DISPLAY_COPY.definitionLinkText}
                  </a>
                </th>
                <td className="border-b border-hairline py-2 pr-4 text-body">
                  {formatCount(row.convictionCount)}
                </td>
                <td className="border-b border-hairline py-2 pr-4 text-body">
                  {formatPercentage(row.percentageOfSentenced)}
                </td>
                <td className="border-b border-hairline py-2 text-body">{median}</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {/* Presentational bars, exactly the DistributionSection pattern: fixed
          0-100 axis, fill width = the served percentage, aria-hidden with the
          table as the accessible equivalent. */}
      <div aria-hidden="true" className="space-y-2 pt-1">
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
        {categories.map((row) => {
          const thinBar = summary.thinData ? ' border border-dashed border-ink opacity-[0.72]' : '';
          return (
            <div key={row.categoryCode} className="space-y-1">
              <div className="flex justify-between gap-4 text-sm text-body">
                <span className="font-serif">{displayNameFor(row.categoryCode)}</span>
                <span className="text-xs font-semibold text-ink">
                  {formatCount(row.convictionCount)} · {formatPercentage(row.percentageOfSentenced)}
                </span>
              </div>
              <div className="chart-track h-4 w-full overflow-hidden">
                <div
                  data-testid={`index-bar-fill-${row.categoryCode}`}
                  className={`h-full ${categoryFillClass('sentencing', row.categoryCode)}${thinBar}`}
                  style={{ width: `${row.percentageOfSentenced}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* Wedge disclosure (pin 10): neutral, numeric, always rendered. */}
      <p data-testid="index-wedge-disclosure" className="text-sm text-muted">
        {formatWedgeDisclosure(summary)}
      </p>

      {/* Grade-mix line (pin 5): charge pages only; served order. */}
      {gradeMixLine !== null && (
        <p data-testid="index-grade-mix" className="text-sm text-muted">
          {gradeMixLine}
        </p>
      )}
    </section>
  );
}

/** 0-100 axis tick positions (labels every 20%; gridlines every 10% via CSS). */
const AXIS_TICKS = [0, 20, 40, 60, 80, 100] as const;
