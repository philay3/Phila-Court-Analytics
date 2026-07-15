import rateLimit from '@fastify/rate-limit';
import { PUBLIC_ERROR_CODES, PUBLIC_ERROR_MESSAGES } from '@pca/shared';
import type { FastifyPluginAsyncTypebox } from '@fastify/type-provider-typebox';
import { publicError } from '../../public-error.js';
import { chargeRoutes } from './charges.js';
import { dataCoverageRoutes } from './data-coverage.js';
import { definitionRoutes } from './definitions.js';
import { judgeRoutes } from './judges.js';
import { methodologyRoutes } from './methodology.js';
import { resultRoutes } from './results.js';

export interface PublicRoutesOptions {
  rateLimitMax: number;
  rateLimitWindowMs: number;
}

// Public API namespace (/api/v1/public). Aggregate-only endpoints; unknown
// paths fall through to the standard 404 shape.
//
// Rate limiting (task 31.3, ADR 0004): registered INSIDE this encapsulation
// scope, so /health and the admin namespace are structurally outside it — no
// exemption list to maintain. The key is a constant: recon proved no reliable
// client identity reaches the private API (server-side fetches carry none and
// the Next rewrite proxy adds only x-forwarded-host), so this bucket is a
// coarse global backstop for the API/DB; per-IP enforcement lives at the edge.
// The exceeded path throws a catalog-coded error (the plugin throws whatever
// errorResponseBuilder returns), so the central error handler in app.ts shapes
// the 429 like every other public error — flat catalog shape, requestId
// included; the plugin's own response body is never used.
export const publicRoutes: FastifyPluginAsyncTypebox<PublicRoutesOptions> = async (app, opts) => {
  await app.register(rateLimit, {
    max: opts.rateLimitMax,
    timeWindow: opts.rateLimitWindowMs,
    keyGenerator: () => 'global',
    errorResponseBuilder: () =>
      publicError(
        PUBLIC_ERROR_CODES.RATE_LIMITED,
        PUBLIC_ERROR_MESSAGES[PUBLIC_ERROR_CODES.RATE_LIMITED],
      ),
  });
  await app.register(chargeRoutes);
  await app.register(dataCoverageRoutes);
  await app.register(definitionRoutes);
  await app.register(judgeRoutes);
  await app.register(methodologyRoutes);
  await app.register(resultRoutes);
};
