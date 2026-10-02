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
 * on 3000). Everywhere else the default is a hazard, not a convenience. Since
 * task STATIC-2b the production shape is a static export: the build script
 * (apps/api/src/static-build) materializes the API responses, serves them on a
 * throwaway local server, and sets API_BASE_URL to it for `next build` — a
 * silent localhost fallback would bake fetch failures into the export. So
 * under NODE_ENV === 'production' an unset or empty API_BASE_URL THROWS (task
 * 31.3, ADR 0004). next.config.ts resolves the base at config load, which makes
 * the throw a `next build` failure — misconfiguration can never reach an
 * upload. Note Next.js defaults NODE_ENV to 'production' for
 * every CLI command except `next dev` (including `next typegen`), so local
 * production builds and typechecking also require API_BASE_URL — see
 * apps/web/.env.example and docs/local-setup.md.
 *
 * API_BASE_URL has no NEXT_PUBLIC_ prefix, so its real value is never inlined
 * into a client bundle: `process.env.API_BASE_URL` is only ever read server-side
 * (the client fetch path returns a relative URL and never consults the base).
 */
export const LOCAL_DEV_API_BASE_URL = 'http://localhost:3001';

export function resolveApiBaseUrl(apiBaseUrl = process.env.API_BASE_URL): string {
  if (apiBaseUrl !== undefined && apiBaseUrl.length > 0) {
    return apiBaseUrl;
  }
  if (process.env.NODE_ENV === 'production') {
    throw new Error(
      'API_BASE_URL is required in production and was unset or empty. Under the ' +
        "static build it is the address of the build script's throwaway API " +
        'server (apps/api/src/static-build sets it for its `next build`); under ' +
        '`next start` it is the API address. The http://localhost:3001 fallback ' +
        'is local-dev only (`next dev`) and is deliberately disabled here so a ' +
        'misconfiguration fails at build instead of silently pointing at ' +
        'localhost.',
    );
  }
  return LOCAL_DEV_API_BASE_URL;
}
