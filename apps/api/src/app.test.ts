import { describe, expect, it } from 'vitest';
import { buildApp } from './app.js';

function testApp() {
  return buildApp({ logger: false });
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
  it('returns the standard 404 shape including requestId', async () => {
    const app = testApp();
    const res = await app.inject({ method: 'GET', url: '/api/v1/public/nope' });
    expect(res.statusCode).toBe(404);
    const body = res.json();
    expect(body).toMatchObject({ statusCode: 404, error: 'Not Found' });
    expect(typeof body.message).toBe('string');
    expect(typeof body.requestId).toBe('string');
    expect(body.requestId.length).toBeGreaterThan(0);
    expect(body).not.toHaveProperty('stack');
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
