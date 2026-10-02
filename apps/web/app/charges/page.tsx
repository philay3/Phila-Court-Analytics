import type { Metadata } from 'next';
import { getCharges } from '../lib/public-api-client';
import { ChargesDirectoryView } from './ChargesDirectoryView';
import { CHARGES_COPY } from './charges-copy';

/**
 * Charges directory route (task DP-4). A thin async server component: it
 * fetches the public charge list via the 11.2 client (server-side, absolute
 * base URL) and dispatches to the presentational view. Both availability arms
 * are data (the view renders the served unavailable message verbatim); only a
 * failed fetch throws — since task STATIC-2b that is a build-time failure of
 * the static export, never a request-time state. The former in-page Suspense
 * fallback (fix R7a) is gone with it: an export streams nothing. Site-wide
 * noindex is inherited from the root layout, unchanged.
 */
export const metadata: Metadata = {
  title: CHARGES_COPY.heading,
};

export default async function ChargesPage() {
  const result = await getCharges();

  if (!result.ok) {
    // Generic, detail-free throw — under the static build this fails the
    // export; the message never reaches a page.
    throw new Error('The charge directory could not be loaded.');
  }

  return (
    <div className="mx-auto w-full max-w-article">
      <ChargesDirectoryView data={result.data} />
    </div>
  );
}
