export interface Env {
  port: number;
  host: string;
  logLevel: string;
  rateLimitMax: number;
  rateLimitWindowMs: number;
  /**
   * Phase 36 ops dashboard gate. OFF by default and off in prod: the ops
   * endpoint reads the internal layers (parsed/fact/review/raw), which exist
   * only on the local canonical database — the deployed database carries the
   * public dump/restore set alone. When false the admin ops routes are never
   * registered and the paths 404 like any unknown route.
   */
  adminOpsEnabled: boolean;
  /** Optional shared secret; when set, ops requests must send x-admin-ops-token. */
  adminOpsToken: string | null;
}

function positiveInt(name: string, raw: string | undefined, fallback: number): number {
  const value = Number(raw ?? fallback);
  if (!Number.isInteger(value) || value < 1) {
    throw new Error(`Invalid ${name}: ${raw}`);
  }
  return value;
}

export function loadEnv(): Env {
  const port = Number(process.env.PORT ?? 3001);
  if (!Number.isInteger(port) || port < 0 || port > 65535) {
    throw new Error(`Invalid PORT: ${process.env.PORT}`);
  }
  return {
    port,
    host: process.env.HOST ?? '127.0.0.1',
    logLevel: process.env.LOG_LEVEL ?? 'info',
    // Public-API rate limiting (task 31.3, ADR 0004): one shared bucket for the
    // whole private API (the edge rule owns per-IP). Env-tunable, never
    // disableable — the limiter is always registered with these values.
    rateLimitMax: positiveInt('RATE_LIMIT_MAX', process.env.RATE_LIMIT_MAX, 120),
    rateLimitWindowMs: positiveInt(
      'RATE_LIMIT_WINDOW_MS',
      process.env.RATE_LIMIT_WINDOW_MS,
      60_000,
    ),
    adminOpsEnabled:
      process.env.ADMIN_OPS_ENABLED === '1' || process.env.ADMIN_OPS_ENABLED === 'true',
    adminOpsToken:
      process.env.ADMIN_OPS_TOKEN && process.env.ADMIN_OPS_TOKEN.length > 0
        ? process.env.ADMIN_OPS_TOKEN
        : null,
  };
}
