import { Type } from '@sinclair/typebox';
import { PUBLIC_ERROR_CODES } from '@pca/shared';
import { describe, expect, it } from 'vitest';
import { buildApp } from './app.js';

function testApp() {
  return buildApp({ logger: false });
}

// Acceptance criterion 1: error responses have exactly this shape, nothing else.
function expectExactErrorShape(body: Record<string, unknown>) {
  expect(Object.keys(body).sort()).toEqual(['code', 'error', 'message', 'requestId', 'statusCode']);
}

describe('GET /health', () => {
  it('returns 200 with the expected shape', async () => {
    const app = testApp();
    const res = await app.inject({ method: 'GET', url: '/health' });
    expect(res.statusCode).toBe(200);
    const body = res.json();
    expect(body.status).toBe('ok');
    expect(typeof body.uptime).toBe('number');
  });
});

describe('not-found handling', () => {
  it('returns the standard 404 shape with code NOT_FOUND', async () => {
    const app = testApp();
    const res = await app.inject({ method: 'GET', url: '/api/v1/public/nope' });
    expect(res.statusCode).toBe(404);
    const body = res.json();
    expect(body).toMatchObject({
      statusCode: 404,
      code: PUBLIC_ERROR_CODES.NOT_FOUND,
      error: 'Not Found',
    });
    expect(typeof body.message).toBe('string');
    expect(typeof body.requestId).toBe('string');
    expect(body.requestId.length).toBeGreaterThan(0);
    expectExactErrorShape(body);
  });
});

describe('request IDs', () => {
  it('echoes a provided x-request-id', async () => {
    const app = testApp();
    const res = await app.inject({
      method: 'GET',
      url: '/health',
      headers: { 'x-request-id': 'test-id-123' },
    });
    expect(res.headers['x-request-id']).toBe('test-id-123');
  });

  it('generates an x-request-id when none is provided', async () => {
    const app = testApp();
    const res = await app.inject({ method: 'GET', url: '/health' });
    const id = res.headers['x-request-id'];
    expect(typeof id).toBe('string');
    expect((id as string).length).toBeGreaterThan(0);
  });
});

describe('format enforcement through the real request path', () => {
  // Regression lock: request validation runs through Fastify's Ajv (which bundles
  // ajv-formats). If the validator compiler is ever swapped for one without format
  // support, these break loudly.
  function appWithFormatRoute() {
    const app = testApp();
    app.get(
      '/format-probe',
      {
        schema: {
          querystring: Type.Object({
            d: Type.Optional(Type.String({ format: 'date' })),
            u: Type.Optional(Type.String({ format: 'uuid' })),
          }),
        },
      },
      async () => ({ ok: true }),
    );
    return app;
  }

  it('rejects a malformed date with 400 INVALID_REQUEST', async () => {
    const app = appWithFormatRoute();
    const res = await app.inject({ method: 'GET', url: '/format-probe?d=not-a-date' });
    expect(res.statusCode).toBe(400);
    const body = res.json();
    expect(body).toMatchObject({ statusCode: 400, code: PUBLIC_ERROR_CODES.INVALID_REQUEST });
    expectExactErrorShape(body);
  });

  it('rejects a calendar-invalid date with 400 INVALID_REQUEST', async () => {
    const app = appWithFormatRoute();
    const res = await app.inject({ method: 'GET', url: '/format-probe?d=2026-02-31' });
    expect(res.statusCode).toBe(400);
    expect(res.json().code).toBe(PUBLIC_ERROR_CODES.INVALID_REQUEST);
  });

  it('rejects a malformed uuid with 400 INVALID_REQUEST', async () => {
    const app = appWithFormatRoute();
    const res = await app.inject({ method: 'GET', url: '/format-probe?u=not-a-uuid' });
    expect(res.statusCode).toBe(400);
    const body = res.json();
    expect(body).toMatchObject({ statusCode: 400, code: PUBLIC_ERROR_CODES.INVALID_REQUEST });
    expectExactErrorShape(body);
  });

  it('accepts well-formed values', async () => {
    const app = appWithFormatRoute();
    const res = await app.inject({
      method: 'GET',
      url: '/format-probe?d=2026-01-15&u=b8eb27a6-6fa1-4d0c-816b-96be2e3428b6',
    });
    expect(res.statusCode).toBe(200);
    expect(res.json()).toEqual({ ok: true });
  });
});

describe('error handler', () => {
  it('maps unexpected errors to 500 INTERNAL_ERROR without leaking the message', async () => {
    const app = testApp();
    app.get('/boom', async () => {
      throw new Error('sentinel-internal-detail: db-password-hunter2');
    });
    const res = await app.inject({ method: 'GET', url: '/boom' });
    expect(res.statusCode).toBe(500);
    const body = res.json();
    expect(body).toMatchObject({
      statusCode: 500,
      code: PUBLIC_ERROR_CODES.INTERNAL_ERROR,
      error: 'Internal Server Error',
      message: 'Internal Server Error',
    });
    expectExactErrorShape(body);
    expect(res.body).not.toContain('sentinel-internal-detail');
    expect(res.body).not.toContain('hunter2');
  });

  it('does not leak messages on non-500 server errors either', async () => {
    const app = testApp();
    app.get('/unavailable-upstream', async () => {
      throw Object.assign(new Error('sentinel-upstream-secret'), { statusCode: 503 });
    });
    const res = await app.inject({ method: 'GET', url: '/unavailable-upstream' });
    expect(res.statusCode).toBe(503);
    const body = res.json();
    expect(body).toMatchObject({
      statusCode: 503,
      code: PUBLIC_ERROR_CODES.INTERNAL_ERROR,
      message: 'Internal Server Error',
    });
    expect(res.body).not.toContain('sentinel-upstream-secret');
    expectExactErrorShape(body);
  });

  it('uses a thrown catalog code and its default status (7.2+ plumbing)', async () => {
    const app = testApp();
    app.get('/missing-charge', async () => {
      throw Object.assign(new Error('Charge not found.'), {
        code: PUBLIC_ERROR_CODES.CHARGE_NOT_FOUND,
      });
    });
    const res = await app.inject({ method: 'GET', url: '/missing-charge' });
    expect(res.statusCode).toBe(404);
    const body = res.json();
    expect(body).toMatchObject({
      statusCode: 404,
      code: PUBLIC_ERROR_CODES.CHARGE_NOT_FOUND,
      error: 'Not Found',
      message: 'Charge not found.',
    });
    expectExactErrorShape(body);
  });

  it('lets an explicit status override a catalog code default (defaults, not invariants)', async () => {
    const app = testApp();
    app.get('/unsupported', async () => {
      throw Object.assign(new Error('Unsupported media type.'), {
        code: PUBLIC_ERROR_CODES.INVALID_REQUEST,
        statusCode: 415,
      });
    });
    const res = await app.inject({ method: 'GET', url: '/unsupported' });
    expect(res.statusCode).toBe(415);
    const body = res.json();
    expect(body).toMatchObject({ statusCode: 415, code: PUBLIC_ERROR_CODES.INVALID_REQUEST });
    expectExactErrorShape(body);
  });

  it("maps Fastify's own client errors (bad JSON body) to INVALID_REQUEST", async () => {
    const app = testApp();
    app.post('/echo', async (request) => request.body);
    const res = await app.inject({
      method: 'POST',
      url: '/echo',
      headers: { 'content-type': 'application/json' },
      payload: '{"broken',
    });
    expect(res.statusCode).toBe(400);
    const body = res.json();
    expect(body).toMatchObject({ statusCode: 400, code: PUBLIC_ERROR_CODES.INVALID_REQUEST });
    expectExactErrorShape(body);
  });
});
