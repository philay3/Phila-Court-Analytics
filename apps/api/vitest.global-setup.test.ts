import { afterEach, describe, expect, it } from 'vitest';

import globalSetup from './vitest.global-setup.js';

// Entry-path deliberate-failure proof for the 29.2 test-database guard
// (AC 3): invoking the REAL global-setup with a live-shaped database name is
// rejected by the guard, and a CI-shaped name (pca_ci) clears it. Both URLs
// point at a closed port (127.0.0.1:1) with synthetic credentials, so:
//  - the live-shaped rejection carrying the GUARD message (not a connection
//    error) proves the block fires before any connection attempt — i.e.
//    before any write could happen;
//  - the pca_ci case failing with a NON-guard (connection) error proves the
//    CI name passes the guard and setup proceeded to connect. This makes the
//    AC-3 spec note ("the CI names must pass") testable locally.
// Guard messages must name the dbname only — never credentials or the URL.

const originalDatabaseUrl = process.env.DATABASE_URL;

afterEach(() => {
  if (originalDatabaseUrl === undefined) {
    delete process.env.DATABASE_URL;
  } else {
    process.env.DATABASE_URL = originalDatabaseUrl;
  }
});

describe('vitest global-setup test-database guard', () => {
  it('rejects a live-shaped database name before any connection attempt', async () => {
    process.env.DATABASE_URL = 'postgres://user:sekrit-cred@127.0.0.1:1/pca';
    await expect(globalSetup()).rejects.toThrowError(
      /api vitest globalSetup: refusing to run against database "pca"/,
    );
  });

  it('never echoes credentials or the URL in the rejection', async () => {
    process.env.DATABASE_URL = 'postgres://user:sekrit-cred@127.0.0.1:1/pca';
    let message = '';
    try {
      await globalSetup();
    } catch (error) {
      message = (error as Error).message;
    }
    expect(message).toContain('"pca"');
    expect(message).not.toContain('sekrit-cred');
    expect(message).not.toContain('127.0.0.1');
    expect(message).not.toContain('://');
  });

  it('lets the CI database name pca_ci through the guard', async () => {
    process.env.DATABASE_URL = 'postgres://user:sekrit-cred@127.0.0.1:1/pca_ci';
    // Past the guard, setup proceeds to connect to the (closed) port and
    // fails with a connection error — NOT the guard's refusal message.
    let message = '';
    try {
      await globalSetup();
    } catch (error) {
      message = (error as Error).message;
    }
    expect(message).not.toBe('');
    expect(message).not.toContain('refusing to run');
  });

  it('skips cleanly when DATABASE_URL is unset', async () => {
    delete process.env.DATABASE_URL;
    await expect(globalSetup()).resolves.toBeUndefined();
  });
});
