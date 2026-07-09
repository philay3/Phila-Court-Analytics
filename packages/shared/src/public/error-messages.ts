import { PUBLIC_ERROR_CODES, type PublicErrorCode } from '../errors.js';
import {
  CHARGE_NOT_FOUND_MESSAGE,
  CHARGE_RESULT_UNAVAILABLE_MESSAGE,
  CHARGE_SENTENCING_UNAVAILABLE_MESSAGE,
} from './charge-result.js';
import { JUDGE_NOT_FOUND_MESSAGE, JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE } from './judge-result.js';

/**
 * User-facing message copy for every public error code (task 11.2). The web
 * app renders these when a client call surfaces `kind: 'api_error'`; the API's
 * own `message` field travels alongside for support use, but this map is the
 * controlled, copy-safety-scanned public wording per code.
 *
 * Five codes reference the already-pinned literals from the 8.1/8.2 contracts
 * (migrated to @pca/shared in 10.2) so there is exactly one string per
 * situation and no drift — in particular JUDGE_SPECIFIC_RESULT_UNAVAILABLE is
 * the pinned 8.2 literal by reference, never re-typed. The remaining four are
 * authored here because their codes carry no pinned contract literal.
 *
 * The `Record<PublicErrorCode, string>` annotation makes adding a tenth code
 * without a message a compile error; the key-set test pins it at runtime too.
 */
export const PUBLIC_ERROR_MESSAGES: Record<PublicErrorCode, string> = {
  [PUBLIC_ERROR_CODES.INVALID_REQUEST]:
    "That request wasn't valid. Please check your input and try again.",
  [PUBLIC_ERROR_CODES.NOT_FOUND]: "We couldn't find that page or resource.",
  [PUBLIC_ERROR_CODES.CHARGE_NOT_FOUND]: CHARGE_NOT_FOUND_MESSAGE,
  [PUBLIC_ERROR_CODES.JUDGE_NOT_FOUND]: JUDGE_NOT_FOUND_MESSAGE,
  [PUBLIC_ERROR_CODES.CHARGE_RESULT_UNAVAILABLE]: CHARGE_RESULT_UNAVAILABLE_MESSAGE,
  [PUBLIC_ERROR_CODES.JUDGE_SPECIFIC_RESULT_UNAVAILABLE]: JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE,
  [PUBLIC_ERROR_CODES.SENTENCING_RESULT_UNAVAILABLE]: CHARGE_SENTENCING_UNAVAILABLE_MESSAGE,
  [PUBLIC_ERROR_CODES.RATE_LIMITED]:
    "You've made too many requests. Please wait a moment and try again.",
  [PUBLIC_ERROR_CODES.INTERNAL_ERROR]: 'Something went wrong on our end. Please try again later.',
};

/**
 * The message shown when a client call fails in transport (network failure,
 * non-JSON body, or a malformed error payload) — the `kind: 'fetch_failed'`
 * arm of the client's tagged union. Not part of the code catalog: transport
 * failure is a client-side condition, never a fake API code. User-facing
 * public copy, so it is copy-safety-scanned alongside PUBLIC_ERROR_MESSAGES.
 */
export const FETCH_FAILURE_MESSAGE =
  "We couldn't reach the server. Please check your connection and try again.";
