import type { FastifyPluginAsyncTypebox } from '@fastify/type-provider-typebox';
import {
  SEARCH_LIMIT_DEFAULT,
  chargeDirectoryResponseSchema,
  chargeSearchQuerySchema,
  chargeSearchResponseSchema,
} from '@pca/shared';
import { getChargeDirectory } from '../../services/charge-directory.js';
import { searchCharges } from '../../services/charge-search.js';

export const chargeRoutes: FastifyPluginAsyncTypebox = async (app) => {
  // Directory list (task DP-4). No query parameters; both availability arms
  // are 200s. Serializing through the response schema strips anything outside
  // the public contract — aggregate-only defense in depth.
  app.get(
    '/charges',
    {
      schema: {
        response: { 200: chargeDirectoryResponseSchema },
      },
    },
    async () => getChargeDirectory(app.getDb),
  );

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
      const results = await searchCharges(() => app.getDb(), q, limit ?? SEARCH_LIMIT_DEFAULT);
      return { results };
    },
  );
};
