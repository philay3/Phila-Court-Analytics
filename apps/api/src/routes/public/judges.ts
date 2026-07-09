import type { FastifyPluginAsyncTypebox } from '@fastify/type-provider-typebox';
import {
  SEARCH_LIMIT_DEFAULT,
  judgeSearchQuerySchema,
  judgeSearchResponseSchema,
} from '@pca/shared';
import { searchJudges } from '../../services/judge-search.js';

export const judgeRoutes: FastifyPluginAsyncTypebox = async (app) => {
  app.get(
    '/judges/search',
    {
      schema: {
        querystring: judgeSearchQuerySchema,
        // Serializing through the response schema strips anything outside the
        // public contract — aggregate-only defense in depth.
        response: { 200: judgeSearchResponseSchema },
      },
    },
    async (request) => {
      const { q, limit } = request.query;
      const results = await searchJudges(() => app.getDb(), q, limit ?? SEARCH_LIMIT_DEFAULT);
      return { results };
    },
  );
};
