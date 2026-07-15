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
  // The Sprint 2 seeded-data disclosure lived here until the first real
  // aggregate run was published (task 28.2); published figures now come from
  // real Philadelphia court records.
  // No calendar dates or counts beyond the fixed 2025-01-01 MVP start may
  // appear here: served date ranges and counts come from the published run.
  'Coverage begins on January 1, 2025 and is anchored to disposition and ' +
    'sentencing event dates, not filing dates.',
  'Coverage includes misdemeanor and felony charges, along with summary-graded ' +
    'charges when they are part of a criminal case; standalone summary ' +
    'citations are not collected. Charges from cases still awaiting a final ' +
    'outcome do not appear until one is recorded.',
  'Collection is ongoing. The covered records are a growing subset of ' +
    'Philadelphia criminal cases, and results grow as newly collected records ' +
    'are aggregated.',
  'Figures are charge-level historical aggregates. They summarize groups of ' +
    'past cases and never describe an individual case.',
  'Some charges have small samples; those figures are labeled as thin data ' +
    'and should be read with caution. Most judge-specific figures are thin at ' +
    'this stage.',
];
