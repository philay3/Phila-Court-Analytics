import type { FastifyPluginAsyncTypebox } from '@fastify/type-provider-typebox';
import { methodologyResponseSchema } from '@pca/shared';
import { METHODOLOGY_CONTENT } from '../../content/methodology.js';

// Served straight from the content module — static per deploy, no database
// access anywhere in the handler chain (9.1 pattern). Serializing through
// the response schema strips anything outside the public contract.
export const methodologyRoutes: FastifyPluginAsyncTypebox = async (app) => {
  app.get(
    '/methodology',
    {
      schema: {
        response: { 200: methodologyResponseSchema },
      },
    },
    async () => METHODOLOGY_CONTENT,
  );
};
