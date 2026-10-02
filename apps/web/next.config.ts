import type { NextConfig } from 'next';
import { resolveApiBaseUrl } from './app/lib/api-base-url';

// Export mode (task STATIC-2b, pin 12): PCA_STATIC_EXPORT=1 — set by the static
// build script (apps/api/src/static-build) for its own `next build` — turns on
// `output: 'export'`. Without it (next dev, next typegen) the config keeps the
// server shape, so local development works unchanged.
//
// Rewrites are not applied under export (Next warns and ignores them), so they
// are returned only outside it. The local-dev default base lives in ONE place
// (app/lib/api-base-url) so the rewrite and the server-side client resolve it
// identically; under the static build API_BASE_URL is the throwaway server.
const staticExport = process.env.PCA_STATIC_EXPORT === '1';
const apiBaseUrl = resolveApiBaseUrl();

const nextConfig: NextConfig = {
  ...(staticExport ? { output: 'export' as const } : {}),
  async rewrites() {
    if (staticExport) {
      return [];
    }
    return [
      // Dev only: the client-side comboboxes read the search index from the
      // export's data-file path; under `next dev` the API serves it.
      {
        source: '/data/search-index.json',
        destination: `${apiBaseUrl}/api/v1/public/search-index`,
      },
      // Legacy same-origin proxy for the browser (retired in STATIC-2b commit 2).
      {
        source: '/api/v1/public/:path*',
        destination: `${apiBaseUrl}/api/v1/public/:path*`,
      },
    ];
  },
};

export default nextConfig;
