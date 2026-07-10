import {
  PUBLIC_ERROR_CODES,
  type ChargeOnlyResultResponse,
  type ChargeOnlyResultSuccess,
  type ChargeOnlyResultUnavailable,
} from '@pca/shared';
import type { PublicApiResult } from '../../lib/public-api-client';

/**
 * Pure branch resolver for the charge-only result page (task 13.2). Maps the
 * 11.2 client's typed result to the four states the page renders, so the
 * server component stays a thin dispatcher and the detection logic is unit-
 * tested here (pinned decision 1: page.tsx itself is exempt from direct tests).
 *
 * The state space (post-13.2a contract):
 *   - success      → HTTP 200 `charge_only` arm; render the result view.
 *   - unavailable  → HTTP 200 `charge_only_unavailable` arm; render the in-page
 *                    unavailable view (NEVER not-found). The charge exists but
 *                    no publishable aggregate does.
 *   - not-found    → CHARGE_NOT_FOUND api_error; render not-found.tsx.
 *   - error        → any other api_error code or a transport failure; the page
 *                    throws so error.tsx renders generic, detail-free copy.
 *
 * Sentencing-unavailable is NOT modeled here: it is an in-payload arm of a
 * success response (`sentencing.available === false`) handled inside the view.
 */
export type ChargeResultState =
  | { kind: 'success'; data: ChargeOnlyResultSuccess }
  | { kind: 'unavailable'; data: ChargeOnlyResultUnavailable }
  | { kind: 'not-found' }
  | { kind: 'error' };

export function resolveChargeResultState(
  result: PublicApiResult<ChargeOnlyResultResponse>,
): ChargeResultState {
  if (result.ok) {
    return result.data.resultType === 'charge_only'
      ? { kind: 'success', data: result.data }
      : { kind: 'unavailable', data: result.data };
  }
  if (
    result.error.kind === 'api_error' &&
    result.error.code === PUBLIC_ERROR_CODES.CHARGE_NOT_FOUND
  ) {
    return { kind: 'not-found' };
  }
  return { kind: 'error' };
}
