import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import type { FastifyPluginAsyncTypebox } from '@fastify/type-provider-typebox';
import { buildApp } from './app.js';
import { formatViolations, scanForForbidden } from '@pca/shared/forbidden-scan';
import {
  PUBLIC_ROUTE_PREFIX,
  checkProbeCoverage,
  discoverPublicGetRoutes,
} from './test-support/public-route-discovery.js';
import { PROBE_REGISTRY } from './test-support/public-route-probes.js';

// Public forbidden-field gate (task 10.1). Every public GET route is
// discovered from the live route table, probed across its response arms, and
// every response body — success, thin-data, 200-unavailable, and error alike
// — is deep-scanned against the @pca/shared forbidden stems and value
// patterns. Coverage is enforced in both directions: an unprobed route fails,
// and a probe for a vanished route fails. The probe registry itself lives in
// test-support/public-route-probes.ts, shared with the 10.2 copy-safety
// suite (task 10.2) so the two gates cannot drift to different endpoint
// lists — this suite's coverage assertions police the shared registry.

const hasDb = Boolean(process.env.DATABASE_URL);
if (!hasDb) {
  console.warn(
    'DATABASE_URL not set — skipping forbidden-field probe execution. ' +
      'Start Postgres (pnpm db:up), apply migrations (pnpm db:migrate:latest), ' +
      'and create the root .env (cp .env.example .env).',
  );
}

// Route discovery needs no database: buildApp's DB handle is lazy and probes
// are not executed here. These assertions therefore ALWAYS run.
describe('public route discovery and probe coverage', () => {
  let discoveredRoutes: string[];

  beforeAll(async () => {
    const app = buildApp({ logger: false });
    try {
      discoveredRoutes = await discoverPublicGetRoutes(app);
    } finally {
      await app.close();
    }
  });

  it('discovers exactly the expected number of public GET routes', () => {
    // This count assertion exists to make silent discovery breakage visible:
    // if the onRoute hook, the prefix filter, or plugin registration ever
    // stops seeing routes, coverage checks against an EMPTY discovered set
    // would pass vacuously. Update the number when a public route is
    // deliberately added or removed — the diff is the review trail.
    expect(discoveredRoutes).toHaveLength(8);
  });

  it('has at least one probe for every discovered route (no unprobed routes)', () => {
    const { unprobed } = checkProbeCoverage(discoveredRoutes, Object.keys(PROBE_REGISTRY));
    expect(
      unprobed,
      `public routes with ZERO probes — add PROBE_REGISTRY entries for:\n  ${unprobed.join('\n  ')}`,
    ).toEqual([]);
  });

  it('has no stale registry entries for routes that no longer exist', () => {
    const { stale } = checkProbeCoverage(discoveredRoutes, Object.keys(PROBE_REGISTRY));
    expect(
      stale,
      `PROBE_REGISTRY references routes that are no longer registered — remove or fix:\n  ${stale.join('\n  ')}`,
    ).toEqual([]);
  });

  it('every registry entry has at least one probe request', () => {
    for (const [route, probes] of Object.entries(PROBE_REGISTRY)) {
      expect(probes.length, `route ${route} has an empty probe list`).toBeGreaterThan(0);
    }
  });
});

describe('coverage-check failure modes (deliberate-failure proofs)', () => {
  it('reports a throwaway public route as unprobed', async () => {
    const app = buildApp({ logger: false });
    try {
      const throwawayRoutes: FastifyPluginAsyncTypebox = async (instance) => {
        instance.get('/zz-throwaway-coverage-probe', async () => ({ ok: true }));
      };
      app.register(throwawayRoutes, { prefix: PUBLIC_ROUTE_PREFIX });
      const discovered = await discoverPublicGetRoutes(app);

      const { unprobed } = checkProbeCoverage(discovered, Object.keys(PROBE_REGISTRY));
      expect(unprobed).toEqual([`${PUBLIC_ROUTE_PREFIX}/zz-throwaway-coverage-probe`]);
    } finally {
      await app.close();
    }
  });

  it('reports a registry entry for a nonexistent route as stale', async () => {
    const app = buildApp({ logger: false });
    try {
      const discovered = await discoverPublicGetRoutes(app);
      const { stale } = checkProbeCoverage(discovered, [
        ...Object.keys(PROBE_REGISTRY),
        `${PUBLIC_ROUTE_PREFIX}/zz-removed-endpoint`,
      ]);
      expect(stale).toEqual([`${PUBLIC_ROUTE_PREFIX}/zz-removed-endpoint`]);
    } finally {
      await app.close();
    }
  });
});

// Fix 4: the privacy gate must never be skippable in CI. Locally, a missing
// DATABASE_URL downgrades probe execution to a skip (with the warning above);
// in CI the database is provisioned by the workflow, so its absence means the
// gate would silently pass without scanning a single response. This test
// always runs — no skipIf — and turns that misconfiguration into a failure.
describe('CI gate integrity', () => {
  it('fails loudly when CI is set but the database is unavailable', () => {
    if (process.env.CI) {
      expect(
        hasDb,
        'DATABASE_URL is not set in CI: the public forbidden-field gate cannot run its probes. ' +
          'This gate must never be skipped in CI — fix the workflow database service before merging.',
      ).toBe(true);
    }
  });
});

describe.skipIf(!hasDb)('forbidden-field scan of every public route arm', () => {
  let app: ReturnType<typeof buildApp>;

  beforeAll(async () => {
    app = buildApp({ logger: false });
    await app.ready();
  });

  afterAll(async () => {
    await app?.close();
  });

  for (const [route, probes] of Object.entries(PROBE_REGISTRY)) {
    describe(route, () => {
      for (const probe of probes) {
        it(`${probe.name}: body is free of forbidden keys and values`, async () => {
          const res = await app.inject({ method: 'GET', url: probe.path });
          expect(res.statusCode, `probe '${probe.name}' (${probe.path}) drifted off its arm`).toBe(
            probe.expectedStatus,
          );

          const violations = scanForForbidden(res.json());
          expect(
            violations,
            `forbidden content in ${route} [probe '${probe.name}' → ${probe.path}]:\n` +
              formatViolations(violations),
          ).toEqual([]);
        });
      }
    });
  }
});
