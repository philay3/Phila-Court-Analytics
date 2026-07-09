import type { PublicErrorCode } from '@pca/shared';

/**
 * Domain errors carry a catalog code and nothing else — the central error
 * handler in app.ts resolves the status and shapes the response. Route and
 * service code must never build error bodies. 4xx messages are echoed to
 * clients, so keep them generic (see the @pca/shared errors module doc).
 */
export function publicError(code: PublicErrorCode, message: string): Error {
  return Object.assign(new Error(message), { code });
}
