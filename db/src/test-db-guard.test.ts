import { describe, expect, it } from 'vitest';

import { assertTestDatabaseUrl, dbNameFromUrl, isTestDbName } from './test-db-guard.js';

// Deliberate-failure coverage for the 29.2 test-database guard (AC 3): the
// live-shaped name is rejected, every established test/CI name passes, and
// unparseable URLs fail closed. Pure — no database required. The synthetic
// credentials below exist only to prove they are NEVER echoed in guard
// messages.

describe('isTestDbName', () => {
  it('rejects the live database name', () => {
    expect(isTestDbName('pca')).toBe(false);
  });

  it('rejects other non-test names', () => {
    expect(isTestDbName('postgres')).toBe(false);
    expect(isTestDbName('pca_prod')).toBe(false);
    expect(isTestDbName('pca_c')).toBe(false);
  });

  it('accepts every established test-database name', () => {
    expect(isTestDbName('pca_test')).toBe(true);
    expect(isTestDbName('pca_pipeline_test')).toBe(true);
    expect(isTestDbName('pca_sweep_test_deadbeef')).toBe(true);
  });

  it('accepts the CI service database by exact allowlist', () => {
    expect(isTestDbName('pca_ci')).toBe(true);
  });

  it('matches "test" case-insensitively (reference-model semantics)', () => {
    expect(isTestDbName('PCA_TEST')).toBe(true);
    expect(isTestDbName('Pca_Test')).toBe(true);
  });
});

describe('dbNameFromUrl', () => {
  it('extracts the database name from a connection URL', () => {
    expect(dbNameFromUrl('postgres://u:p@localhost:5433/pca_test')).toBe('pca_test');
    expect(dbNameFromUrl('postgresql://ci:ci@localhost:5432/pca_ci')).toBe('pca_ci');
  });

  it('returns null when the URL has no database path (fail-closed input)', () => {
    expect(dbNameFromUrl('postgres://u:p@localhost:5433')).toBeNull();
    expect(dbNameFromUrl('postgres://u:p@localhost:5433/')).toBeNull();
  });

  it('returns null on an unparseable URL (fail-closed input)', () => {
    expect(dbNameFromUrl('not a url')).toBeNull();
  });
});

describe('assertTestDatabaseUrl', () => {
  const context = 'guard unit test';

  it('rejects a live-shaped database name with a clear message', () => {
    expect(() =>
      assertTestDatabaseUrl('postgres://user:sekrit-cred@localhost:5433/pca', context),
    ).toThrowError(/refusing to run against database "pca"/);
  });

  it('never echoes credentials, host, or the URL in the rejection message', () => {
    let message = '';
    try {
      assertTestDatabaseUrl('postgres://user:sekrit-cred@example-host:5433/pca', context);
    } catch (error) {
      message = (error as Error).message;
    }
    expect(message).toContain('"pca"');
    expect(message).not.toContain('sekrit-cred');
    expect(message).not.toContain('user');
    expect(message).not.toContain('example-host');
    expect(message).not.toContain('://');
  });

  it('fails closed on a URL with no determinable database name', () => {
    expect(() =>
      assertTestDatabaseUrl('postgres://user:sekrit-cred@localhost:5433/', context),
    ).toThrowError(/could not be determined/);
    expect(() => assertTestDatabaseUrl('not a url', context)).toThrowError(
      /could not be determined/,
    );
  });

  it('passes every established test/CI database name', () => {
    for (const dbname of ['pca_test', 'pca_ci', 'pca_pipeline_test', 'pca_sweep_test_deadbeef']) {
      expect(() =>
        assertTestDatabaseUrl(`postgres://u:p@localhost:5433/${dbname}`, context),
      ).not.toThrow();
    }
  });
});
