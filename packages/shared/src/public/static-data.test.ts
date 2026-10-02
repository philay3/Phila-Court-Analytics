import { describe, expect, it } from 'vitest';
import { SEARCH_INDEX_DATA_PATH, STATIC_DATA_DIR, chargeJudgeDataPath } from './static-data.js';

describe('static-export data paths (STATIC-2b)', () => {
  it('pins the top-level data folder and the index path', () => {
    expect(STATIC_DATA_DIR).toBe('data');
    expect(SEARCH_INDEX_DATA_PATH).toBe('/data/search-index.json');
  });

  it('builds a per-charge path under data/charges with the slug encoded', () => {
    expect(chargeJudgeDataPath('retail-theft')).toBe('/data/charges/retail-theft.json');
    expect(chargeJudgeDataPath('a b/c')).toBe('/data/charges/a%20b%2Fc.json');
  });
});
