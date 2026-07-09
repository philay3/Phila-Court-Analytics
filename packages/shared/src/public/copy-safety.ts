/**
 * Canonical public copy-safety rules (task 10.2). Single source of truth for
 * the forbidden-term list, the guarded disclaimer phrases, and the scanner —
 * the web copy guard and the API copy-safety suite both consume this module;
 * no other package may define copy-safety terms.
 *
 * Matching discipline: every term is case-insensitive and word-boundary-aware
 * (`odds` never matches inside another word), and multi-word terms match
 * across single spaces. Callers scanning multi-line sources collapse
 * whitespace before calling `scanPublicCopy` — that is file-level
 * preprocessing, not scanner behavior.
 */

export interface ForbiddenPublicTerm {
  /** Human-readable label reported in violations. */
  term: string;
  /** Case-insensitive, word-boundary-aware pattern for the term. */
  pattern: RegExp;
}

/**
 * The locked forbidden-term list. `predict` and `guarantee` are stems: every
 * enumerated inflection is a violation. `better` / `worse` are intentionally
 * absent from the mechanical list.
 */
export const FORBIDDEN_PUBLIC_TERMS: readonly ForbiddenPublicTerm[] = [
  { term: 'odds', pattern: /\bodds\b/i },
  // predict, predicts, predicted, predicting, prediction(s), predictive
  { term: 'predict stem', pattern: /\bpredict(?:s|ed|ing|ions?|ive)?\b/i },
  // guarantee, guarantees, guaranteed, guaranteeing
  { term: 'guarantee stem', pattern: /\bguarantee(?:s|d|ing)?\b/i },
  { term: 'likely sentence', pattern: /\blikely sentence\b/i },
  { term: 'best judge', pattern: /\bbest judge\b/i },
  { term: 'worst judge', pattern: /\bworst judge\b/i },
  { term: 'judge score', pattern: /\bjudge score\b/i },
  { term: 'win rate', pattern: /\bwin rate\b/i },
  { term: 'harsher', pattern: /\bharsher\b/i },
  { term: 'more lenient', pattern: /\bmore lenient\b/i },
];

/**
 * The ONLY phrasings in which forbidden vocabulary may appear in public copy.
 * The scanner masks these exact phrases (case-insensitively) before applying
 * the forbidden-term patterns, so any unguarded use of the vocabulary still
 * fails. Union of the 4.1 web allowlist and the 9.2 methodology set.
 */
export const GUARDED_DISCLAIMER_PHRASES = [
  'not a prediction',
  'not predictions',
  'do not predict',
  'does not predict',
  'not legal advice',
  'does not provide legal advice',
] as const;

export interface CopySafetyViolation {
  /** The `term` label of the FORBIDDEN_PUBLIC_TERMS entry that matched. */
  term: string;
  /** Match position in the input text (mask-preserving, so indexes are real). */
  index: number;
  /** The matched text with surrounding context from the original input. */
  context: string;
}

function escapeRegExp(literal: string): string {
  return literal.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

const CONTEXT_RADIUS = 30;

/**
 * Mask-then-scan (pinned algorithm): every guarded-phrase occurrence is
 * blanked out first (replaced with spaces, so indexes are preserved and
 * masking one phrase cannot launder adjacent text), then the remainder is
 * scanned with every forbidden-term pattern. No other exemption mechanism.
 * An empty array means the text is clean.
 */
export function scanPublicCopy(text: string): CopySafetyViolation[] {
  let masked = text;
  for (const phrase of GUARDED_DISCLAIMER_PHRASES) {
    masked = masked.replace(new RegExp(escapeRegExp(phrase), 'gi'), (occurrence) =>
      ' '.repeat(occurrence.length),
    );
  }

  const violations: CopySafetyViolation[] = [];
  for (const { term, pattern } of FORBIDDEN_PUBLIC_TERMS) {
    // Fresh global regex per scan: the exported patterns stay flag-stable and
    // stateless for consumers that .test() them directly.
    for (const match of masked.matchAll(new RegExp(pattern.source, 'gi'))) {
      violations.push({
        term,
        index: match.index,
        context: text.slice(
          Math.max(0, match.index - CONTEXT_RADIUS),
          match.index + match[0].length + CONTEXT_RADIUS,
        ),
      });
    }
  }
  return violations;
}
