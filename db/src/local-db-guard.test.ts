import { describe, expect, it } from 'vitest';

import {
  assertLocalDatabaseUrl,
  hostFromUrl,
  isLocalDbHost,
  REMOTE_DB_OK_ENV,
  REMOTE_DB_OK_VALUE,
  remoteDbOverrideActive,
} from './local-db-guard.js';

// URLs below are synthetic — no real hosts or secrets.
const LOCAL_URL = 'postgres://pca:pca@localhost:5432/pca';
const REMOTE_URL = 'postgres://user:sekret@db.fake-remote.example.com:5432/pca';

describe('task 34.6: hostFromUrl', () => {
  it('extracts the hostname', () => {
    expect(hostFromUrl(LOCAL_URL)).toBe('localhost');
    expect(hostFromUrl(REMOTE_URL)).toBe('db.fake-remote.example.com');
  });

  it('strips IPv6 brackets and lowercases', () => {
    expect(hostFromUrl('postgres://u@[::1]:5432/pca')).toBe('::1');
    expect(hostFromUrl('postgres://u@LOCALHOST:5432/pca')).toBe('localhost');
  });

  it('returns null for unparseable or hostless URLs (fail-closed input)', () => {
    expect(hostFromUrl('not a url')).toBeNull();
    expect(hostFromUrl('postgresql:///pca')).toBeNull();
  });
});

describe('task 34.6: isLocalDbHost', () => {
  it('accepts exactly localhost, 127.0.0.1, and ::1', () => {
    expect(isLocalDbHost('localhost')).toBe(true);
    expect(isLocalDbHost('127.0.0.1')).toBe(true);
    expect(isLocalDbHost('::1')).toBe(true);
  });

  it('rejects everything else, including lookalikes', () => {
    expect(isLocalDbHost('db.fake-remote.example.com')).toBe(false);
    expect(isLocalDbHost('localhost.example.com')).toBe(false);
    expect(isLocalDbHost('127.0.0.2')).toBe(false);
    expect(isLocalDbHost('192.168.1.10')).toBe(false);
  });
});

describe('task 34.6: remoteDbOverrideActive', () => {
  it('requires the exact value, not truthiness', () => {
    expect(remoteDbOverrideActive({ [REMOTE_DB_OK_ENV]: REMOTE_DB_OK_VALUE })).toBe(true);
    expect(remoteDbOverrideActive({ [REMOTE_DB_OK_ENV]: 'true' })).toBe(false);
    expect(remoteDbOverrideActive({ [REMOTE_DB_OK_ENV]: '0' })).toBe(false);
    expect(remoteDbOverrideActive({ [REMOTE_DB_OK_ENV]: '' })).toBe(false);
    expect(remoteDbOverrideActive({})).toBe(false);
  });
});

describe('task 34.6: assertLocalDatabaseUrl', () => {
  it('passes local hosts through in both modes', () => {
    for (const url of [LOCAL_URL, 'postgres://u@127.0.0.1:5432/pca', 'postgres://u@[::1]/pca']) {
      expect(() =>
        assertLocalDatabaseUrl(url, 'ctx', { allowRemoteOverride: true, env: {} }),
      ).not.toThrow();
      expect(() =>
        assertLocalDatabaseUrl(url, 'ctx', { allowRemoteOverride: false, env: {} }),
      ).not.toThrow();
    }
  });

  it('refuses a remote host, naming host and dbname but never the URL', () => {
    let thrown: Error | undefined;
    try {
      assertLocalDatabaseUrl(REMOTE_URL, 'db:migrate:latest', {
        allowRemoteOverride: true,
        env: {},
      });
    } catch (error) {
      thrown = error as Error;
    }
    expect(thrown).toBeDefined();
    expect(thrown?.message).toContain('db:migrate:latest');
    expect(thrown?.message).toContain('db.fake-remote.example.com');
    expect(thrown?.message).toContain('"pca"');
    expect(thrown?.message).not.toContain('sekret');
    expect(thrown?.message).not.toContain(REMOTE_URL);
  });

  it('refuses fail-closed when the host cannot be determined', () => {
    expect(() =>
      assertLocalDatabaseUrl('postgresql:///pca', 'ctx', { allowRemoteOverride: true, env: {} }),
    ).toThrow(/fail-closed/);
    expect(() =>
      assertLocalDatabaseUrl('not a url', 'ctx', { allowRemoteOverride: false, env: {} }),
    ).toThrow(/fail-closed/);
  });

  it('honors PCA_REMOTE_DB_OK=1 only where the call site opts in (migrate)', () => {
    const armed = { [REMOTE_DB_OK_ENV]: REMOTE_DB_OK_VALUE };
    expect(() =>
      assertLocalDatabaseUrl(REMOTE_URL, 'db:migrate:latest', {
        allowRemoteOverride: true,
        env: armed,
      }),
    ).not.toThrow();
    // Exact-value match: anything else stays refused.
    expect(() =>
      assertLocalDatabaseUrl(REMOTE_URL, 'db:migrate:latest', {
        allowRemoteOverride: true,
        env: { [REMOTE_DB_OK_ENV]: 'true' },
      }),
    ).toThrow(/not a local host/);
  });

  it('never honors the override at the seed boundary', () => {
    const armed = { [REMOTE_DB_OK_ENV]: REMOTE_DB_OK_VALUE };
    let thrown: Error | undefined;
    try {
      assertLocalDatabaseUrl(REMOTE_URL, 'db:seed', { allowRemoteOverride: false, env: armed });
    } catch (error) {
      thrown = error as Error;
    }
    expect(thrown).toBeDefined();
    expect(thrown?.message).toContain('no override');
  });
});
