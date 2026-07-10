import type { FastifyPluginAsyncTypebox } from '@fastify/type-provider-typebox';
import { Type } from '@sinclair/typebox';
import { chargeOnlyResultResponseSchema, judgeSpecificResultResponseSchema } from '@pca/shared';
import { getChargeOnlyResult } from '../../services/charge-result.js';
import { getJudgeSpecificResult } from '../../services/judge-result.js';

const chargeResultParamsSchema = Type.Object(
  { chargeIdOrSlug: Type.String({ minLength: 1 }) },
  { additionalProperties: false },
);

const judgeResultParamsSchema = Type.Object(
  {
    chargeIdOrSlug: Type.String({ minLength: 1 }),
    judgeIdOrSlug: Type.String({ minLength: 1 }),
  },
  { additionalProperties: false },
);

export const resultRoutes: FastifyPluginAsyncTypebox = async (app) => {
  app.get(
    '/results/charge/:chargeIdOrSlug',
    {
      schema: {
        params: chargeResultParamsSchema,
        // The single 200 schema is the top-level tagged union (task 13.2a), so
        // response stripping covers the success AND unavailable arms alike —
        // aggregate-only defense in depth.
        response: { 200: chargeOnlyResultResponseSchema },
      },
    },
    async (request) => getChargeOnlyResult(() => app.getDb(), request.params.chargeIdOrSlug),
  );

  app.get(
    '/results/charge/:chargeIdOrSlug/judge/:judgeIdOrSlug',
    {
      schema: {
        params: judgeResultParamsSchema,
        // The single 200 schema is the top-level tagged union, so response
        // stripping covers the success AND unavailable arms alike.
        response: { 200: judgeSpecificResultResponseSchema },
      },
    },
    async (request) =>
      getJudgeSpecificResult(
        () => app.getDb(),
        request.params.chargeIdOrSlug,
        request.params.judgeIdOrSlug,
      ),
  );
};
