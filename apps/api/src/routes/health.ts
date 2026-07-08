import { Type } from '@sinclair/typebox';
import type { FastifyPluginAsyncTypebox } from '@fastify/type-provider-typebox';

const healthResponseSchema = Type.Object({
  status: Type.Literal('ok'),
  uptime: Type.Number(),
});

export const healthRoutes: FastifyPluginAsyncTypebox = async (app) => {
  app.get(
    '/health',
    { schema: { response: { 200: healthResponseSchema } } },
    async () => ({ status: 'ok' as const, uptime: process.uptime() }),
  );
};
