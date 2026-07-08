import type { FastifyPluginAsyncTypebox } from '@fastify/type-provider-typebox';

// Admin API namespace (/api/v1/admin). Empty shell — endpoints and auth arrive
// in later tasks. Unknown paths fall through to the standard 404 shape.
export const adminRoutes: FastifyPluginAsyncTypebox = async () => {};
