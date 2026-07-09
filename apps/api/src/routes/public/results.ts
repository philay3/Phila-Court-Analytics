import type { FastifyPluginAsyncTypebox } from '@fastify/type-provider-typebox';
import { Type } from '@sinclair/typebox';
import { chargeOnlyResultResponseSchema } from '@pca/shared';
import { getChargeOnlyResult } from '../../services/charge-result.js';

const chargeResultParamsSchema = Type.Object(
  { chargeIdOrSlug: Type.String({ minLength: 1 }) },
  { additionalProperties: false },
);

export const resultRoutes: FastifyPluginAsyncTypebox = async (app) => {
  app.get(
    '/results/charge/:chargeIdOrSlug',
    {
      schema: {
        params: chargeResultParamsSchema,
        // Serializing through the response schema strips anything outside the
        // public contract — aggregate-only defense in depth.
        response: { 200: chargeOnlyResultResponseSchema },
      },
    },
    async (request) => getChargeOnlyResult(() => app.getDb(), request.params.chargeIdOrSlug),
  );
};
