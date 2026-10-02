import { resolveApiBaseUrl } from '../../lib/api-base-url';

/**
 * Same-origin proxy for the Phase 36 ops feed. The dashboard is a client
 * component polling THIS route; the hop to the private API happens here,
 * server-side, through the same base-URL resolution every other server-side
 * fetch uses — no CORS surface, and ADMIN_OPS_TOKEN (when set) stays
 * server-only. When the API's gate is off, its standard 404 passes through
 * and the dashboard renders its disabled state.
 */
export const dynamic = 'force-dynamic';

export async function GET(): Promise<Response> {
  const base = resolveApiBaseUrl();
  const token = process.env.ADMIN_OPS_TOKEN;
  try {
    const upstream = await fetch(`${base}/api/v1/admin/ops/numbers`, {
      cache: 'no-store',
      headers: token ? { 'x-admin-ops-token': token } : undefined,
    });
    const body = await upstream.text();
    return new Response(body, {
      status: upstream.status,
      headers: { 'content-type': 'application/json' },
    });
  } catch {
    return Response.json({ error: 'api_unreachable' }, { status: 502 });
  }
}
