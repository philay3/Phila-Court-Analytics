/**
 * Public-safe known-limitations copy for GET /public/data-coverage, common
 * to both coverage arms. The DB-backed route test runs the forbidden-term
 * regexes and the forbidden-substring sweep over the full response body, so
 * this copy must stay clear of both lists (no docket/defendant/parser/review
 * vocabulary, no prediction/ranking/advice vocabulary).
 *
 * Mutable array because Fastify's reply type for the response schema expects
 * one; nothing mutates it in practice.
 */
export const DATA_COVERAGE_KNOWN_LIMITATIONS: string[] = [
  // Seeded-data disclosure (Sprint 2 standing requirement): every currently
  // published figure is fabricated seed data. Remove this entry in Sprint 7
  // when real aggregates replace the seeds.
  'All figures currently published are seeded demonstration data created for ' +
    'development and testing. They do not describe real Philadelphia court outcomes.',
  'Coverage begins on January 1, 2025 and is anchored to disposition and ' +
    'sentencing event dates, not filing dates.',
  'Figures are charge-level historical aggregates. They summarize groups of ' +
    'past cases and never describe an individual case.',
  'Some charges have small samples; those figures are labeled as thin data ' +
    'and should be read with caution.',
];
