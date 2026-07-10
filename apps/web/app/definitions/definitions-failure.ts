import { FETCH_FAILURE_MESSAGE, PUBLIC_ERROR_MESSAGES } from '@pca/shared';
import type { PublicApiFailure } from '../lib/public-api-client';

/**
 * Maps a definitions-fetch failure to the user-facing message to render (task
 * 14.1). Both arms resolve to a controlled, copy-safety-scanned @pca/shared
 * constant — never an inline string and never the API's own `message` field or
 * any request detail:
 *   - `api_error` → the catalog message for the returned code
 *     (`PUBLIC_ERROR_MESSAGES`), typically INTERNAL_ERROR for this static,
 *     DB-independent endpoint.
 *   - `fetch_failed` → `FETCH_FAILURE_MESSAGE` (transport / non-JSON / malformed
 *     error payload).
 *
 * Pure and directly unit-tested, so the page's async server component stays a
 * thin fetch-and-dispatch shell.
 */
export function definitionsFailureMessage(failure: PublicApiFailure): string {
  return failure.kind === 'api_error' ? PUBLIC_ERROR_MESSAGES[failure.code] : FETCH_FAILURE_MESSAGE;
}
