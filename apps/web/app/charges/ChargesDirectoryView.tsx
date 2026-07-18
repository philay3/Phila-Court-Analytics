'use client';

import Link from 'next/link';
import { useId, useRef, useState } from 'react';
import { CHARGE_DIRECTORY_UNAVAILABLE_MESSAGE, type ChargeDirectoryResponse } from '@pca/shared';
import { CHARGES_COPY, formatChargeCountLine } from './charges-copy';

/**
 * Charges directory view (task DP-4): h1 + lead → filter → count line → row
 * list → states (bglad §8 structure, Civic Atlas register skin — one bordered
 * surface, hairline row separators, no cards-per-row, no radius, no shadow).
 *
 * Filter (bglad §8.4): client-side over the loaded list — case-insensitive
 * substring against display name and statute code. The count line is a
 * polite live region so filtering announces without stealing focus. The
 * no-match state keeps the count line ("0 available charges") plus a clear
 * action that restores the list and refocuses the input — refocus happens
 * ONLY via the clear control; never a blank container.
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
 * unavailable arm's message IS that constant, literal-typed), never a false
 * zero count.
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
  const [query, setQuery] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const inputId = useId();

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

  const needle = query.trim().toLowerCase();
  const filtered = needle
    ? charges.filter(
        (charge) =>
          charge.displayName.toLowerCase().includes(needle) ||
          charge.statuteCode?.toLowerCase().includes(needle),
      )
    : charges;

  const handleClear = () => {
    setQuery('');
    inputRef.current?.focus();
  };

  return (
    <section>
      <h1>{CHARGES_COPY.heading}</h1>
      <p className="text-muted">{CHARGES_COPY.lead}</p>
      <div className="mt-6 border-2 border-ink bg-card p-5">
        <label
          htmlFor={inputId}
          className="block text-xs font-semibold tracking-[.12em] text-ink uppercase"
        >
          {CHARGES_COPY.filterLabel}
        </label>
        <input
          id={inputId}
          ref={inputRef}
          type="text"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={CHARGES_COPY.filterPlaceholder}
          className="mt-3 min-h-11 w-full bg-card px-1 py-2 font-serif text-lg text-ink placeholder:text-muted"
        />
      </div>
      <p aria-live="polite" className="mt-4 text-sm text-muted">
        {formatChargeCountLine(filtered.length)}
      </p>
      {filtered.length === 0 ? (
        <div className="mt-3 space-y-4">
          <p>{CHARGES_COPY.noMatchBody}</p>
          <button
            type="button"
            onClick={handleClear}
            className="min-h-11 bg-ink px-5 py-3 text-sm font-semibold tracking-[.08em] text-card uppercase hover:bg-ink-hover"
          >
            {CHARGES_COPY.clearAction}
          </button>
        </div>
      ) : (
        <ul className="mt-3 border-2 border-ink bg-card">
          {filtered.map((charge) => (
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
      )}
    </section>
  );
}
