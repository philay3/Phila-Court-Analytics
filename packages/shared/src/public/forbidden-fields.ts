// Forbidden-content constants for the public API privacy gate (task 10.1).
// The public API is aggregate-only: nothing tied to a person, a case, a source
// document, or the internal pipeline may appear in any public response. These
// constants are the single source of truth for what "forbidden" means; the
// apps/api forbidden-field suite (and, later, web E2E checks) import them —
// consumers must never inline their own copies.

/**
 * Normalized key stems. A response-body key fails the gate when its
 * normalized form (lowercased, with `_` and `-` stripped) CONTAINS any stem,
 * so `defendantName`, `defendant_name`, and `primary-defendant` all match the
 * `defendant` stem.
 *
 * Known boundary (deliberate): only these exact stems are caught — exotic
 * abbreviations of the same concepts (e.g. `srcKey`) pass the key check.
 * Widening a stem (e.g. `sourceid` → `source`) is not an option here because
 * legitimate public keys like `dataSource` would false-positive, forcing an
 * allowlist mechanism the gate must not grow.
 */
export const FORBIDDEN_FIELD_STEMS: readonly string[] = [
  'defendant',
  'docket',
  'sourcedocument',
  'sourceid',
  'sourceurl',
  'storagekey',
  'rawtext',
  'extractedtext',
  'parseddocket',
  'parsedcharge',
  'factid',
  'reviewstatus',
  'admincorrection',
  'confidence',
];

/**
 * Patterns applied to every string VALUE in a public response body.
 *
 * UJS criminal docket numbers, e.g. CP-51-CR-0001234-2025. The prefix set is
 * deliberately Philadelphia-scoped: CP (Court of Common Pleas) and MC
 * (Municipal Court). Magisterial district dockets (MJ-) use a different
 * format and do not exist in Philadelphia — a future statewide expansion must
 * add a new pattern rather than widen this one. The court-type segment is
 * generalized to any two letters (CR, MD, SA, SU, …) and the sequence allows
 * 4–7 digits to catch non-zero-padded renderings; matching is
 * case-insensitive.
 */
export const FORBIDDEN_VALUE_PATTERNS: readonly RegExp[] = [
  /\b(?:CP|MC)-\d{2}-[A-Za-z]{2}-\d{4,7}-\d{4}\b/i,
];
