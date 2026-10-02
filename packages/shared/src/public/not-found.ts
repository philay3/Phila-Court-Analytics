/**
 * Root 404 copy (task STATIC-2b, pin 7). The static site serves ONE not-found
 * page — Cloudflare Pages answers every unknown path, including an unknown
 * charge slug and a `?judge=` that no longer maps anywhere, with `404.html` —
 * so this wording has to be true for all three cases at once. Pinned here so
 * the web renders it verbatim and the copy-safety scanner covers it at its
 * definition.
 */
export const ROOT_NOT_FOUND_HEADING = 'Page not found';

export const ROOT_NOT_FOUND_MESSAGE =
  'No page exists at this address. It may name a charge or judge that is not in the published data, or the link may be out of date.';

/** Link back to the homepage search. The directory link reuses BROWSE_ALL_CHARGES_LINK_TEXT. */
export const ROOT_NOT_FOUND_HOME_LINK_TEXT = 'Return to search';
