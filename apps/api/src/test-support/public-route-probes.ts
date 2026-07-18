import { PUBLIC_ROUTE_PREFIX } from './public-route-discovery.js';

/**
 * The single public endpoint inventory, shared by the 10.1 forbidden-field
 * suite and the 10.2 copy-safety suite so the two gates can never drift to
 * different endpoint lists. The 10.1 suite's discovery/coverage assertions
 * enforce that this registry matches the live route table in both directions.
 */

export interface PublicRouteProbe {
  /** Arm label, e.g. 'success', 'thin-data', '200-unavailable', '404-charge'. */
  name: string;
  /** Concrete request path (including query string) against globalSetup-seeded data. */
  path: string;
  /** Sanity check that the probe still hits the arm it claims; bodies are scanned regardless. */
  expectedStatus: number;
}

// Keyed by the EXACT Fastify route pattern as registered (prefix included).
// Probe targets are globalSetup-seeded slugs only (vitest.global-setup.ts);
// consuming suites never insert or delete rows. Arm choices mirror the seeded
// facts the 8.1/8.2/13.2a suites verify: possession-controlled-substance has
// no sentencing rows, harassment has no aggregate rows at all (charge-only
// unavailable), retail-theft + judge-fakename-example has no judge-specific
// aggregate, criminal-trespass and simple-assault + judge-testina-placeholder
// are the thin-data cases. The search routes have
// no 404/unavailable arms, so their error coverage is the 400
// validation-error arm (central error handler output must be scanned too).
export const PROBE_REGISTRY: Readonly<Record<string, readonly PublicRouteProbe[]>> = {
  [`${PUBLIC_ROUTE_PREFIX}/charges`]: [
    // The unavailable arm requires invalidating the seeded run, which probes
    // never do (no-mutation rule above); it is scanned by the DP-4 route
    // suite's rollback-isolated test instead.
    { name: 'success', path: `${PUBLIC_ROUTE_PREFIX}/charges`, expectedStatus: 200 },
  ],
  [`${PUBLIC_ROUTE_PREFIX}/charges/search`]: [
    { name: 'success', path: `${PUBLIC_ROUTE_PREFIX}/charges/search?q=theft`, expectedStatus: 200 },
    {
      name: 'empty-results',
      path: `${PUBLIC_ROUTE_PREFIX}/charges/search?q=zzz-no-such-charge`,
      expectedStatus: 200,
    },
    {
      name: '400-missing-q',
      path: `${PUBLIC_ROUTE_PREFIX}/charges/search`,
      expectedStatus: 400,
    },
  ],
  [`${PUBLIC_ROUTE_PREFIX}/judges/search`]: [
    { name: 'success', path: `${PUBLIC_ROUTE_PREFIX}/judges/search?q=judge`, expectedStatus: 200 },
    {
      name: 'empty-results',
      path: `${PUBLIC_ROUTE_PREFIX}/judges/search?q=zzz-no-such-judge`,
      expectedStatus: 200,
    },
    {
      name: '400-missing-q',
      path: `${PUBLIC_ROUTE_PREFIX}/judges/search`,
      expectedStatus: 400,
    },
  ],
  [`${PUBLIC_ROUTE_PREFIX}/results/charge/:chargeIdOrSlug`]: [
    {
      name: 'success',
      path: `${PUBLIC_ROUTE_PREFIX}/results/charge/retail-theft`,
      expectedStatus: 200,
    },
    {
      name: 'thin-data',
      path: `${PUBLIC_ROUTE_PREFIX}/results/charge/criminal-trespass`,
      expectedStatus: 200,
    },
    {
      name: '200-sentencing-unavailable',
      path: `${PUBLIC_ROUTE_PREFIX}/results/charge/possession-controlled-substance`,
      expectedStatus: 200,
    },
    {
      // Charge exists (seeded) but has zero aggregate rows → the 13.2a HTTP
      // 200 charge-only unavailable arm.
      name: '200-charge-unavailable',
      path: `${PUBLIC_ROUTE_PREFIX}/results/charge/harassment`,
      expectedStatus: 200,
    },
    {
      name: '404-charge-not-found',
      path: `${PUBLIC_ROUTE_PREFIX}/results/charge/no-such-charge`,
      expectedStatus: 404,
    },
  ],
  [`${PUBLIC_ROUTE_PREFIX}/results/charge/:chargeIdOrSlug/judge/:judgeIdOrSlug`]: [
    {
      name: 'success',
      path: `${PUBLIC_ROUTE_PREFIX}/results/charge/retail-theft/judge/judge-testina-placeholder`,
      expectedStatus: 200,
    },
    {
      name: 'thin-data',
      path: `${PUBLIC_ROUTE_PREFIX}/results/charge/simple-assault/judge/judge-testina-placeholder`,
      expectedStatus: 200,
    },
    {
      name: '200-judge-unavailable',
      path: `${PUBLIC_ROUTE_PREFIX}/results/charge/retail-theft/judge/judge-fakename-example`,
      expectedStatus: 200,
    },
    {
      name: '404-charge-not-found',
      path: `${PUBLIC_ROUTE_PREFIX}/results/charge/no-such-charge/judge/judge-testina-placeholder`,
      expectedStatus: 404,
    },
    {
      name: '404-judge-not-found',
      path: `${PUBLIC_ROUTE_PREFIX}/results/charge/retail-theft/judge/no-such-judge`,
      expectedStatus: 404,
    },
  ],
  [`${PUBLIC_ROUTE_PREFIX}/definitions`]: [
    { name: 'success', path: `${PUBLIC_ROUTE_PREFIX}/definitions`, expectedStatus: 200 },
  ],
  [`${PUBLIC_ROUTE_PREFIX}/methodology`]: [
    { name: 'success', path: `${PUBLIC_ROUTE_PREFIX}/methodology`, expectedStatus: 200 },
  ],
  [`${PUBLIC_ROUTE_PREFIX}/data-coverage`]: [
    { name: 'success', path: `${PUBLIC_ROUTE_PREFIX}/data-coverage`, expectedStatus: 200 },
  ],
};
