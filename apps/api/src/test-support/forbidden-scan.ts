import { FORBIDDEN_FIELD_STEMS, FORBIDDEN_VALUE_PATTERNS } from '@pca/shared';

/**
 * One forbidden-content hit inside a scanned response body. The shape carries
 * everything a failure message needs to be actionable: where (jsonPath), what
 * (offender), and which rule fired (matched).
 */
export interface ForbiddenViolation {
  /** JSON path to the offending key or value, e.g. `$.results[2].docketNumber`. */
  jsonPath: string;
  kind: 'key' | 'value';
  /** The raw key name, or the string value that matched. */
  offender: string;
  /** The stem (kind: 'key') or pattern source (kind: 'value') that matched. */
  matched: string;
}

// Keys are normalized before stem matching so casing and separator style can
// never smuggle a forbidden field past the gate: `docket_number`,
// `docketNumber`, and `Docket-Number` all normalize onto the same stem.
function normalizeKey(key: string): string {
  return key.toLowerCase().replaceAll('_', '').replaceAll('-', '');
}

/**
 * Deep-recursive scan of a parsed JSON body (objects + arrays) against the
 * shared forbidden stems and value patterns. Returns every violation rather
 * than throwing, so callers control the failure message and self-tests can
 * assert on the full list.
 */
export function scanForForbidden(body: unknown): ForbiddenViolation[] {
  const violations: ForbiddenViolation[] = [];
  walk(body, '$', violations);
  return violations;
}

function walk(node: unknown, path: string, violations: ForbiddenViolation[]): void {
  if (typeof node === 'string') {
    for (const pattern of FORBIDDEN_VALUE_PATTERNS) {
      if (pattern.test(node)) {
        violations.push({ jsonPath: path, kind: 'value', offender: node, matched: `${pattern}` });
      }
    }
    return;
  }

  if (Array.isArray(node)) {
    node.forEach((item, index) => walk(item, `${path}[${index}]`, violations));
    return;
  }

  if (node !== null && typeof node === 'object') {
    for (const [key, value] of Object.entries(node)) {
      const keyPath = `${path}.${key}`;
      const normalized = normalizeKey(key);
      for (const stem of FORBIDDEN_FIELD_STEMS) {
        if (normalized.includes(stem)) {
          violations.push({ jsonPath: keyPath, kind: 'key', offender: key, matched: stem });
        }
      }
      walk(value, keyPath, violations);
    }
  }
}

/** Formats violations for an assertion message that names route, probe, and every hit. */
export function formatViolations(violations: ForbiddenViolation[]): string {
  return violations
    .map(
      (v) =>
        `  ${v.jsonPath}: forbidden ${v.kind} ${JSON.stringify(v.offender)} matched ${v.matched}`,
    )
    .join('\n');
}
