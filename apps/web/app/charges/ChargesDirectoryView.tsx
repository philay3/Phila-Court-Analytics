'use client';

import Link from 'next/link';
import { CHARGE_DIRECTORY_UNAVAILABLE_MESSAGE, type ChargeDirectoryResponse } from '@pca/shared';
import { CHARGES_COPY, formatChargeCountLine } from './charges-copy';

/**
 * Charges directory view (task DP-4): h1 + lead → count line → row list →
 * states (bglad §8 structure, Civic Atlas register skin — one bordered
 * surface, hairline row separators, no cards-per-row, no radius, no shadow).
 *
 * Row anchoring (review-gate required fix): each row carries exactly ONE link
 * in the accessibility tree — the anchor on the charge name, stretched over
 * the whole row via an absolutely positioned pseudo-element — so every row
 * link's accessible name is its charge name, never seventy identical "View
 * results" entries. The sanctioned "View results" action stays visible
 * alongside the anchor (accent, arrow via CSS generated content excluded from
 * the accessible name); no aria-label replaces visible text.
 *
 * Both empty cases — the served unavailable arm and an available run with
 * zero rows — render the shared CHARGE_DIRECTORY_UNAVAILABLE_MESSAGE (the
 * unavailable arm's message IS that constant, literal-typed), never a blank
 * container and never a false zero count.
 */
interface ChargesDirectoryViewProps {
  data: ChargeDirectoryResponse;
}

function availabilityText(hasSentencing: boolean): string {
  return hasSentencing
    ? CHARGES_COPY.availabilityWithSentencing
    : CHARGES_COPY.availabilityOutcomesOnly;
}

export function ChargesDirectoryView({ data }: ChargesDirectoryViewProps) {
  const charges = data.available ? data.charges : [];

  if (charges.length === 0) {
    return (
      <section>
        <h1>{CHARGES_COPY.heading}</h1>
        <p className="text-muted">{CHARGES_COPY.lead}</p>
        <p role="status" className="mt-6 text-muted">
          {CHARGE_DIRECTORY_UNAVAILABLE_MESSAGE}
        </p>
      </section>
    );
  }

  return (
    <section>
      <h1>{CHARGES_COPY.heading}</h1>
      <p className="text-muted">{CHARGES_COPY.lead}</p>
      <p aria-live="polite" className="mt-6 text-sm text-muted">
        {formatChargeCountLine(charges.length)}
      </p>
      <ul className="mt-3 border-2 border-ink bg-card">
        {charges.map((charge) => (
          <li
            key={charge.slug}
            className="group relative flex min-h-26 flex-col border-b border-hairline p-5 last:border-b-0 hover:bg-paper desktop:min-h-22 desktop:px-6 desktop:py-[1.125rem] desktop:pr-44"
          >
            <Link
              href={`/charges/${charge.slug}`}
              className="self-start font-serif text-lg font-bold text-ink before:absolute before:inset-0 before:content-['']"
            >
              {charge.displayName}
            </Link>
            <p className="mt-1.5 text-sm text-muted">{availabilityText(charge.hasSentencing)}</p>
            <span className="row-action-arrow mt-3 self-start text-[0.9375rem] font-semibold text-accent group-hover:underline desktop:absolute desktop:top-[1.125rem] desktop:right-6 desktop:mt-0">
              {CHARGES_COPY.rowAction}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
