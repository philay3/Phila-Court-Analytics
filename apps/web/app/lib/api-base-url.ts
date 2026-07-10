/**
 * Single source of truth for the public API base URL (task 15.1 walkthrough
 * fix — Finding 2). BOTH fetch paths resolve the base through this helper so
 * they behave identically:
 *   - the Next.js rewrite in next.config.ts (browser calls, proxied same-origin)
 *   - the server-side public API client (server-component fetches)
 *
 * Before this fix only the rewrite carried the local-dev default, so with
 * API_BASE_URL absent, browser autocomplete worked while server-rendered result
 * pages failed hard — a half-working state that presented as an application bug.
 * Unifying on one default removes that asymmetry.
 *
 * `http://localhost:3001` is a LOCAL-DEV DEFAULT ONLY (the API runs on 3001, web
 * on 3000; CI's `next build` relies on it). Production env wiring that removes
 * reliance on this default is Sprint 9 launch-readiness scope — deliberately not
 * introduced here, matching the standing next.config.ts / .env.example notes.
 *
 * API_BASE_URL has no NEXT_PUBLIC_ prefix, so its real value is never inlined
 * into a client bundle: `process.env.API_BASE_URL` is only ever read server-side
 * (the client fetch path returns a relative URL and never consults the base).
 */
export const LOCAL_DEV_API_BASE_URL = 'http://localhost:3001';

export function resolveApiBaseUrl(apiBaseUrl = process.env.API_BASE_URL): string {
  return apiBaseUrl !== undefined && apiBaseUrl.length > 0 ? apiBaseUrl : LOCAL_DEV_API_BASE_URL;
}
