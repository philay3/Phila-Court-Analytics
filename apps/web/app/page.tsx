import Link from 'next/link';
import type { ChargeDirectoryEntry } from '@pca/shared';
import { FeaturedCharges } from './components/FeaturedCharges';
import { SearchForm } from './components/SearchForm';
import { HOME_COPY } from './components/home-copy';
import { getCharges } from './lib/public-api-client';

/**
 * Homepage (task DP-5): gains a server-side fetch feeding the featured
 * section, so it renders per request — `force-dynamic` per the standing
 * no-build-time-API-fetch rule (the /charges 15.2 precedent). The featured
 * section is strictly fail-soft (pin 5): any failure arm renders the page
 * without the section; the search surface never depends on the fetch.
 */
export const dynamic = 'force-dynamic';

/**
 * Top directory rows (up to 4, served order) for the featured section, or an
 * empty list on ANY failure: fetch/API failure, the unavailable arm, zero
 * rows, or a thrown fetch. The catch is deliberate defense in depth —
 * getCharges resolves failures as `{ ok: false }` by contract, but the
 * homepage must never error because of this section, so a rejection is
 * absorbed here rather than reaching the route boundary.
 */
async function featuredCharges(): Promise<ChargeDirectoryEntry[]> {
  try {
    const result = await getCharges();
    if (!result.ok || !result.data.available) {
      return [];
    }
    return result.data.charges.slice(0, 4);
  } catch {
    return [];
  }
}

export default async function HomePage() {
  const featured = await featuredCharges();

  return (
    <div className="mx-auto w-full max-w-article">
      <h1>{HOME_COPY.heading}</h1>
      <p className="text-muted">{HOME_COPY.intro}</p>

      <SearchForm />

      <p className="mt-8 text-muted">{HOME_COPY.disclaimer}</p>

      <p className="mt-4 text-muted">
        {HOME_COPY.linksIntro}{' '}
        <Link href="/methodology" className="text-accent underline hover:text-accent-hover">
          {HOME_COPY.methodologyLinkText}
        </Link>{' '}
        ({HOME_COPY.methodologyLinkDescription}) ·{' '}
        <Link href="/data-coverage" className="text-accent underline hover:text-accent-hover">
          {HOME_COPY.dataCoverageLinkText}
        </Link>{' '}
        ({HOME_COPY.dataCoverageLinkDescription}).
      </p>

      {/* DP-5 placement ruling: the featured section renders below the
          disclaimer and links — the honesty copy keeps its adjacency to the
          search card; this is the last content block before the footer. */}
      {featured.length > 0 && <FeaturedCharges charges={featured} />}
    </div>
  );
}
