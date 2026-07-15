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

  describe('production guard (task 31.3)', () => {
    it('throws in production when API_BASE_URL is unset', () => {
      vi.stubEnv('NODE_ENV', 'production');
      expect(() => resolveApiBaseUrl(undefined)).toThrowError(
        /API_BASE_URL is required in production/,
      );
    });

    it('throws in production when API_BASE_URL is empty', () => {
      vi.stubEnv('NODE_ENV', 'production');
      expect(() => resolveApiBaseUrl('')).toThrowError(/API_BASE_URL is required in production/);
    });

    it('returns the configured value in production when set', () => {
      vi.stubEnv('NODE_ENV', 'production');
      expect(resolveApiBaseUrl('http://api.internal:3001')).toBe('http://api.internal:3001');
    });

    it('keeps the local-dev default outside production', () => {
      vi.stubEnv('NODE_ENV', 'development');
      expect(resolveApiBaseUrl(undefined)).toBe(LOCAL_DEV_API_BASE_URL);

      vi.stubEnv('NODE_ENV', 'test');
      expect(resolveApiBaseUrl('')).toBe(LOCAL_DEV_API_BASE_URL);
    });
  });
});
