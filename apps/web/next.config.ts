import type { NextConfig } from 'next';

// http://localhost:3001 is a LOCAL-DEV DEFAULT ONLY: the API runs on 3001 and
// web on 3000, and CI's `next build` relies on this fallback. Production env
// wiring that eliminates reliance on it is Sprint 9 launch-readiness scope.
const apiBaseUrl = process.env.API_BASE_URL ?? 'http://localhost:3001';

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
