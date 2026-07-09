import type { FastifyInstance } from 'fastify';

export const PUBLIC_ROUTE_PREFIX = '/api/v1/public';

/**
 * Collects every public GET route pattern from a Fastify instance via an
 * `onRoute` hook. buildApp registers routes through plugins, which Fastify
 * defers until ready() — so the hook must be attached BEFORE ready() is
 * awaited, and this helper owns that ordering. Fastify's auto-registered HEAD
 * twins and everything outside the public prefix (/health, the admin
 * namespace) are dropped by the method + prefix filter.
 *
 * Returns the exact registered patterns (e.g.
 * `/api/v1/public/results/charge/:chargeIdOrSlug`), sorted and deduplicated.
 */
export async function discoverPublicGetRoutes(app: FastifyInstance): Promise<string[]> {
  const discovered = new Set<string>();
  app.addHook('onRoute', (route) => {
    // route.method is a string or an array of methods for multi-method routes.
    const methods = Array.isArray(route.method) ? route.method : [route.method];
    if (methods.includes('GET') && route.url.startsWith(PUBLIC_ROUTE_PREFIX)) {
      discovered.add(route.url);
    }
  });
  await app.ready();
  return [...discovered].sort();
}

export interface ProbeCoverage {
  /** Discovered routes with no probe registry entry — the gate must fail on these. */
  unprobed: string[];
  /** Registry entries whose route no longer exists — stale probes, symmetric failure. */
  stale: string[];
}

/**
 * Two-directional coverage check between the discovered route table and the
 * probe registry. Pure so the deliberate-failure tests can prove both
 * directions against synthetic inputs.
 */
export function checkProbeCoverage(
  discoveredRoutes: readonly string[],
  registryRoutes: readonly string[],
): ProbeCoverage {
  const registry = new Set(registryRoutes);
  const discovered = new Set(discoveredRoutes);
  return {
    unprobed: [...discovered].filter((route) => !registry.has(route)).sort(),
    stale: [...registry].filter((route) => !discovered.has(route)).sort(),
  };
}
