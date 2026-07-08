import type { FastifyPluginAsyncTypebox } from '@fastify/type-provider-typebox';

// Public API namespace (/api/v1/public). Empty shell — aggregate-only endpoints
// arrive in later tasks. Unknown paths fall through to the standard 404 shape.
export const publicRoutes: FastifyPluginAsyncTypebox = async () => {};
