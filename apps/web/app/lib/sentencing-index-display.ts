import type {
  ChargeSentencingIndex,
  ChargeSentencingIndexPresent,
  JudgeSentencingIndex,
  JudgeSentencingIndexPresent,
} from '@pca/shared';

/**
 * Display-arm derivation for the sentencing index (task 35.3). The API payload
 * makes the states derivable but does not name them (35.2 handoff note); this
 * module is the single place the naming happens. The arm NAMES are historical
 * (35.3 coined them when the index led the page); since the pre-recording
 * session's canonical reorder every arm renders outcome-first and the arms
 * differ only in the trailing index content:
 *
 *   - `lead`           — present with >= 1 category: the full index section
 *                        renders as the trailing rates block.
 *   - `zero-sentenced` — present with zero categories: no rates to show; the
 *                        ruling-4 fallback line carrying the conviction count
 *                        renders in the index's trailing position.
 *   - `absent`         — `available: false`: no index content at all.
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
