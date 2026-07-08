/**
 * Copy-compliance term lists for the public web app.
 *
 * These constants seed the automated copy guard (see copy-guard.test.ts) and
 * are exported so the PUB-008 copy guard tests can import and extend them.
 * All matching is case-insensitive.
 */

/** Terms that must never appear anywhere in apps/web/app. */
export const FORBIDDEN_TERMS: readonly string[] = [
  'odds',
  'likely sentence',
  'best judge',
  'worst judge',
  'judge score',
  'win rate',
  'guaranteed result',
  'guarantee',
  'guaranteed',
  'harsher',
  'more lenient',
];

/**
 * Guarded stem: any occurrence of this stem is a violation unless it falls
 * inside one of the allowlisted disclaimer phrases.
 */
export const GUARDED_STEM = 'predict';

/** Disclaimer phrases in which the guarded stem is permitted. */
export const DISCLAIMER_ALLOWLIST: readonly string[] = [
  'not a prediction',
  'not predictions',
  'does not predict',
];
