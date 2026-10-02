import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { loadChargeJudgeData, loadSearchIndex, resetStaticDataCache } from './static-data.js';

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

const INDEX = {
  available: true,
  aggregateRunId: '11111111-1111-4111-8111-111111111111',
  taxonomyVersion: '1.0.0',
  lastRefreshed: '2026-01-01T00:00:00.000Z',
  charges: [],
  judges: [],
  pairs: [],
};

beforeEach(() => {
  resetStaticDataCache();
  // The readers run in the browser; in this node suite the client resolves
  // against a base, which the stub makes deterministic.
  vi.stubEnv('API_BASE_URL', 'http://static.test');
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  resetStaticDataCache();
});

describe('loadSearchIndex', () => {
  it('fetches /data/search-index.json once and memoises the result', async () => {
    const fetchMock = vi.fn<(url: string | URL) => Promise<Response>>(() =>
      Promise.resolve(jsonResponse(INDEX)),
    );
    vi.stubGlobal('fetch', fetchMock);

    const [a, b] = await Promise.all([loadSearchIndex(), loadSearchIndex()]);
    expect(a).toEqual({ ok: true, data: INDEX });
    expect(b).toBe(a);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe('http://static.test/data/search-index.json');
  });

  it('treats an unavailable arm as a failed load and allows a retry', async () => {
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(() =>
        Promise.resolve(jsonResponse({ available: false, message: 'x' })),
      )
      .mockImplementation(() => Promise.resolve(jsonResponse(INDEX)));
    vi.stubGlobal('fetch', fetchMock);

    expect(await loadSearchIndex()).toEqual({ ok: false, error: { kind: 'fetch_failed' } });
    expect(await loadSearchIndex()).toEqual({ ok: true, data: INDEX });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('surfaces a rejected request as fetch_failed and does not cache it', async () => {
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(() => Promise.reject(new Error('offline')))
      .mockImplementation(() => Promise.resolve(jsonResponse(INDEX)));
    vi.stubGlobal('fetch', fetchMock);

    expect((await loadSearchIndex()).ok).toBe(false);
    expect((await loadSearchIndex()).ok).toBe(true);
  });
});

describe('loadChargeJudgeData', () => {
  it('fetches one file per charge, memoised per slug, with the slug encoded', async () => {
    const file = { aggregateRunId: INDEX.aggregateRunId, chargeSlug: 'a b', judges: {} };
    const fetchMock = vi.fn<(url: string | URL) => Promise<Response>>(() =>
      Promise.resolve(jsonResponse(file)),
    );
    vi.stubGlobal('fetch', fetchMock);

    const first = await loadChargeJudgeData('a b');
    const second = await loadChargeJudgeData('a b');
    expect(first).toEqual({ ok: true, data: file });
    expect(second).toBe(first);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe('http://static.test/data/charges/a%20b.json');
  });

  it('forgets a failed file so a later selection retries', async () => {
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(() => Promise.resolve(jsonResponse({ code: 'NOT_FOUND' }, 404)))
      .mockImplementation(() =>
        Promise.resolve(jsonResponse({ aggregateRunId: 'r', chargeSlug: 'x', judges: {} })),
      );
    vi.stubGlobal('fetch', fetchMock);

    expect((await loadChargeJudgeData('x')).ok).toBe(false);
    expect((await loadChargeJudgeData('x')).ok).toBe(true);
  });
});
