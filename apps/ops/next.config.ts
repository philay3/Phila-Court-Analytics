import type { NextConfig } from 'next';

// Operator-only dashboard (task STATIC-2a, relocation of apps/web/app/admin).
// No rewrites and no base-URL resolution at config load: the /admin/numbers
// route handler resolves API_BASE_URL at request time (app/lib/api-base-url.ts),
// so `next typegen` under NODE_ENV=production evaluates no guard here. This
// app is run with `next dev` only and is never built for deployment.
const nextConfig: NextConfig = {};

export default nextConfig;
