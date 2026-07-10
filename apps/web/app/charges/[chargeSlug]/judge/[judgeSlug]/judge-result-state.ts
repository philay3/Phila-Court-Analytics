import {
  PUBLIC_ERROR_CODES,
  type JudgeSpecificResultResponse,
  type JudgeSpecificResultSuccess,
  type JudgeSpecificResultUnavailable,
} from '@pca/shared';
import type { PublicApiResult } from '../../../../lib/public-api-client';

/**
 * Pure branch resolver for the judge-specific result page (task 13.3). Maps the
 * 11.2 client's typed result to the states the page renders, so the server
 * component stays a thin dispatcher and the detection logic is unit-tested here
 * (page.tsx itself is exempt from direct tests, mirroring 13.2).
 *
 * The state space:
 *   - success      → HTTP 200 `judge_specific` arm; render the result view.
 *   - unavailable  → HTTP 200 `judge_specific_unavailable` arm; render the
 *                    in-page unavailable view. The charge and judge both exist
 *                    but no judge-specific aggregate does. This is NEVER an
 *                    api_error — the contract carries it as a 200 arm so the
 *                    charge-only fallback travels with the identity.
 *   - not-found    → CHARGE_NOT_FOUND or JUDGE_NOT_FOUND api_error; the page
 *                    renders the in-page not-found view with the matching pinned
 *                    literal. `reason` selects which of the two distinct
 *                    @pca/shared messages is shown.
 *   - error        → any other api_error code or a transport failure; the page
 *                    throws so error.tsx renders generic, detail-free copy.
 *
 * Sentencing-unavailable is NOT modeled here: each scope's sentencing block is
 * an in-payload arm of a success response (`sentencing.available === false`)
 * handled inside the view, independently for the judge and baseline slots.
 */
export type JudgeResultState =
  | { kind: 'success'; data: JudgeSpecificResultSuccess }
  | { kind: 'unavailable'; data: JudgeSpecificResultUnavailable }
  | { kind: 'not-found'; reason: 'charge' | 'judge' }
  | { kind: 'error' };

export function resolveJudgeResultState(
  result: PublicApiResult<JudgeSpecificResultResponse>,
): JudgeResultState {
  if (result.ok) {
    return result.data.resultType === 'judge_specific'
      ? { kind: 'success', data: result.data }
      : { kind: 'unavailable', data: result.data };
  }
  if (result.error.kind === 'api_error') {
    if (result.error.code === PUBLIC_ERROR_CODES.CHARGE_NOT_FOUND) {
      return { kind: 'not-found', reason: 'charge' };
    }
    if (result.error.code === PUBLIC_ERROR_CODES.JUDGE_NOT_FOUND) {
      return { kind: 'not-found', reason: 'judge' };
    }
  }
  return { kind: 'error' };
}
