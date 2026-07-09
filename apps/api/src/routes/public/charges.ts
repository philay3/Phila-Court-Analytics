import type { FastifyPluginAsyncTypebox } from '@fastify/type-provider-typebox';
import { chargeSearchQuerySchema, chargeSearchResponseSchema } from '@pca/shared';
import { searchCharges } from '../../services/charge-search.js';

export const chargeRoutes: FastifyPluginAsyncTypebox = async (app) => {
  app.get(
    '/charges/search',
    {
      schema: {
        querystring: chargeSearchQuerySchema,
        // Serializing through the response schema strips anything outside the
        // public contract — aggregate-only defense in depth.
        response: { 200: chargeSearchResponseSchema },
      },
    },
    async (request) => {
      const { q, limit } = request.query;
      const results = await searchCharges(() => app.getDb(), q, limit ?? 10);
      return { results };
    },
  );
};
