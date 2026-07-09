import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import {
  CHARGE_NOT_FOUND_MESSAGE,
  CHARGE_RESULT_UNAVAILABLE_MESSAGE,
  CHARGE_SENTENCING_UNAVAILABLE_MESSAGE,
  DATA_COVERAGE_UNAVAILABLE_MESSAGE,
  JUDGE_NOT_FOUND_MESSAGE,
  JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE,
  scanPublicCopy,
  type CopySafetyViolation,
} from '@pca/shared';
import { buildApp } from './app.js';
import { DATA_COVERAGE_KNOWN_LIMITATIONS } from './content/data-coverage.js';
import { METHODOLOGY_CONTENT } from './content/methodology.js';
import { PUBLIC_DEFINITIONS } from './taxonomy.js';
import { PROBE_REGISTRY } from './test-support/public-route-probes.js';

// Public copy-safety gate (task 10.2). Two layers over the same scanner:
// static sources (content modules, pinned message literals, public taxonomy
// definitions) are scanned at their definition, and every public route arm
// from the shared 10.1/10.2 probe registry is scanned live — every string
// value in every JSON payload must come back clean from @pca/shared's
// scanPublicCopy. Endpoint coverage is enforced by the 10.1 suite's
// discovery/coverage assertions against the same registry.

interface StringScanResult {
  /** JSON-path-ish location of the string, e.g. 'sections.notPrediction.body'. */
  path: string;
  value: string;
  violations: CopySafetyViolation[];
}

/**
 * Recursively collects every string value in a JSON-shaped payload and scans
 * each with the shared scanner. This exact function is the mechanism under
 * test in the deliberate-failure probe below.
 */
function scanJsonStrings(payload: unknown, pathPrefix = '$'): StringScanResult[] {
  if (typeof payload === 'string') {
    return [{ path: pathPrefix, value: payload, violations: scanPublicCopy(payload) }];
  }
  if (Array.isArray(payload)) {
    return payload.flatMap((entry, index) => scanJsonStrings(entry, `${pathPrefix}[${index}]`));
  }
  if (payload !== null && typeof payload === 'object') {
    return Object.entries(payload).flatMap(([key, value]) =>
      scanJsonStrings(value, `${pathPrefix}.${key}`),
    );
  }
  return [];
}

function formatCopyViolations(results: StringScanResult[]): string {
  return results
    .filter((result) => result.violations.length > 0)
    .map(
      (result) =>
        `  ${result.path}: ${result.violations
          .map((violation) => `"${violation.term}" at ${violation.index} (…${violation.context}…)`)
          .join('; ')}`,
    )
    .join('\n');
}

function expectClean(results: StringScanResult[], label: string): void {
  const dirty = results.filter((result) => result.violations.length > 0);
  expect(dirty, `forbidden copy in ${label}:\n${formatCopyViolations(dirty)}`).toEqual([]);
}

const PINNED_PUBLIC_MESSAGES = {
  CHARGE_NOT_FOUND_MESSAGE,
  CHARGE_RESULT_UNAVAILABLE_MESSAGE,
  CHARGE_SENTENCING_UNAVAILABLE_MESSAGE,
  DATA_COVERAGE_UNAVAILABLE_MESSAGE,
  JUDGE_NOT_FOUND_MESSAGE,
  JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE,
} as const;

describe('static public copy sources', () => {
  it('methodology content scans clean', () => {
    expectClean(scanJsonStrings(METHODOLOGY_CONTENT), 'METHODOLOGY_CONTENT');
  });

  it('data-coverage known-limitations copy scans clean', () => {
    expectClean(
      scanJsonStrings(DATA_COVERAGE_KNOWN_LIMITATIONS),
      'DATA_COVERAGE_KNOWN_LIMITATIONS',
    );
  });

  it('every pinned public message literal scans clean', () => {
    for (const [name, message] of Object.entries(PINNED_PUBLIC_MESSAGES)) {
      expect(scanPublicCopy(message), `${name} must scan clean`).toEqual([]);
    }
  });

  it('public-visible taxonomy definitions scan clean', () => {
    expectClean(scanJsonStrings(PUBLIC_DEFINITIONS), 'PUBLIC_DEFINITIONS (@pca/taxonomy)');
  });
});

describe('deliberate-failure proof: the scan mechanism reports poisoned strings', () => {
  it('flags a poisoned payload routed through the exact live-scan path', () => {
    const poisoned = {
      message: 'A guaranteed outcome improves your odds.',
      nested: [{ note: 'This is a prediction with a strong win rate.' }],
      clean: 'Historical aggregates of past cases.',
    };
    const results = scanJsonStrings(poisoned);
    const flaggedTerms = results.flatMap((result) => result.violations.map((v) => v.term));
    expect(flaggedTerms).toContain('guarantee stem');
    expect(flaggedTerms).toContain('odds');
    expect(flaggedTerms).toContain('predict stem');
    expect(flaggedTerms).toContain('win rate');
    // The clean string must not be flagged — the probe proves sensitivity,
    // not blanket failure.
    const cleanEntry = results.find((result) => result.path === '$.clean');
    expect(cleanEntry?.violations).toEqual([]);
  });
});

const hasDb = Boolean(process.env.DATABASE_URL);
if (!hasDb) {
  console.warn(
    'DATABASE_URL not set — skipping live copy-safety probe execution. ' +
      'Start Postgres (pnpm db:up), apply migrations (pnpm db:migrate:latest), ' +
      'and create the root .env (cp .env.example .env).',
  );
}

// Same rule as the 10.1 gate: locally a missing DATABASE_URL downgrades the
// live probes to a skip, but in CI the database is provisioned by the
// workflow, so its absence would silently pass the gate without scanning a
// single response. This test always runs — no skipIf.
describe('CI gate integrity', () => {
  it('fails loudly when CI is set but the database is unavailable', () => {
    if (process.env.CI) {
      expect(
        hasDb,
        'DATABASE_URL is not set in CI: the public copy-safety gate cannot run its live probes. ' +
          'This gate must never be skipped in CI — fix the workflow database service before merging.',
      ).toBe(true);
    }
  });
});

describe.skipIf(!hasDb)('copy-safety scan of every public route arm', () => {
  let app: ReturnType<typeof buildApp>;

  beforeAll(async () => {
    app = buildApp({ logger: false });
    await app.ready();
  });

  afterAll(async () => {
    await app?.close();
  });

  for (const [route, probes] of Object.entries(PROBE_REGISTRY)) {
    describe(route, () => {
      for (const probe of probes) {
        it(`${probe.name}: every string in the body scans clean`, async () => {
          const res = await app.inject({ method: 'GET', url: probe.path });
          expect(res.statusCode, `probe '${probe.name}' (${probe.path}) drifted off its arm`).toBe(
            probe.expectedStatus,
          );

          expectClean(
            scanJsonStrings(res.json()),
            `${route} [probe '${probe.name}' → ${probe.path}]`,
          );
        });
      }
    });
  }
});
