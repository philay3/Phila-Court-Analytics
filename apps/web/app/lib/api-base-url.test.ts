import { afterEach, describe, expect, it, vi } from 'vitest';
import { LOCAL_DEV_API_BASE_URL, resolveApiBaseUrl } from './api-base-url.js';

afterEach(() => {
  vi.unstubAllEnvs();
});

describe('resolveApiBaseUrl', () => {
  it('returns an explicitly provided base URL unchanged', () => {
    expect(resolveApiBaseUrl('http://api.internal:3001')).toBe('http://api.internal:3001');
  });

  it('falls back to the local-dev default when the argument is undefined', () => {
    expect(resolveApiBaseUrl(undefined)).toBe(LOCAL_DEV_API_BASE_URL);
  });

  it('falls back to the local-dev default for an empty string', () => {
    expect(resolveApiBaseUrl('')).toBe(LOCAL_DEV_API_BASE_URL);
  });

  it('reads process.env.API_BASE_URL by default and defaults when it is unset', () => {
    vi.stubEnv('API_BASE_URL', 'http://from-env:3001');
    expect(resolveApiBaseUrl()).toBe('http://from-env:3001');

    vi.stubEnv('API_BASE_URL', '');
    expect(resolveApiBaseUrl()).toBe(LOCAL_DEV_API_BASE_URL);
  });
});
