/**
 * Shared E2E constants (task 15.2): ports, base URLs, and the seed slugs each
 * flow exercises. Slugs are read off db/seeds/reference-data.ts and
 * db/seeds/aggregate-data.ts — the deterministic seed set — never invented
 * here. Any pinned user-facing COPY is imported from @pca/shared (or the web
 * copy modules) in the spec files, never re-typed alongside these slugs.
 */

// Local-dev / CI ports (matches the 15.1 walkthrough note: web 3000, api 3001).
export const WEB_PORT = 3000;
export const API_PORT = 3001;

export const WEB_BASE_URL = `http://127.0.0.1:${WEB_PORT}`;
export const API_HEALTH_URL = `http://127.0.0.1:${API_PORT}/health`;

/**
 * Seed-slug fixtures, each mapped to the scenario it exercises. Sourced from
 * the deterministic seed files:
 *   - retail-theft: data-bearing charge (outcomes n=1200, sentencing n=700),
 *     verified in the 15.1 walkthrough.
 *   - criminal-trespass: thin-data charge (outcomes n=18, isThinData).
 *   - possession-controlled-substance: outcomes present (n=950), sentencing
 *     deliberately ABSENT — the sentencing-unavailable scenario.
 *   - harassment: a real charge with a published run but ZERO aggregate rows —
 *     CHARGE_RESULT_UNAVAILABLE (200 arm on the charge route, 404 envelope on
 *     the judge route: the W1 case).
 *   - judge-testina-placeholder: data-bearing judge for retail-theft
 *     (outcomes n=140, sentencing n=85).
 *   - judge-fakename-example: canonical judge-specific-unavailable fixture —
 *     both ref rows exist, zero aggregate rows (200 unavailable arm).
 */
export const SLUGS = {
  chargeDataBearing: 'retail-theft',
  chargeThin: 'criminal-trespass',
  chargeSentencingUnavailable: 'possession-controlled-substance',
  chargeUnavailable: 'harassment',
  chargeUnknown: 'no-such-charge-slug-xyz',
  judgeDataBearing: 'judge-testina-placeholder',
  judgeNoAggregate: 'judge-fakename-example',
} as const;

// Display names as seeded (used to target autocomplete options), sourced from
// reference-data.ts. Not user-facing copy under the copy-safety policy —
// statutes/charge names and the obviously-fake seed judge names.
export const DISPLAY_NAMES = {
  chargeDataBearing: 'Retail Theft',
  judgeDataBearing: 'Judge Testina Placeholder',
} as const;
