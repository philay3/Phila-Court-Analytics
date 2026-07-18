import type { Metadata } from 'next';
import { getCharges } from '../lib/public-api-client';
import { ChargesDirectoryView } from './ChargesDirectoryView';
import { CHARGES_COPY } from './charges-copy';

/**
 * Charges directory route (task DP-4). A thin async server component: it
 * fetches the public charge list via the 11.2 client (server-side, absolute
 * base URL) and dispatches to the presentational view. Both availability arms
 * are data (the view renders the served unavailable message verbatim); only a
 * failed fetch throws, into the error.tsx boundary — the charge-route
 * precedent, which supplies the retry via reset().
 *
 * Rendering: `dynamic = 'force-dynamic'` (task 15.2 CI finding) so the page
 * renders per request and never bakes a build-time snapshot of the published
 * run. Site-wide noindex is inherited from the root layout, unchanged.
 */
export const metadata: Metadata = {
  title: CHARGES_COPY.heading,
};

export const dynamic = 'force-dynamic';

export default async function ChargesPage() {
  const result = await getCharges();

  if (!result.ok) {
    // Generic, detail-free throw — error.tsx renders its own safe copy and
    // never surfaces this message or any request detail.
    throw new Error('The charge directory could not be loaded.');
  }

  return (
    <div className="mx-auto w-full max-w-article">
      <ChargesDirectoryView data={result.data} />
    </div>
  );
}
