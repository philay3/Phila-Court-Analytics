import { describe, expect, it } from 'vitest';
import {
  FORBIDDEN_PUBLIC_TERMS,
  GUARDED_DISCLAIMER_PHRASES,
  scanPublicCopy,
} from './copy-safety.js';

// One violating sample per term label, with every enumerated stem inflection
// covered for the two stems. The exhaustiveness test below pins this map to
// FORBIDDEN_PUBLIC_TERMS so a term added without samples fails loudly.
const VIOLATING_SAMPLES: Record<string, readonly string[]> = {
  odds: ['The odds are unclear.'],
  'predict stem': [
    'We predict outcomes.',
    'It predicts outcomes.',
    'It predicted the result.',
    'It is predicting results.',
    'This is a prediction.',
    'These are predictions.',
    'A predictive model.',
  ],
  'guarantee stem': [
    'No guarantee of anything.',
    'It guarantees a result.',
    'A guaranteed outcome.',
    'They are guaranteeing it.',
  ],
  'likely sentence': ['The likely sentence is short.'],
  'best judge': ['Find the best judge here.'],
  'worst judge': ['Avoid the worst judge here.'],
  'judge score': ['Each judge score is shown.'],
  'win rate': ['Compare the win rate.'],
  harsher: ['This court is harsher.'],
  'more lenient': ['That court is more lenient.'],
};

describe('scanPublicCopy', () => {
  it('flags bare "prediction" as a violation', () => {
    const violations = scanPublicCopy('This figure is a prediction of the outcome.');
    expect(violations).not.toEqual([]);
    expect(violations.map((v) => v.term)).toContain('predict stem');
  });

  it('scans the exact guarded phrase "not a prediction" clean', () => {
    expect(scanPublicCopy('This figure is not a prediction.')).toEqual([]);
  });

  it('masking a guarded phrase does not launder a separate bare "predictive"', () => {
    const violations = scanPublicCopy(
      'This is not a prediction. Separately, our predictive summary is here.',
    );
    expect(violations.map((v) => v.term)).toEqual(['predict stem']);
  });

  it('does not match "odds" inside a longer word (word boundary)', () => {
    expect(scanPublicCopy('The oddsmakers were not consulted.')).toEqual([]);
  });

  it('flags mixed-case "Win Rate" (case-insensitive)', () => {
    const violations = scanPublicCopy('See the Win Rate for details.');
    expect(violations.map((v) => v.term)).toEqual(['win rate']);
  });

  it('scans every guarded disclaimer phrase individually clean', () => {
    for (const phrase of GUARDED_DISCLAIMER_PHRASES) {
      expect(scanPublicCopy(phrase), `phrase "${phrase}" should scan clean`).toEqual([]);
    }
  });

  it('flags every forbidden term individually, across all stem variants', () => {
    for (const { term } of FORBIDDEN_PUBLIC_TERMS) {
      const samples = VIOLATING_SAMPLES[term];
      expect(samples, `term "${term}" has no violating samples`).toBeDefined();
      for (const sample of samples ?? []) {
        const violations = scanPublicCopy(sample);
        expect(violations, `sample "${sample}" should violate`).not.toEqual([]);
        expect(
          violations.map((v) => v.term),
          `sample "${sample}" should be attributed to "${term}"`,
        ).toContain(term);
      }
    }
  });

  it('has a violating sample set for exactly the canonical term list', () => {
    expect(Object.keys(VIOLATING_SAMPLES).sort()).toEqual(
      FORBIDDEN_PUBLIC_TERMS.map(({ term }) => term).sort(),
    );
  });

  it('reports the match position and surrounding context from the original text', () => {
    const text = 'A completely harmless start before the odds appear.';
    const [violation] = scanPublicCopy(text);
    expect(violation?.term).toBe('odds');
    expect(violation?.index).toBe(text.indexOf('odds'));
    expect(violation?.context).toContain('odds');
  });

  it('preserves indexes when guarded phrases are masked (spaces, not removal)', () => {
    const text = 'It is not a prediction, yet the odds remain listed.';
    const [violation] = scanPublicCopy(text);
    expect(violation?.term).toBe('odds');
    expect(violation?.index).toBe(text.indexOf('odds'));
  });

  it('returns an empty array for empty and clean text', () => {
    expect(scanPublicCopy('')).toEqual([]);
    expect(scanPublicCopy('Historical aggregates of past Philadelphia cases.')).toEqual([]);
  });

  it('matches multi-word terms case-insensitively across a single space', () => {
    expect(scanPublicCopy('the LIKELY SENTENCE here').map((v) => v.term)).toEqual([
      'likely sentence',
    ]);
    // Word-boundary discipline pins single-space matching; a line-wrapped
    // source is the caller's whitespace-collapse responsibility.
    expect(scanPublicCopy('likely\nsentence')).toEqual([]);
  });
});
