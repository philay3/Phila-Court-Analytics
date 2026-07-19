import { describe, expect, it } from 'vitest';
import {
  AGGREGATE_RUN_LABEL_PREFIX,
  CONVICTION_GRADES_ITEM_SEPARATOR,
  CONVICTION_GRADES_LABEL_PREFIX,
  RECORDS_LABEL_PREFIX,
  SENTENCE_COMPONENTS_LABEL_PREFIX,
  SENTENCED_CONVICTIONS_LABEL_PREFIX,
  SENTENCING_DETAIL_CAPTION,
  SENTENCING_INDEX_CAPTION,
  SENTENCING_INDEX_CATEGORY_HEADER,
  SENTENCING_INDEX_COUNT_HEADER,
  SENTENCING_INDEX_MEDIAN_HEADER,
  SENTENCING_INDEX_PERCENTAGE_HEADER,
  SINGLE_GRADE_TEMPLATE,
  SINGLE_GRADE_UNGRADED_LINE,
  UNGRADED_GRADE_LABEL,
  WEDGE_DISCLOSURE_TEMPLATE,
  WEDGE_DISCLOSURE_TEMPLATE_SINGULAR,
  ZERO_SENTENCED_FALLBACK_SINGULAR,
  ZERO_SENTENCED_FALLBACK_TEMPLATE,
} from './result-display.js';
import { scanPublicCopy } from './copy-safety.js';

/**
 * Byte-pins for the 35.3 sanctioned string set. Every value here was
 * adjudicated in the framing review; a diff in this file means the copy
 * changed and must re-adjudicate.
 */
const SANCTIONED = {
  SENTENCING_INDEX_CAPTION:
    'Historical sentencing rates: when charges like this ended in conviction',
  SENTENCING_INDEX_CATEGORY_HEADER: 'Sentence category',
  SENTENCING_INDEX_COUNT_HEADER: 'Convictions',
  SENTENCING_INDEX_PERCENTAGE_HEADER: 'Percentage of sentenced convictions',
  SENTENCING_INDEX_MEDIAN_HEADER: 'Median (months)',
  SENTENCED_CONVICTIONS_LABEL_PREFIX: 'Sentenced convictions: ',
  WEDGE_DISCLOSURE_TEMPLATE:
    '{wedgeCount} of {convictions} recorded convictions ({wedgePercentage}) have no public sentencing record in the collected data and are not counted in the rates above.',
  WEDGE_DISCLOSURE_TEMPLATE_SINGULAR:
    '1 of {convictions} recorded convictions ({wedgePercentage}) has no public sentencing record in the collected data and is not counted in the rates above.',
  ZERO_SENTENCED_FALLBACK_TEMPLATE:
    'None of the {convictions} recorded convictions here has a public sentencing record in the collected data.',
  ZERO_SENTENCED_FALLBACK_SINGULAR:
    'The 1 recorded conviction here has no public sentencing record in the collected data.',
  CONVICTION_GRADES_LABEL_PREFIX: 'Conviction grades: ',
  CONVICTION_GRADES_ITEM_SEPARATOR: ' · ',
  SINGLE_GRADE_TEMPLATE: 'Every recorded conviction here is grade {grade}.',
  SINGLE_GRADE_UNGRADED_LINE: 'Every recorded conviction here has no recorded grade.',
  UNGRADED_GRADE_LABEL: 'no recorded grade',
  SENTENCING_DETAIL_CAPTION: 'Historical sentencing detail by sentence component',
  RECORDS_LABEL_PREFIX: 'Records: ',
  SENTENCE_COMPONENTS_LABEL_PREFIX: 'Sentence components: ',
  AGGREGATE_RUN_LABEL_PREFIX: 'Data release: ',
} as const;

const ACTUAL: Record<keyof typeof SANCTIONED, string> = {
  SENTENCING_INDEX_CAPTION,
  SENTENCING_INDEX_CATEGORY_HEADER,
  SENTENCING_INDEX_COUNT_HEADER,
  SENTENCING_INDEX_PERCENTAGE_HEADER,
  SENTENCING_INDEX_MEDIAN_HEADER,
  SENTENCED_CONVICTIONS_LABEL_PREFIX,
  WEDGE_DISCLOSURE_TEMPLATE,
  WEDGE_DISCLOSURE_TEMPLATE_SINGULAR,
  ZERO_SENTENCED_FALLBACK_TEMPLATE,
  ZERO_SENTENCED_FALLBACK_SINGULAR,
  CONVICTION_GRADES_LABEL_PREFIX,
  CONVICTION_GRADES_ITEM_SEPARATOR,
  SINGLE_GRADE_TEMPLATE,
  SINGLE_GRADE_UNGRADED_LINE,
  UNGRADED_GRADE_LABEL,
  SENTENCING_DETAIL_CAPTION,
  RECORDS_LABEL_PREFIX,
  SENTENCE_COMPONENTS_LABEL_PREFIX,
  AGGREGATE_RUN_LABEL_PREFIX,
};

describe('result-display pinned copy (35.3 sanctions)', () => {
  it('pins every sanctioned string byte-exact', () => {
    for (const [name, sanctioned] of Object.entries(SANCTIONED)) {
      expect(ACTUAL[name as keyof typeof SANCTIONED], name).toBe(sanctioned);
    }
  });

  it('every string scans clean', () => {
    for (const [name, value] of Object.entries(ACTUAL)) {
      expect(scanPublicCopy(value), `${name} must scan clean`).toEqual([]);
    }
  });

  it('contains no em dash (R4: the rule binds new copy)', () => {
    for (const [name, value] of Object.entries(ACTUAL)) {
      expect(value, `${name} must not contain an em dash`).not.toContain('—');
    }
  });

  it('singular variants carry their literal 1', () => {
    expect(WEDGE_DISCLOSURE_TEMPLATE_SINGULAR.startsWith('1 of ')).toBe(true);
    expect(ZERO_SENTENCED_FALLBACK_SINGULAR.startsWith('The 1 ')).toBe(true);
    expect(WEDGE_DISCLOSURE_TEMPLATE_SINGULAR).not.toContain('{wedgeCount}');
    expect(ZERO_SENTENCED_FALLBACK_SINGULAR).not.toContain('{convictions}');
  });
});
