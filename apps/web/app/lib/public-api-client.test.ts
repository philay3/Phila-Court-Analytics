import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  getChargeResult,
  getDataCoverage,
  getDefinitions,
  getJudgeSpecificResult,
  getMethodology,
  resolvePublicApiUrl,
  searchCharges,
  searchJudges,
} from './public-api-client.js';

// A well-formed API error envelope (the flat five-field public shape).
const API_ERROR_BODY = {
  statusCode: 404,
  code: 'CHARGE_NOT_FOUND',
  error: 'Not Found',
  message: 'No charge matches the requested identifier.',
  requestId: 'req-abc-123',
};

function jsonResponse(body: unknown, init: { status?: number } = {}): Response {
  const status = init.status ?? 200;
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

function stubFetch(impl: (url: string) => Promise<Response> | Response): void {
  vi.stubGlobal(
    'fetch',
    vi.fn((input: string | URL) => Promise.resolve(impl(String(input)))),
  );
}

// Vitest runs in a node environment, so the client detects server context
// (typeof window === 'undefined') and resolves against API_BASE_URL. The
// stub below makes that base deterministic; the browser (relative-path)
// branch is proven directly by the resolvePublicApiUrl unit tests.
const TEST_BASE = 'http://api.test';

beforeEach(() => {
  vi.stubEnv('API_BASE_URL', TEST_BASE);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe('resolvePublicApiUrl', () => {
  it('prefixes the absolute base URL on the server', () => {
    expect(
      resolvePublicApiUrl('/api/v1/public/definitions', {
        isServer: true,
        apiBaseUrl: 'http://localhost:3001',
      }),
    ).toBe('http://localhost:3001/api/v1/public/definitions');
  });

  it('returns the relative path in the browser (hits the Next rewrite)', () => {
    expect(resolvePublicApiUrl('/api/v1/public/definitions', { isServer: false })).toBe(
      '/api/v1/public/definitions',
    );
  });

  it('throws on the server when API_BASE_URL is missing', () => {
    expect(() => resolvePublicApiUrl('/api/v1/public/definitions', { isServer: true })).toThrow(
      /API_BASE_URL/,
    );
  });
});

describe('public API client — success', () => {
  it('returns ok:true with the parsed body for a 200 response', async () => {
    stubFetch(() => jsonResponse({ results: [] }));
    const result = await searchCharges('theft');
    expect(result).toEqual({ ok: true, data: { results: [] } });
  });

  it('returns a 200 unavailable arm as ok:true data (not an error)', async () => {
    const unavailableArm = {
      resultType: 'judge_specific_unavailable',
      code: 'JUDGE_SPECIFIC_RESULT_UNAVAILABLE',
      message: 'unavailable',
      charge: {},
      judge: {},
      fallback: { chargeOnlyResultPath: '/api/v1/public/results/charge/theft' },
    };
    stubFetch(() => jsonResponse(unavailableArm));
    const result = await getJudgeSpecificResult('theft', 'jane-doe');
    expect(result.ok).toBe(true);
  });

  it('returns the charge-only 200 unavailable arm as ok:true data (not an error)', async () => {
    const unavailableArm = {
      resultType: 'charge_only_unavailable',
      code: 'CHARGE_RESULT_UNAVAILABLE',
      message: 'unavailable',
      charge: { id: 'x', slug: 'harassment', displayName: 'Harassment' },
      links: { methodology: '/methodology', definitions: '/definitions' },
    };
    stubFetch(() => jsonResponse(unavailableArm));
    const result = await getChargeResult('harassment');
    expect(result).toEqual({ ok: true, data: unavailableArm });
  });

  it('builds the search query string with q and limit', async () => {
    const fetchMock = vi.fn<(url: string | URL) => Promise<Response>>(() =>
      Promise.resolve(jsonResponse({ results: [] })),
    );
    vi.stubGlobal('fetch', fetchMock);
    await searchJudges('smith', 5);
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe(
      `${TEST_BASE}/api/v1/public/judges/search?q=smith&limit=5`,
    );
  });

  it('URL-encodes path parameters', async () => {
    const fetchMock = vi.fn<(url: string | URL) => Promise<Response>>(() =>
      Promise.resolve(jsonResponse({})),
    );
    vi.stubGlobal('fetch', fetchMock);
    await getChargeResult('a b/c');
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe(
      `${TEST_BASE}/api/v1/public/results/charge/a%20b%2Fc`,
    );
  });
});

describe('public API client — api_error', () => {
  it('surfaces a well-formed error with all five flat-shape fields preserved', async () => {
    stubFetch(() => jsonResponse(API_ERROR_BODY, { status: 404 }));
    const result = await getChargeResult('nope');
    expect(result).toEqual({
      ok: false,
      error: { kind: 'api_error', ...API_ERROR_BODY },
    });
  });

  it('retains requestId for support use', async () => {
    stubFetch(() => jsonResponse(API_ERROR_BODY, { status: 404 }));
    const result = await getChargeResult('nope');
    expect(result.ok).toBe(false);
    if (!result.ok && result.error.kind === 'api_error') {
      expect(result.error.requestId).toBe('req-abc-123');
    }
  });

  it('does not throw on an error response', async () => {
    stubFetch(() => jsonResponse(API_ERROR_BODY, { status: 404 }));
    await expect(getDefinitions()).resolves.toBeDefined();
  });
});

describe('public API client — fetch_failed', () => {
  it('surfaces a network failure as fetch_failed (no throw)', async () => {
    stubFetch(() => {
      throw new Error('network down');
    });
    await expect(getMethodology()).resolves.toEqual({
      ok: false,
      error: { kind: 'fetch_failed' },
    });
  });

  it('surfaces a non-JSON response body as fetch_failed', async () => {
    stubFetch(() => new Response('<html>gateway error</html>', { status: 502 }));
    await expect(getDataCoverage()).resolves.toEqual({
      ok: false,
      error: { kind: 'fetch_failed' },
    });
  });

  it('surfaces a malformed error payload as fetch_failed', async () => {
    // Valid JSON, wrong shape (missing requestId, unknown code) → not a
    // catalog error, so it must not masquerade as api_error.
    stubFetch(() => jsonResponse({ statusCode: 500, code: 'MADE_UP' }, { status: 500 }));
    await expect(getChargeResult('x')).resolves.toEqual({
      ok: false,
      error: { kind: 'fetch_failed' },
    });
  });
});

describe('no API base URL leaks into a client bundle', () => {
  const APP_DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');

  // Only shippable source counts: test files are never in a client bundle,
  // and this file itself names the token in strings — scanning it would
  // self-trigger.
  function collectShippableTsFiles(dir: string): string[] {
    const files: string[] = [];
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        files.push(...collectShippableTsFiles(full));
      } else if (/\.tsx?$/.test(entry.name) && !/\.test\.tsx?$/.test(entry.name)) {
        files.push(full);
      }
    }
    return files;
  }

  // Match an actual client-inlined env *reference* (process.env.NEXT_PUBLIC_…),
  // not prose that merely names the convention. Built at runtime so the needle
  // never appears as scannable source. Next only inlines NEXT_PUBLIC_-prefixed
  // vars into client bundles, so the absence of any such reference ensures no
  // API base URL can leak.
  const clientInlinedRef = new RegExp(`process\\.env\\.${['NEXT', 'PUBLIC', ''].join('_')}`);

  it('references no client-inlined env var anywhere under app/', () => {
    const offenders: string[] = [];
    for (const file of collectShippableTsFiles(APP_DIR)) {
      if (clientInlinedRef.test(readFileSync(file, 'utf8'))) {
        offenders.push(path.relative(APP_DIR, file));
      }
    }
    expect(offenders, offenders.join(', ')).toEqual([]);
  });
});
