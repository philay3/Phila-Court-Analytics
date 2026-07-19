import Link from 'next/link';
import { BROWSE_ALL_CHARGES_LINK_TEXT, FEATURED_CHARGES_HEADING } from '@pca/shared';
import type { ChargeDirectoryEntry } from '@pca/shared';
import { availabilityText } from '../charges/charges-copy';
import { formatSampleSize } from '../lib/formatters';

/**
 * Homepage featured-charges section (task DP-5, pins 4–5). Purely
 * presentational: the page passes the top rows of the directory response in
 * served order (already sliced; zero rows never reach here — the page omits
 * the section entirely). Card contents mirror directory rows exactly — name,
 * the availability line (shared availabilityText helper), the pinned
 * `Sample size: N` line — and nothing else; no other statistic renders.
 *
 * Link mechanism is the directory-row ruling reused: each card carries
 * exactly ONE anchor — on the charge name, stretched over the card via an
 * absolutely positioned pseudo-element — so every card link's accessible
 * name is its charge name. The sanctioned browse-all link sits below the
 * cards, outside the list.
 */
interface FeaturedChargesProps {
  /** Top directory rows in served order; length 1–4 by construction. */
  charges: readonly ChargeDirectoryEntry[];
}

export function FeaturedCharges({ charges }: FeaturedChargesProps) {
  return (
    <section aria-labelledby="featured-charges-heading" className="mt-10">
      <h2 id="featured-charges-heading" className="font-serif text-xl font-bold text-ink">
        {FEATURED_CHARGES_HEADING}
      </h2>
      <ul className="mt-4 grid gap-4 tablet:grid-cols-2">
        {charges.map((charge) => (
          <li
            key={charge.slug}
            className="group relative flex flex-col border border-rule bg-card p-5 hover:bg-paper"
          >
            <Link
              href={`/charges/${charge.slug}`}
              className="self-start font-serif text-lg font-bold text-ink before:absolute before:inset-0 before:content-[''] group-hover:underline"
            >
              {charge.displayName}
            </Link>
            <p className="mt-1.5 text-sm text-muted">{availabilityText(charge.hasSentencing)}</p>
            <p className="mt-1 text-sm text-faint">{formatSampleSize(charge.outcomeSampleSize)}</p>
          </li>
        ))}
      </ul>
      <p className="mt-4">
        <Link href="/charges" className="text-accent underline hover:text-accent-hover">
          {BROWSE_ALL_CHARGES_LINK_TEXT}
        </Link>
      </p>
    </section>
  );
}
