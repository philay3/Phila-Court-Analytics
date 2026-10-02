import Link from 'next/link';
import {
  BROWSE_ALL_CHARGES_LINK_TEXT,
  ROOT_NOT_FOUND_HEADING,
  ROOT_NOT_FOUND_HOME_LINK_TEXT,
  ROOT_NOT_FOUND_MESSAGE,
} from '@pca/shared';

/**
 * Root not-found page (task STATIC-2b, pin 7). In the static export this is
 * `404.html`, the one answer Cloudflare Pages gives for every unknown path —
 * an unknown route, an unknown charge slug, or a stale link — so the copy is
 * pinned in @pca/shared to be true for all of them and rendered verbatim here,
 * with links to the homepage search and the charges directory. Site-wide
 * noindex is inherited from the root layout.
 */
export default function NotFound() {
  return (
    <div className="mx-auto w-full max-w-article space-y-4">
      <h1>{ROOT_NOT_FOUND_HEADING}</h1>
      <p className="text-muted">{ROOT_NOT_FOUND_MESSAGE}</p>
      <p className="flex flex-wrap gap-4">
        <Link href="/" className="text-accent hover:text-accent-hover hover:underline">
          {ROOT_NOT_FOUND_HOME_LINK_TEXT}
        </Link>
        <Link href="/charges" className="text-accent hover:text-accent-hover hover:underline">
          {BROWSE_ALL_CHARGES_LINK_TEXT}
        </Link>
      </p>
    </div>
  );
}
