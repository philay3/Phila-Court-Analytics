import { resolveApiBaseUrl } from './api-base-url';
import {
  isPublicErrorCode,
  type ChargeOnlyResultResponse,
  type ChargeSearchResponse,
  type DataCoverageResponse,
  type DefinitionsResponse,
  type JudgeSpecificResultResponse,
  type JudgeSearchResponse,
  type MethodologyResponse,
  type PublicErrorCode,
} from '@pca/shared';

/**
 * Public API client for apps/web (task 11.2). One module serves both
 * rendering contexts: server-side calls hit `${API_BASE_URL}` directly, while
 * browser calls use the relative `/api/v1/public/*` path and reach the API
 * through the Next.js rewrite (same-origin, no CORS). API_BASE_URL is
 * server-only — it has no NEXT_PUBLIC_ prefix, so it never enters a
 * client-delivered bundle.
 *
 * The server-side base is resolved through the shared `resolveApiBaseUrl`
 * helper (task 15.1 walkthrough Finding 2) — the SAME helper the next.config
 * rewrite uses — so both fetch paths share one local-dev default instead of the
 * server path failing hard when API_BASE_URL is unset.
 *
 * Every function returns a tagged union and never throws for expected
 * outcomes (API errors or transport failures). Success bodies are trusted
 * against the @pca/shared response types and not revalidated at runtime; only
 * the flat error envelope is validated, to decide api_error vs fetch_failed.
 */

/** A well-formed API error response, or a client-side transport failure. */
export type PublicApiFailure =
  | {
      kind: 'api_error';
      statusCode: number;
      code: PublicErrorCode;
      error: string;
      message: string;
      requestId: string;
    }
  | { kind: 'fetch_failed' };

export type PublicApiResult<T> = { ok: true; data: T } | { ok: false; error: PublicApiFailure };

const PUBLIC_API_PREFIX = '/api/v1/public';

interface UrlContext {
  isServer: boolean;
  apiBaseUrl?: string;
}

/**
 * Resolves the fetch URL for a public API path. Server-side needs an absolute
 * base; the caller now passes one resolved through `resolveApiBaseUrl` (which
 * always yields a non-empty string), so the empty-base throw here is a
 * defensive guard — an unresolved base still surfaces as fetch_failed via the
 * caller's try/catch rather than a raw crash. Browser-side returns the relative
 * path so the request rides the Next.js rewrite. Pure and directly unit-tested
 * for both branches.
 */
export function resolvePublicApiUrl(path: string, ctx: UrlContext): string {
  if (!ctx.isServer) {
    return path;
  }
  if (!ctx.apiBaseUrl) {
    throw new Error('API_BASE_URL is not set: server-side public API calls require it.');
  }
  return `${ctx.apiBaseUrl}${path}`;
}

const FETCH_FAILED: PublicApiResult<never> = { ok: false, error: { kind: 'fetch_failed' } };

/**
 * True only for an object carrying the exact flat public error envelope with a
 * catalog code. Anything else (non-object, missing/mistyped field, unknown
 * code) is a malformed error payload → fetch_failed.
 */
function toApiError(body: unknown): PublicApiFailure | null {
  if (typeof body !== 'object' || body === null) {
    return null;
  }
  const envelope = body as Record<string, unknown>;
  if (
    typeof envelope.statusCode === 'number' &&
    isPublicErrorCode(envelope.code) &&
    typeof envelope.error === 'string' &&
    typeof envelope.message === 'string' &&
    typeof envelope.requestId === 'string'
  ) {
    return {
      kind: 'api_error',
      statusCode: envelope.statusCode,
      code: envelope.code,
      error: envelope.error,
      message: envelope.message,
      requestId: envelope.requestId,
    };
  }
  return null;
}

async function fetchPublic<T>(path: string): Promise<PublicApiResult<T>> {
  let response: Response;
  try {
    const isServer = typeof window === 'undefined';
    // Only the server path consults the base URL; the browser path returns a
    // relative URL and rides the rewrite, so the base is resolved server-side
    // only (keeping the resolution — and its env read — off the client path).
    const url = resolvePublicApiUrl(path, {
      isServer,
      apiBaseUrl: isServer ? resolveApiBaseUrl() : undefined,
    });
    response = await fetch(url, { headers: { accept: 'application/json' } });
  } catch {
    // Network failure, DNS failure, aborted request, or missing base URL.
    return FETCH_FAILED;
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    // Non-JSON body on either a success or an error status.
    return FETCH_FAILED;
  }

  if (!response.ok) {
    const apiError = toApiError(body);
    return apiError ? { ok: false, error: apiError } : FETCH_FAILED;
  }

  // Success body is trusted against the shared response type (no revalidation).
  return { ok: true, data: body as T };
}

function buildQuery(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) {
      search.set(key, String(value));
    }
  }
  const query = search.toString();
  return query ? `?${query}` : '';
}

export function searchCharges(
  q: string,
  limit?: number,
): Promise<PublicApiResult<ChargeSearchResponse>> {
  return fetchPublic(`${PUBLIC_API_PREFIX}/charges/search${buildQuery({ q, limit })}`);
}

export function searchJudges(
  q: string,
  limit?: number,
): Promise<PublicApiResult<JudgeSearchResponse>> {
  return fetchPublic(`${PUBLIC_API_PREFIX}/judges/search${buildQuery({ q, limit })}`);
}

export function getChargeResult(
  chargeIdOrSlug: string,
): Promise<PublicApiResult<ChargeOnlyResultResponse>> {
  return fetchPublic(`${PUBLIC_API_PREFIX}/results/charge/${encodeURIComponent(chargeIdOrSlug)}`);
}

export function getJudgeSpecificResult(
  chargeIdOrSlug: string,
  judgeIdOrSlug: string,
): Promise<PublicApiResult<JudgeSpecificResultResponse>> {
  return fetchPublic(
    `${PUBLIC_API_PREFIX}/results/charge/${encodeURIComponent(chargeIdOrSlug)}/judge/${encodeURIComponent(judgeIdOrSlug)}`,
  );
}

export function getDefinitions(): Promise<PublicApiResult<DefinitionsResponse>> {
  return fetchPublic(`${PUBLIC_API_PREFIX}/definitions`);
}

export function getMethodology(): Promise<PublicApiResult<MethodologyResponse>> {
  return fetchPublic(`${PUBLIC_API_PREFIX}/methodology`);
}

export function getDataCoverage(): Promise<PublicApiResult<DataCoverageResponse>> {
  return fetchPublic(`${PUBLIC_API_PREFIX}/data-coverage`);
}
