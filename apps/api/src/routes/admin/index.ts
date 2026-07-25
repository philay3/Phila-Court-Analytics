import type { FastifyPluginAsyncTypebox } from '@fastify/type-provider-typebox';
import { getOpsNumbers } from '../../services/ops-numbers.js';
import { registerOpsDb } from '../../ops-db.js';

export interface AdminRouteOptions {
  /** Ops routes register ONLY when true (ADMIN_OPS_ENABLED). Default off. */
  opsEnabled?: boolean;
  /** Optional shared secret; requests must send x-admin-ops-token when set. */
  opsToken?: string | null;
}

/**
 * Admin API namespace (/api/v1/admin).
 *
 * Phase 36 fills the shell with the operator ops surface, behind a hard env
 * gate: with `opsEnabled` false (the default, and the deployed posture) NO
 * admin route exists — unknown paths fall through to the standard 404 shape,
 * indistinguishable from any other miss. The gate is registration-time, not
 * request-time, so a misconfigured check cannot leak a route.
 *
 * The ops endpoint reads the INTERNAL layers (parsed/fact/review/raw) through
 * its own OpsDatabase handle — tables that exist only on the local canonical
 * database. It serves counts, codes, statuses, slugs, and run ids only; the
 * shape is documented on OpsNumbers (services/ops-numbers.ts). An optional
 * token adds a second factor for the local-network case; when unset, the
 * flag itself is the gate (localhost, operator machine).
 */
export const adminRoutes: FastifyPluginAsyncTypebox<AdminRouteOptions> = async (app, options) => {
  if (!options.opsEnabled) {
    return;
  }

  registerOpsDb(app);

  if (options.opsToken) {
    const expected = options.opsToken;
    app.addHook('onRequest', async (request, reply) => {
      if (request.headers['x-admin-ops-token'] !== expected) {
        return reply.status(401).send({
          statusCode: 401,
          code: 'UNAUTHORIZED',
          error: 'Unauthorized',
          message: 'Missing or incorrect x-admin-ops-token header.',
          requestId: request.id,
        });
      }
    });
  }

  app.get('/ops/numbers', async () => getOpsNumbers(app.getOpsDb()));
};
