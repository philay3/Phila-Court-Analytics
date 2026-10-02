import { describe, expect, it } from 'vitest';
import type { SearchIndexCharge, SearchIndexJudge } from './search-index.js';
import {
  clampSearchLimit,
  judgesWithResultsFor,
  matchCharges,
  matchJudges,
  normalizeSearchQuery,
} from './search-match.js';

/**
 * Fixture roster (tier-1 rules): invented offenses and obviously fictional
 * judges — no real statute, roster entry, or person. Names are plain ASCII with
 * distinct leading letters so no test depends on collation tiebreaks.
 *
 * Each rank case of the repository SQL (charge-search.ts:65-82, judge-search.ts
 * :58-73) is locked by exactly one test below; the task report tabulates them.
 */
const CHARGES: SearchIndexCharge[] = [
  {
    slug: 'kite-string-tampering',
    displayName: 'Kite String Tampering',
    statuteCode: '99 § 1002',
    aliases: [],
  },
  {
    slug: 'unlawful-kite-flying',
    displayName: 'Unlawful Kite Flying',
    statuteCode: '99 § 1001',
    grade: 'M3',
    aliases: ['box kite offense'],
  },
  {
    slug: 'reckless-skipping',
    displayName: 'Reckless Skipping',
    statuteCode: '99 § 2001(a)',
    aliases: ['rapid hopping'],
  },
  {
    slug: 'skipping-in-a-library',
    displayName: 'Skipping in a Library',
    statuteCode: '99 § 2002',
    aliases: ['hop in the stacks', 'library hop'],
  },
  {
    slug: 'possession-of-a-loud-hat',
    displayName: 'Possession of a Loud Hat',
    statuteCode: '99 § 3003',
    grade: 'S',
    aliases: ['hat noise', 'loud headwear'],
  },
  { slug: 'hat-noise-conspiracy', displayName: 'Hat Noise Conspiracy', aliases: ['noisy hats'] },
  {
    slug: 'alpha-50-percent-sign',
    displayName: 'Alpha 50% Sign',
    statuteCode: '99 § 5050',
    aliases: [],
  },
  { slug: 'under-score-statute', displayName: 'Under_Score Statute', aliases: [] },
  { slug: 'long-alias-holder', displayName: 'Long Alias Holder', aliases: ['y'.repeat(100)] },
  ...Array.from({ length: 26 }, (_, i) => {
    const nn = String(i + 1).padStart(2, '0');
    return { slug: `cap-case-${nn}`, displayName: `Cap Case ${nn}`, aliases: [] };
  }),
];

const JUDGES: SearchIndexJudge[] = [
  { slug: 'judge-ada-quill', displayName: 'Judge Ada Quill', aliases: ['A. Quill'] },
  { slug: 'judge-quillon-bast', displayName: 'Judge Quillon Bast', aliases: [] },
  {
    slug: 'judge-mira-stone',
    displayName: 'Judge Mira Stone',
    aliases: ['M. Stone', 'Stone, Mira'],
  },
  { slug: 'judge-ora-flint', displayName: 'Judge Ora Flint', aliases: ['Flint-Stone, Ora'] },
];

const index = { charges: CHARGES, judges: JUDGES };
const slugs = (rows: { slug: string }[]) => rows.map((r) => r.slug);

describe('query rule (services: trim, then 1–100 characters)', () => {
  it('empty and whitespace-only queries return no results', () => {
    expect(normalizeSearchQuery('')).toBeNull();
    expect(normalizeSearchQuery('   ')).toBeNull();
    expect(matchCharges(index, '')).toEqual([]);
    expect(matchCharges(index, '   ')).toEqual([]);
    expect(matchJudges(index, '\t\n')).toEqual([]);
  });

  it('a 101-character query returns no results; exactly 100 is processed', () => {
    expect(matchCharges(index, 'y'.repeat(101))).toEqual([]);
    expect(matchCharges(index, 'y'.repeat(100))).toEqual([
      {
        slug: 'long-alias-holder',
        displayName: 'Long Alias Holder',
        matchedAlias: 'y'.repeat(100),
      },
    ]);
  });

  it('trims before matching, like the service', () => {
    expect(slugs(matchCharges(index, '  kite string tampering  '))).toEqual([
      'kite-string-tampering',
    ]);
  });
});

describe('limit (schema: default 10, maximum 25)', () => {
  it('defaults to 10 and caps at 25', () => {
    expect(clampSearchLimit()).toBe(10);
    expect(clampSearchLimit(25)).toBe(25);
    expect(clampSearchLimit(26)).toBe(25);
    expect(clampSearchLimit(100)).toBe(25);
    expect(clampSearchLimit(0)).toBe(1);
    expect(clampSearchLimit(3.9)).toBe(3);
    expect(matchCharges(index, 'cap case')).toHaveLength(10);
    expect(matchCharges(index, 'cap case', 100)).toHaveLength(25);
    expect(matchCharges(index, 'cap case', 3)).toHaveLength(3);
  });
});

describe('charge rank cases (repositories/charge-search.ts:65-82)', () => {
  it('rank 1a: case-insensitive equality on the display name', () => {
    expect(matchCharges(index, 'KITE string tampering')).toEqual([
      {
        slug: 'kite-string-tampering',
        displayName: 'Kite String Tampering',
        statuteCode: '99 § 1002',
      },
    ]);
  });

  it('rank 1b: equality on the statute code (statute-only match carries no matchedAlias)', () => {
    expect(matchCharges(index, '99 § 1002')).toEqual([
      {
        slug: 'kite-string-tampering',
        displayName: 'Kite String Tampering',
        statuteCode: '99 § 1002',
      },
    ]);
  });

  it('rank 1c: equality on an alias ranks above a name prefix, with matchedAlias', () => {
    expect(matchCharges(index, 'hat noise')).toEqual([
      {
        slug: 'possession-of-a-loud-hat',
        displayName: 'Possession of a Loud Hat',
        statuteCode: '99 § 3003',
        grade: 'S',
        matchedAlias: 'hat noise',
      },
      { slug: 'hat-noise-conspiracy', displayName: 'Hat Noise Conspiracy' },
    ]);
  });

  it('rank 2a: display-name prefix ranks above a name substring; a matched name never shows an alias', () => {
    // "Unlawful Kite Flying" contains the query in its name (rank 3) and in an
    // alias ("box kite offense", also substring) — the alias cannot promote it
    // and is not reported because the name itself matched.
    expect(matchCharges(index, 'kite')).toEqual([
      {
        slug: 'kite-string-tampering',
        displayName: 'Kite String Tampering',
        statuteCode: '99 § 1002',
      },
      {
        slug: 'unlawful-kite-flying',
        displayName: 'Unlawful Kite Flying',
        statuteCode: '99 § 1001',
        grade: 'M3',
      },
    ]);
  });

  it('rank 2b: statute-code prefix, no matchedAlias, equal ranks ordered by display name', () => {
    expect(matchCharges(index, '99 § 20')).toEqual([
      { slug: 'reckless-skipping', displayName: 'Reckless Skipping', statuteCode: '99 § 2001(a)' },
      {
        slug: 'skipping-in-a-library',
        displayName: 'Skipping in a Library',
        statuteCode: '99 § 2002',
      },
    ]);
  });

  it('rank 2c: alias prefix ranks above an alias substring; matchedAlias is the alphabetically first matching alias', () => {
    // "Skipping in a Library" matches via two aliases ("hop in the stacks" as a
    // prefix, "library hop" as a substring): rank 2, and the reported alias is
    // the minimum of the MATCHING aliases. "Reckless Skipping" matches only via
    // "rapid hopping" (substring): rank 3.
    expect(matchCharges(index, 'hop')).toEqual([
      {
        slug: 'skipping-in-a-library',
        displayName: 'Skipping in a Library',
        statuteCode: '99 § 2002',
        matchedAlias: 'hop in the stacks',
      },
      {
        slug: 'reckless-skipping',
        displayName: 'Reckless Skipping',
        statuteCode: '99 § 2001(a)',
        matchedAlias: 'rapid hopping',
      },
    ]);
  });

  it('rank 3a: display-name substring, no matchedAlias', () => {
    expect(matchCharges(index, 'string')).toEqual([
      {
        slug: 'kite-string-tampering',
        displayName: 'Kite String Tampering',
        statuteCode: '99 § 1002',
      },
    ]);
  });

  it('rank 3b: statute-code substring, no matchedAlias', () => {
    expect(matchCharges(index, '1002')).toEqual([
      {
        slug: 'kite-string-tampering',
        displayName: 'Kite String Tampering',
        statuteCode: '99 § 1002',
      },
    ]);
  });

  it('rank 3c: alias substring, with matchedAlias', () => {
    expect(matchCharges(index, 'stacks')).toEqual([
      {
        slug: 'skipping-in-a-library',
        displayName: 'Skipping in a Library',
        statuteCode: '99 § 2002',
        matchedAlias: 'hop in the stacks',
      },
    ]);
  });

  it('treats % and _ literally (the SQL escapes LIKE wildcards)', () => {
    expect(slugs(matchCharges(index, '50%'))).toEqual(['alpha-50-percent-sign']);
    expect(slugs(matchCharges(index, '%'))).toEqual(['alpha-50-percent-sign']);
    expect(slugs(matchCharges(index, '_'))).toEqual(['under-score-statute']);
  });

  it('returns nothing when no field matches', () => {
    expect(matchCharges(index, 'zzz')).toEqual([]);
  });
});

describe('judge rank cases (repositories/judge-search.ts:58-73)', () => {
  it('rank 1a: case-insensitive equality on the display name', () => {
    expect(matchJudges(index, 'JUDGE ada quill')).toEqual([
      { slug: 'judge-ada-quill', displayName: 'Judge Ada Quill' },
    ]);
  });

  it('rank 1b: equality on an alias, with matchedAlias', () => {
    expect(matchJudges(index, 'a. quill')).toEqual([
      { slug: 'judge-ada-quill', displayName: 'Judge Ada Quill', matchedAlias: 'A. Quill' },
    ]);
  });

  it('rank 2a: display-name prefix', () => {
    expect(matchJudges(index, 'judge q')).toEqual([
      { slug: 'judge-quillon-bast', displayName: 'Judge Quillon Bast' },
    ]);
  });

  it('rank 2b: alias prefix, with matchedAlias', () => {
    expect(matchJudges(index, 'm. st')).toEqual([
      { slug: 'judge-mira-stone', displayName: 'Judge Mira Stone', matchedAlias: 'M. Stone' },
    ]);
  });

  it('rank 3a: display-name substring, equal ranks ordered by display name, no matchedAlias', () => {
    expect(matchJudges(index, 'quill')).toEqual([
      { slug: 'judge-ada-quill', displayName: 'Judge Ada Quill' },
      { slug: 'judge-quillon-bast', displayName: 'Judge Quillon Bast' },
    ]);
  });

  it('rank 3b: alias substring with matchedAlias, beside a name substring without one', () => {
    expect(matchJudges(index, 'stone')).toEqual([
      { slug: 'judge-mira-stone', displayName: 'Judge Mira Stone' },
      { slug: 'judge-ora-flint', displayName: 'Judge Ora Flint', matchedAlias: 'Flint-Stone, Ora' },
    ]);
  });

  it('applies the same query rule and limit cap', () => {
    expect(matchJudges(index, '')).toEqual([]);
    expect(matchJudges(index, 'x'.repeat(101))).toEqual([]);
    expect(matchJudges(index, 'judge', 100)).toHaveLength(4);
    expect(matchJudges(index, 'judge', 2)).toHaveLength(2);
  });

  it('never returns an id or statute fields for judges', () => {
    for (const row of matchJudges(index, 'judge', 25)) {
      expect(Object.keys(row).sort()).toEqual(
        row.matchedAlias === undefined
          ? ['displayName', 'slug']
          : ['displayName', 'matchedAlias', 'slug'],
      );
    }
  });
});

describe('judgesWithResultsFor (STATIC-2b pin 4)', () => {
  const pairs = [
    { chargeSlug: 'reckless-skipping', judgeSlug: 'judge-mira-stone' },
    { chargeSlug: 'reckless-skipping', judgeSlug: 'judge-ada-quill' },
    { chargeSlug: 'kite-string-tampering', judgeSlug: 'judge-ora-flint' },
  ];

  it('returns the paired judges for a charge in index order, and none for an unpaired charge', () => {
    expect(slugs(judgesWithResultsFor({ judges: JUDGES, pairs }, 'reckless-skipping'))).toEqual([
      'judge-ada-quill',
      'judge-mira-stone',
    ]);
    expect(judgesWithResultsFor({ judges: JUDGES, pairs }, 'under-score-statute')).toEqual([]);
  });

  it('ignores pairs whose judge is not in the judge list', () => {
    const stray = [{ chargeSlug: 'reckless-skipping', judgeSlug: 'judge-not-listed' }];
    expect(judgesWithResultsFor({ judges: JUDGES, pairs: stray }, 'reckless-skipping')).toEqual([]);
  });
});
