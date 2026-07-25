import {
  PUBLIC_ERROR_CODES,
  type ChargeOnlyResultResponse,
  type ChargeOnlyResultSuccess,
  type ChargeOnlyResultUnavailable,
  type ChargeOnlyResultVolume,
} from '@pca/shared';
import type { PublicApiResult } from '../../lib/public-api-client';

/**
 * Pure branch resolver for the charge-only result page (task 13.2). Maps the
 * 11.2 client's typed result to the five states the page renders, so the
 * server component stays a thin dispatcher and the detection logic is unit-
 * tested here (pinned decision 1: page.tsx itself is exempt from direct tests).
 *
 * The state space (post-Phase-36 contract):
 *   - success      → HTTP 200 `charge_only` arm; render the result view.
 *   - volume       → HTTP 200 `charge_only_volume` arm (Phase 36): the charge
 *                    is seen in the published run but has no recorded outcome
 *                    yet; render the volume view (the number, never the dead
 *                    end).
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
  | { kind: 'volume'; data: ChargeOnlyResultVolume }
  | { kind: 'unavailable'; data: ChargeOnlyResultUnavailable }
  | { kind: 'not-found' }
  | { kind: 'error' };

export function resolveChargeResultState(
  result: PublicApiResult<ChargeOnlyResultResponse>,
): ChargeResultState {
  if (result.ok) {
    switch (result.data.resultType) {
      case 'charge_only':
        return { kind: 'success', data: result.data };
      case 'charge_only_volume':
        return { kind: 'volume', data: result.data };
      case 'charge_only_unavailable':
        return { kind: 'unavailable', data: result.data };
    }
  }
  if (
    result.error.kind === 'api_error' &&
    result.error.code === PUBLIC_ERROR_CODES.CHARGE_NOT_FOUND
  ) {
    return { kind: 'not-found' };
  }
  return { kind: 'error' };
}
