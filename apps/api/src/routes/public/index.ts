import type { FastifyPluginAsyncTypebox } from '@fastify/type-provider-typebox';
import { chargeRoutes } from './charges.js';
import { definitionRoutes } from './definitions.js';
import { judgeRoutes } from './judges.js';
import { resultRoutes } from './results.js';

// Public API namespace (/api/v1/public). Aggregate-only endpoints; unknown
// paths fall through to the standard 404 shape.
export const publicRoutes: FastifyPluginAsyncTypebox = async (app) => {
  await app.register(chargeRoutes);
  await app.register(definitionRoutes);
  await app.register(judgeRoutes);
  await app.register(resultRoutes);
};
