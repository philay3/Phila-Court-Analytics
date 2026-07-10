import { FETCH_FAILURE_MESSAGE, PUBLIC_ERROR_MESSAGES } from '@pca/shared';
import type { PublicApiFailure } from '../lib/public-api-client';

/**
 * Maps a data-coverage-fetch TRANSPORT/error failure to the user-facing message
 * to render (task 14.2). Mirrors definitions-failure (14.1): both arms resolve
 * to a controlled, copy-safety-scanned @pca/shared constant — never an inline
 * string and never the API's own `message` field or any request detail:
 *   - `api_error` → the catalog message for the returned code
 *     (`PUBLIC_ERROR_MESSAGES`).
 *   - `fetch_failed` → `FETCH_FAILURE_MESSAGE` (transport / non-JSON / malformed
 *     error payload).
 *
 * This is distinct from the endpoint's own HTTP-200 "unavailable" arm, which is
 * a successful response the view renders directly (served `coverage.message`) —
 * NOT a failure. Pure and directly unit-tested, so the page's async server
 * component stays a thin fetch-and-dispatch shell.
 */
export function dataCoverageFailureMessage(failure: PublicApiFailure): string {
  return failure.kind === 'api_error' ? PUBLIC_ERROR_MESSAGES[failure.code] : FETCH_FAILURE_MESSAGE;
}
