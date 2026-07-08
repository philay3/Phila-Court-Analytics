import { randomUUID } from 'node:crypto';
import { STATUS_CODES } from 'node:http';
import Fastify, { type FastifyError } from 'fastify';
import type { TypeBoxTypeProvider } from '@fastify/type-provider-typebox';
import { loadEnv } from './env.js';
import { healthRoutes } from './routes/health.js';
import { publicRoutes } from './routes/public/index.js';
import { adminRoutes } from './routes/admin/index.js';

export interface BuildAppOptions {
  logger?: boolean;
}

export function buildApp({ logger = true }: BuildAppOptions = {}) {
  const env = loadEnv();

  const app = Fastify({
    logger: logger ? { level: env.logLevel } : false,
    requestIdHeader: 'x-request-id',
    genReqId: () => randomUUID(),
  }).withTypeProvider<TypeBoxTypeProvider>();

  app.addHook('onRequest', async (request, reply) => {
    reply.header('x-request-id', request.id);
  });

  app.setErrorHandler<FastifyError>((error, request, reply) => {
    request.log.error({ err: error }, 'request failed');

    if (error.validation) {
      return reply.status(400).send({
        statusCode: 400,
        error: 'Bad Request',
        message: error.message,
        requestId: request.id,
      });
    }

    const statusCode =
      typeof error.statusCode === 'number' && error.statusCode >= 400 ? error.statusCode : 500;
    return reply.status(statusCode).send({
      statusCode,
      error: STATUS_CODES[statusCode] ?? 'Error',
      // Never leak internals: 5xx bodies get a generic message; details are in logs only.
      message: statusCode >= 500 ? 'Internal Server Error' : error.message,
      requestId: request.id,
    });
  });

  app.setNotFoundHandler((request, reply) => {
    reply.status(404).send({
      statusCode: 404,
      error: 'Not Found',
      message: `Route ${request.method} ${request.url} not found`,
      requestId: request.id,
    });
  });

  app.register(healthRoutes);
  app.register(publicRoutes, { prefix: '/api/v1/public' });
  app.register(adminRoutes, { prefix: '/api/v1/admin' });

  return app;
}
