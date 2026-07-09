import { Type, type Static } from '@sinclair/typebox';

/**
 * Public error code catalog.
 *
 * Every public API error response carries the flat shape
 * `{ statusCode, code, error, message, requestId }` where `code` is one of these
 * stable, machine-readable values. Codes are append-only identifiers: never rename
 * or repurpose one once published.
 *
 * Default HTTP status per code (see PUBLIC_ERROR_CODE_STATUS):
 *
 * - INVALID_REQUEST (400) — schema validation failures and other malformed-request
 *   errors (bad JSON body, unsupported media type, …).
 * - NOT_FOUND (404) — the requested route/resource path does not exist.
 * - CHARGE_NOT_FOUND (404) — the requested charge does not resolve.
 * - JUDGE_NOT_FOUND (404) — the requested judge does not resolve.
 * - CHARGE_RESULT_UNAVAILABLE (404) — the charge resolves but no publishable
 *   aggregate exists for it (unavailable-state semantics consumed by 8.1/8.2).
 * - JUDGE_SPECIFIC_RESULT_UNAVAILABLE (404) — the charge/judge pair resolves but no
 *   publishable judge-specific aggregate exists.
 * - SENTENCING_RESULT_UNAVAILABLE (404) — outcome data exists but no publishable
 *   sentencing aggregate does.
 * - RATE_LIMITED (429) — catalog entry only; no rate limiting middleware exists yet.
 * - INTERNAL_ERROR (500) — unexpected server error; the message must stay generic.
 *
 * PUBLIC_ERROR_CODE_STATUS values are DEFAULTS, not invariants: the `statusCode`
 * field in each emitted response is authoritative, and a response may legitimately
 * pair a code with a non-default status (e.g. INVALID_REQUEST with 415).
 *
 * Public error messages must stay generic: never mention parser confidence,
 * extraction, review status, raw records, docket internals, odds, predictions,
 * legal advice, or internal IDs.
 */
export const PUBLIC_ERROR_CODES = {
  INVALID_REQUEST: 'INVALID_REQUEST',
  NOT_FOUND: 'NOT_FOUND',
  CHARGE_NOT_FOUND: 'CHARGE_NOT_FOUND',
  JUDGE_NOT_FOUND: 'JUDGE_NOT_FOUND',
  CHARGE_RESULT_UNAVAILABLE: 'CHARGE_RESULT_UNAVAILABLE',
  JUDGE_SPECIFIC_RESULT_UNAVAILABLE: 'JUDGE_SPECIFIC_RESULT_UNAVAILABLE',
  SENTENCING_RESULT_UNAVAILABLE: 'SENTENCING_RESULT_UNAVAILABLE',
  RATE_LIMITED: 'RATE_LIMITED',
  INTERNAL_ERROR: 'INTERNAL_ERROR',
} as const;

export type PublicErrorCode = (typeof PUBLIC_ERROR_CODES)[keyof typeof PUBLIC_ERROR_CODES];

// Defaults, not invariants — see the module doc above.
export const PUBLIC_ERROR_CODE_STATUS: Record<PublicErrorCode, number> = {
  INVALID_REQUEST: 400,
  NOT_FOUND: 404,
  CHARGE_NOT_FOUND: 404,
  JUDGE_NOT_FOUND: 404,
  CHARGE_RESULT_UNAVAILABLE: 404,
  JUDGE_SPECIFIC_RESULT_UNAVAILABLE: 404,
  SENTENCING_RESULT_UNAVAILABLE: 404,
  RATE_LIMITED: 429,
  INTERNAL_ERROR: 500,
};

export function isPublicErrorCode(value: unknown): value is PublicErrorCode {
  return typeof value === 'string' && Object.hasOwn(PUBLIC_ERROR_CODES, value);
}

export const publicErrorCodeSchema = Type.Union(
  Object.values(PUBLIC_ERROR_CODES).map((code) => Type.Literal(code)),
);

export const publicErrorResponseSchema = Type.Object(
  {
    statusCode: Type.Integer({ minimum: 400, maximum: 599 }),
    code: publicErrorCodeSchema,
    error: Type.String(),
    message: Type.String(),
    requestId: Type.String(),
  },
  { additionalProperties: false },
);
export type PublicErrorResponse = Static<typeof publicErrorResponseSchema>;
