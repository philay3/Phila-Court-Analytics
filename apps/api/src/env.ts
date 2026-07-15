export interface Env {
  port: number;
  host: string;
  logLevel: string;
  rateLimitMax: number;
  rateLimitWindowMs: number;
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
  };
}
