import type {
  ChargeSentencingIndex,
  ChargeSentencingIndexPresent,
  JudgeSentencingIndex,
  JudgeSentencingIndexPresent,
} from '@pca/shared';

/**
 * Display-arm derivation for the sentencing index (task 35.3). The API payload
 * makes the states derivable but does not name them (35.2 handoff note); this
 * module is the single place the naming happens:
 *
 *   - `lead`           — present with >= 1 category: the index renders as the
 *                        page's lead block (pin 1).
 *   - `zero-sentenced` — present with zero categories: no rates to lead with;
 *                        the page renders outcome-first with the ruling-4
 *                        fallback line carrying the conviction count (pin 3).
 *   - `absent`         — `available: false`: today's post-Phase-33 page,
 *                        structurally unchanged (pin 2).
 *
 * Pure presentation logic: no thresholds, no arithmetic, no payload values
 * are computed here — only the served discriminator and array length are read.
 */

export type ChargeSentencingIndexDisplay =
  | { kind: 'lead'; index: ChargeSentencingIndexPresent }
  | { kind: 'zero-sentenced'; index: ChargeSentencingIndexPresent }
  | { kind: 'absent' };

export type JudgeSentencingIndexDisplay =
  | { kind: 'lead'; index: JudgeSentencingIndexPresent }
  | { kind: 'zero-sentenced'; index: JudgeSentencingIndexPresent }
  | { kind: 'absent' };

export function resolveChargeSentencingIndexDisplay(
  sentencingIndex: ChargeSentencingIndex,
): ChargeSentencingIndexDisplay {
  switch (sentencingIndex.available) {
    case true:
      return sentencingIndex.categories.length > 0
        ? { kind: 'lead', index: sentencingIndex }
        : { kind: 'zero-sentenced', index: sentencingIndex };
    case false:
      return { kind: 'absent' };
    default: {
      // A new union arm must add a case above rather than fall through.
      const exhaustive: never = sentencingIndex;
      return exhaustive;
    }
  }
}

export function resolveJudgeSentencingIndexDisplay(
  sentencingIndex: JudgeSentencingIndex,
): JudgeSentencingIndexDisplay {
  switch (sentencingIndex.available) {
    case true:
      return sentencingIndex.categories.length > 0
        ? { kind: 'lead', index: sentencingIndex }
        : { kind: 'zero-sentenced', index: sentencingIndex };
    case false:
      return { kind: 'absent' };
    default: {
      const exhaustive: never = sentencingIndex;
      return exhaustive;
    }
  }
}
