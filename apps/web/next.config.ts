import type { NextConfig } from 'next';
import { resolveApiBaseUrl } from './app/lib/api-base-url';

// The local-dev default lives in ONE place (app/lib/api-base-url) so this
// rewrite and the server-side client resolve the base identically. See that
// module for why: http://localhost:3001 is a LOCAL-DEV DEFAULT ONLY (API on
// 3001, web on 3000; CI's `next build` relies on it), and removing reliance on
// it is Sprint 9 launch-readiness scope.
const apiBaseUrl = resolveApiBaseUrl();

const nextConfig: NextConfig = {
  // Keep browser calls same-origin: /api/v1/public/* is proxied to the API,
  // so no API URL is shipped to the client and no CORS layer is needed.
  async rewrites() {
    return [
      {
        source: '/api/v1/public/:path*',
        destination: `${apiBaseUrl}/api/v1/public/:path*`,
      },
    ];
  },
};

export default nextConfig;
