import type { FastifyPluginAsyncTypebox } from '@fastify/type-provider-typebox';
import { searchIndexResponseSchema } from '@pca/shared';
import { getSearchIndex } from '../../services/search-index.js';

// Search index (task STATIC-2a). No query parameters; both availability arms
// are 200s. Serializing through the response schema strips anything outside
// the public contract — aggregate-only defense in depth (no id can leak).
export const searchIndexRoutes: FastifyPluginAsyncTypebox = async (app) => {
  app.get(
    '/search-index',
    {
      schema: {
        response: { 200: searchIndexResponseSchema },
      },
    },
    async () => getSearchIndex(app.getDb),
  );
};
