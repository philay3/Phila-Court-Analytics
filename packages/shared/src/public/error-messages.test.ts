import { describe, expect, it } from 'vitest';
import { PUBLIC_ERROR_CODES } from '../errors.js';
import { CHARGE_NOT_FOUND_MESSAGE, CHARGE_RESULT_UNAVAILABLE_MESSAGE } from './charge-result.js';
import { JUDGE_NOT_FOUND_MESSAGE, JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE } from './judge-result.js';
import { CHARGE_SENTENCING_UNAVAILABLE_MESSAGE } from './charge-result.js';
import { scanPublicCopy } from './copy-safety.js';
import { FETCH_FAILURE_MESSAGE, PUBLIC_ERROR_MESSAGES } from './error-messages.js';

describe('PUBLIC_ERROR_MESSAGES', () => {
  it('covers exactly the nine catalog codes (adding a tenth fails loudly)', () => {
    expect(Object.keys(PUBLIC_ERROR_MESSAGES).sort()).toEqual(
      Object.values(PUBLIC_ERROR_CODES).sort(),
    );
  });

  it('references the pinned 8.2 judge-specific literal by identity, not a re-typed string', () => {
    expect(PUBLIC_ERROR_MESSAGES.JUDGE_SPECIFIC_RESULT_UNAVAILABLE).toBe(
      JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE,
    );
  });

  it('references the other four pinned contract literals by identity', () => {
    expect(PUBLIC_ERROR_MESSAGES.CHARGE_NOT_FOUND).toBe(CHARGE_NOT_FOUND_MESSAGE);
    expect(PUBLIC_ERROR_MESSAGES.JUDGE_NOT_FOUND).toBe(JUDGE_NOT_FOUND_MESSAGE);
    expect(PUBLIC_ERROR_MESSAGES.CHARGE_RESULT_UNAVAILABLE).toBe(CHARGE_RESULT_UNAVAILABLE_MESSAGE);
    expect(PUBLIC_ERROR_MESSAGES.SENTENCING_RESULT_UNAVAILABLE).toBe(
      CHARGE_SENTENCING_UNAVAILABLE_MESSAGE,
    );
  });

  it('every message value scans clean, including the fetch-failure message', () => {
    for (const [code, message] of Object.entries(PUBLIC_ERROR_MESSAGES)) {
      expect(scanPublicCopy(message), `${code} message must scan clean`).toEqual([]);
    }
    expect(scanPublicCopy(FETCH_FAILURE_MESSAGE), 'FETCH_FAILURE_MESSAGE must scan clean').toEqual(
      [],
    );
  });
});
