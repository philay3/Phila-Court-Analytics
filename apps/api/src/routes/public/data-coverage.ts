import type { FastifyPluginAsyncTypebox } from '@fastify/type-provider-typebox';
import { dataCoverageResponseSchema } from '@pca/shared';
import { getDataCoverage } from '../../services/data-coverage.js';

// Both coverage arms are 200s; serializing through the response schema
// strips anything outside the public contract — aggregate-only defense in
// depth on top of the count-only repository.
export const dataCoverageRoutes: FastifyPluginAsyncTypebox = async (app) => {
  app.get(
    '/data-coverage',
    {
      schema: {
        response: { 200: dataCoverageResponseSchema },
      },
    },
    async () => getDataCoverage(app.getDb),
  );
};
