import { PUBLIC_ERROR_CODES, PUBLIC_ERROR_MESSAGES } from '@pca/shared';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { buildApp } from './app.js';
import { loadEnv } from './env.js';

/**
 * Rate limiting acceptance suite (task 31.3, ADR 0004). The limiter is
 * always registered; tests tune it exactly the way production does — via
 * RATE_LIMIT_MAX / RATE_LIMIT_WINDOW_MS read by loadEnv() at buildApp() time.
 * Probes use /definitions (static content, no DB) so no database is needed.
 */

afterEach(() => {
  vi.unstubAllEnvs();
});

function buildLimitedApp(max: number) {
  vi.stubEnv('RATE_LIMIT_MAX', String(max));
  return buildApp({ logger: false });
}

describe('loadEnv rate-limit configuration', () => {
  it('defaults to the ruled thresholds (120 requests per 60s window)', () => {
    const env = loadEnv();
    expect(env.rateLimitMax).toBe(120);
    expect(env.rateLimitWindowMs).toBe(60_000);
  });

  it('reads RATE_LIMIT_MAX and RATE_LIMIT_WINDOW_MS from the environment', () => {
    vi.stubEnv('RATE_LIMIT_MAX', '7');
    vi.stubEnv('RATE_LIMIT_WINDOW_MS', '1000');
    const env = loadEnv();
    expect(env.rateLimitMax).toBe(7);
    expect(env.rateLimitWindowMs).toBe(1000);
  });

  it('rejects non-integer and non-positive values loudly', () => {
    vi.stubEnv('RATE_LIMIT_MAX', 'lots');
    expect(() => loadEnv()).toThrowError(/Invalid RATE_LIMIT_MAX/);
    vi.unstubAllEnvs();

    vi.stubEnv('RATE_LIMIT_WINDOW_MS', '0');
    expect(() => loadEnv()).toThrowError(/Invalid RATE_LIMIT_WINDOW_MS/);
  });
});

describe('public API rate limiting', () => {
  it('returns the flat catalog RATE_LIMITED shape through the central handler', async () => {
    const app = buildLimitedApp(2);

    expect((await app.inject({ url: '/api/v1/public/definitions' })).statusCode).toBe(200);
    expect((await app.inject({ url: '/api/v1/public/definitions' })).statusCode).toBe(200);

    const limited = await app.inject({ url: '/api/v1/public/definitions' });
    expect(limited.statusCode).toBe(429);
    const body = limited.json<Record<string, unknown>>();
    expect(body).toEqual({
      statusCode: 429,
      code: PUBLIC_ERROR_CODES.RATE_LIMITED,
      error: 'Too Many Requests',
      message: PUBLIC_ERROR_MESSAGES[PUBLIC_ERROR_CODES.RATE_LIMITED],
      requestId: expect.any(String),
    });
    // requestId is added only by the central error handler, so its presence
    // (asserted above) proves the 429 was shaped there, not by the plugin.
    expect(body.requestId).toBeTruthy();

    await app.close();
  });

  it('keys globally: distinct client IPs share one bucket', async () => {
    const app = buildLimitedApp(2);

    expect(
      (await app.inject({ url: '/api/v1/public/definitions', remoteAddress: '10.0.0.1' }))
        .statusCode,
    ).toBe(200);
    expect(
      (await app.inject({ url: '/api/v1/public/definitions', remoteAddress: '10.0.0.2' }))
        .statusCode,
    ).toBe(200);
    // A third IP still trips the shared bucket — the limiter is a global
    // backstop, not per-client (per-IP enforcement lives at the edge).
    expect(
      (await app.inject({ url: '/api/v1/public/definitions', remoteAddress: '10.0.0.3' }))
        .statusCode,
    ).toBe(429);

    await app.close();
  });

  it('never throttles /health (outside the limited encapsulation scope)', async () => {
    const app = buildLimitedApp(2);

    for (let i = 0; i < 10; i += 1) {
      const res = await app.inject({ url: '/health' });
      expect(res.statusCode).toBe(200);
      expect(res.json()).toMatchObject({ status: 'ok' });
    }

    await app.close();
  });

  it('honors an env-tuned threshold', async () => {
    const app = buildLimitedApp(5);

    for (let i = 0; i < 5; i += 1) {
      expect((await app.inject({ url: '/api/v1/public/definitions' })).statusCode).toBe(200);
    }
    expect((await app.inject({ url: '/api/v1/public/definitions' })).statusCode).toBe(429);

    await app.close();
  });
});
