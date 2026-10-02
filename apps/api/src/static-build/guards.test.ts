import { describe, expect, it } from 'vitest';
import {
  assertDatabaseUrlForMode,
  assertPinnedRunId,
  hostFromUrl,
  parseBuildMode,
} from './guards.js';

// Invented URLs with a dummy credential; nothing here is a real connection string.
const LOCAL_PCA = 'postgres://user:secret@localhost:5433/pca';
const LOCAL_PCA_V6 = 'postgres://user:secret@[::1]:5433/pca';
const LOCAL_TEST = 'postgres://user:secret@127.0.0.1:5433/pca_test';
const REMOTE_PCA = 'postgres://user:secret@db.example.internal:5432/pca';
const CI_DB = 'postgresql://ci:ci@localhost:5432/pca_ci';

describe('parseBuildMode', () => {
  it('accepts publish and ci', () => {
    expect(parseBuildMode(['--mode', 'publish'])).toBe('publish');
    expect(parseBuildMode(['--mode', 'ci'])).toBe('ci');
  });

  it('refuses a missing or unknown mode', () => {
    expect(() => parseBuildMode([])).toThrowError(/mode flag is required/);
    expect(() => parseBuildMode(['--mode'])).toThrowError(/mode flag is required/);
    expect(() => parseBuildMode(['--mode', 'prod'])).toThrowError(/mode flag is required/);
  });
});

describe('assertDatabaseUrlForMode — publish', () => {
  it('accepts the canonical database on a local host and returns its name', () => {
    expect(assertDatabaseUrlForMode(LOCAL_PCA, 'publish')).toBe('pca');
    expect(assertDatabaseUrlForMode(LOCAL_PCA_V6, 'publish')).toBe('pca');
  });

  it('refuses a test database (the deliberate-failure proof the task requires)', () => {
    expect(() => assertDatabaseUrlForMode(LOCAL_TEST, 'publish')).toThrowError(
      /publish mode refuses database "pca_test"/,
    );
  });

  it('refuses the canonical name on a remote host', () => {
    expect(() => assertDatabaseUrlForMode(REMOTE_PCA, 'publish')).toThrowError(
      /refuses host "db.example.internal" for database "pca"/,
    );
  });

  it('fails closed on a missing or undeterminable URL and never echoes the URL', () => {
    expect(() => assertDatabaseUrlForMode(undefined, 'publish')).toThrowError(
      /DATABASE_URL is not set/,
    );
    expect(() => assertDatabaseUrlForMode('not a url', 'publish')).toThrowError(/fail-closed/);
    try {
      assertDatabaseUrlForMode(LOCAL_TEST, 'publish');
    } catch (error) {
      expect((error as Error).message).not.toContain('secret');
      expect((error as Error).message).not.toContain('postgres://');
    }
  });
});

describe('assertDatabaseUrlForMode — ci', () => {
  it('accepts test-shaped names and the CI database', () => {
    expect(assertDatabaseUrlForMode(LOCAL_TEST, 'ci')).toBe('pca_test');
    expect(assertDatabaseUrlForMode(CI_DB, 'ci')).toBe('pca_ci');
  });

  it('refuses the canonical database', () => {
    expect(() => assertDatabaseUrlForMode(LOCAL_PCA, 'ci')).toThrowError(
      /refusing to run against database "pca"/,
    );
  });
});

describe('helpers', () => {
  it('hostFromUrl strips IPv6 brackets and fails closed', () => {
    expect(hostFromUrl(LOCAL_PCA_V6)).toBe('::1');
    expect(hostFromUrl('nope')).toBeNull();
  });

  it('assertPinnedRunId accepts the pinned id and refuses any other, naming only short ids', () => {
    const pinned = '78f90de7-d250-4206-a76f-ef7732e97fe2';
    expect(() => assertPinnedRunId(pinned, pinned, 'x')).not.toThrow();
    expect(() =>
      assertPinnedRunId(pinned, 'aaaaaaaa-0000-4000-8000-000000000000', 'results'),
    ).toThrowError(/results carries aggregateRunId aaaaaaaa but the pinned run is 78f90de7/);
    expect(() => assertPinnedRunId(pinned, undefined, 'results')).toThrowError(/\(none\)/);
  });
});
