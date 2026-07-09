import { randomUUID } from 'node:crypto';
import { STATUS_CODES } from 'node:http';
import Fastify, { type FastifyError } from 'fastify';
import type { TypeBoxTypeProvider } from '@fastify/type-provider-typebox';
import {
  PUBLIC_ERROR_CODES,
  PUBLIC_ERROR_CODE_STATUS,
  isPublicErrorCode,
  registerFormats,
  type PublicErrorResponse,
} from '@pca/shared';
import type { Kysely } from 'kysely';
import { loadEnv } from './env.js';
import { registerDb, type PublicApiDatabase } from './db.js';
import { healthRoutes } from './routes/health.js';
import { publicRoutes } from './routes/public/index.js';
import { adminRoutes } from './routes/admin/index.js';

export interface BuildAppOptions {
  logger?: boolean;
  /** Injected database handle (tests); when omitted one is created lazily from DATABASE_URL. */
  db?: Kysely<PublicApiDatabase>;
}

export function buildApp({ logger = true, db }: BuildAppOptions = {}) {
  // TypeBox rejects any value against a `format` it has no registered checker for, so
  // formats must exist before any schema is compiled. (Request validation itself runs
  // through Fastify's Ajv, which bundles ajv-formats; this covers the TypeBox path.)
  registerFormats();

  const env = loadEnv();

  const app = Fastify({
    logger: logger ? { level: env.logLevel } : false,
    requestIdHeader: 'x-request-id',
    genReqId: () => randomUUID(),
  }).withTypeProvider<TypeBoxTypeProvider>();

  registerDb(app, db);

  app.addHook('onRequest', async (request, reply) => {
    reply.header('x-request-id', request.id);
  });

  app.setErrorHandler<FastifyError>((error, request, reply) => {
    request.log.error({ err: error }, 'request failed');

    if (error.validation) {
      return reply.status(400).send({
        statusCode: 400,
        code: PUBLIC_ERROR_CODES.INVALID_REQUEST,
        error: 'Bad Request',
        message: error.message,
        requestId: request.id,
      } satisfies PublicErrorResponse);
    }

    // Domain errors thrown with a catalog code (the 7.2+ plumbing): the code's default
    // status applies unless the error carries an explicit error status of its own.
    if (isPublicErrorCode(error.code)) {
      const statusCode =
        typeof error.statusCode === 'number' && error.statusCode >= 400
          ? error.statusCode
          : PUBLIC_ERROR_CODE_STATUS[error.code];
      return reply.status(statusCode).send({
        statusCode,
        code: error.code,
        error: STATUS_CODES[statusCode] ?? 'Error',
        message: statusCode >= 500 ? 'Internal Server Error' : error.message,
        requestId: request.id,
      } satisfies PublicErrorResponse);
    }

    const statusCode =
      typeof error.statusCode === 'number' && error.statusCode >= 400 ? error.statusCode : 500;
    return reply.status(statusCode).send({
      statusCode,
      code:
        statusCode >= 500 ? PUBLIC_ERROR_CODES.INTERNAL_ERROR : PUBLIC_ERROR_CODES.INVALID_REQUEST,
      error: STATUS_CODES[statusCode] ?? 'Error',
      // Never leak internals: 5xx bodies get a generic message; details are in logs only.
      message: statusCode >= 500 ? 'Internal Server Error' : error.message,
      requestId: request.id,
    } satisfies PublicErrorResponse);
  });

  app.setNotFoundHandler((request, reply) => {
    reply.status(404).send({
      statusCode: 404,
      code: PUBLIC_ERROR_CODES.NOT_FOUND,
      error: 'Not Found',
      message: `Route ${request.method} ${request.url} not found`,
      requestId: request.id,
    } satisfies PublicErrorResponse);
  });

  app.register(healthRoutes);
  app.register(publicRoutes, { prefix: '/api/v1/public' });
  app.register(adminRoutes, { prefix: '/api/v1/admin' });

  return app;
}
