/**
 * Result metadata aside (task DP-3, bglad §9.4 adapted per the approved plan).
 * The shared sidebar for both result success views: heading, page-specific
 * rows, the relocated last-refreshed line, page-specific actions, and the
 * relocated Definitions/Methodology links (the former `section-links` block,
 * which this aside dissolves).
 *
 * Relocations are byte-identical: the last-refreshed line and both link
 * renders reuse the exact CHARGE_RESULT_COPY strings, the 11.4 formatter, and
 * the API `links` hrefs their previous positions used. Only position changed.
 *
 * Layout contract (DP-3 acceptance criteria 2–3): exactly ONE aside instance
 * exists in the DOM at every viewport — the ≥900px column placement is pure
 * CSS grid on the parent view; below 900px the aside renders in normal flow at
 * its DOM position (last). Stickiness is desktop-only (bglad §5.4/§15.5): the
 * sticky utilities are gated on the `desktop:` variant, so no sticky element
 * exists below 900px. No hidden/shown viewport variants, so no content is
 * exposed twice to assistive technology.
 *
 * The heading is a Civic Atlas double-rule section header WITHOUT the
 * section-counter utility: Roman-numeral markers belong to distribution
 * captions only, and the aside must not shift their numbering.
 */
import { useId, type ReactNode } from 'react';
import Link from 'next/link';
import { formatAggregateRunLabel, formatLastRefreshed } from '../lib/formatters';
import { CHARGE_RESULT_COPY } from './charge-result-copy';
import { RESULT_DISPLAY_COPY } from './result-display-copy';

const LINK_CLASS = 'text-accent hover:text-accent-hover hover:underline';

interface ResultMetadataAsideProps {
  /** ISO timestamp for the relocated last-refreshed line (API field). */
  lastRefreshed: string;
  /** API links object — hrefs for the relocated Definitions/Methodology links. */
  links: { methodology: string; definitions: string };
  /** The served run reference for the provenance line (task 35.3, pin 7). */
  aggregateRunId: string;
  /** Page-specific rows between the heading and last-refreshed (charge page:
   *  the sample-size label/value pairs). */
  children?: ReactNode;
  /** Page-specific action between last-refreshed and the links (charge page:
   *  the judge-filter entry; judge page: the remove-filter link). */
  actions?: ReactNode;
}

export function ResultMetadataAside({
  lastRefreshed,
  links,
  aggregateRunId,
  children,
  actions,
}: ResultMetadataAsideProps) {
  const headingId = useId();

  return (
    <aside
      data-testid="section-metadata"
      aria-labelledby={headingId}
      className="flex flex-col gap-4 border-t-3 border-double border-ink pt-3 desktop:sticky desktop:top-6"
    >
      <h2 id={headingId} className="text-sm font-semibold tracking-[.12em] text-ink uppercase">
        {RESULT_DISPLAY_COPY.asideHeading}
      </h2>
      {children}
      <p className="text-sm text-muted">
        {CHARGE_RESULT_COPY.lastRefreshedLabel}: {formatLastRefreshed(lastRefreshed)}
      </p>
      {actions}
      <p className="flex flex-wrap gap-4">
        <Link href={links.methodology} className={LINK_CLASS}>
          {CHARGE_RESULT_COPY.methodologyLinkText}
        </Link>
        <Link href={links.definitions} className={LINK_CLASS}>
          {CHARGE_RESULT_COPY.definitionsLinkText}
        </Link>
      </p>
      {/* Provenance line (task 35.3, pin 7): the served run reference in its
          short id form, at the bottom of the aside on both result pages. Its
          meaning is explained in methodology. */}
      <p data-testid="aggregate-run-line" className="text-xs text-faint">
        {formatAggregateRunLabel(aggregateRunId)}
      </p>
    </aside>
  );
}
