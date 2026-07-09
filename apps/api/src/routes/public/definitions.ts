import type { FastifyPluginAsyncTypebox } from '@fastify/type-provider-typebox';
import { TAXONOMY_VERSION } from '@pca/taxonomy';
import { definitionsResponseSchema } from '@pca/shared';
import { PUBLIC_DEFINITIONS } from '../../taxonomy.js';

// Served straight from the @pca/taxonomy generated artifact — static per
// deploy, no database access anywhere in the handler chain.
export const definitionRoutes: FastifyPluginAsyncTypebox = async (app) => {
  app.get(
    '/definitions',
    {
      schema: {
        // Serializing through the response schema strips anything outside the
        // public contract — aggregate-only defense in depth.
        response: { 200: definitionsResponseSchema },
      },
    },
    async () => ({
      taxonomyVersion: TAXONOMY_VERSION,
      outcomes: PUBLIC_DEFINITIONS.outcomes,
      sentencing: PUBLIC_DEFINITIONS.sentencing,
    }),
  );
};
