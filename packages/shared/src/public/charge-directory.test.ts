import { describe, expect, it } from 'vitest';
import {
  BROWSE_ALL_CHARGES_LINK_TEXT,
  CHARGE_DIRECTORY_UNAVAILABLE_MESSAGE,
  FEATURED_CHARGES_HEADING,
  RECORDED_OUTCOMES_LABEL_PREFIX,
} from './charge-directory.js';
import { scanPublicCopy } from './copy-safety.js';

describe('charge-directory pinned copy', () => {
  it('pins the DP-5 strings to their sanctioned values (Amendment 1 forms)', () => {
    expect(FEATURED_CHARGES_HEADING).toBe('Find your charge');
    expect(BROWSE_ALL_CHARGES_LINK_TEXT).toBe('Browse all charges');
    expect(RECORDED_OUTCOMES_LABEL_PREFIX).toBe('Recorded outcomes: ');
  });

  it('every pinned string scans clean', () => {
    for (const [name, value] of Object.entries({
      CHARGE_DIRECTORY_UNAVAILABLE_MESSAGE,
      FEATURED_CHARGES_HEADING,
      BROWSE_ALL_CHARGES_LINK_TEXT,
      RECORDED_OUTCOMES_LABEL_PREFIX,
    })) {
      expect(scanPublicCopy(value), `${name} must scan clean`).toEqual([]);
    }
  });

  it('the new DP-5 strings contain no em dash (R4: the rule binds new copy)', () => {
    expect(FEATURED_CHARGES_HEADING).not.toContain('—');
    expect(BROWSE_ALL_CHARGES_LINK_TEXT).not.toContain('—');
    expect(RECORDED_OUTCOMES_LABEL_PREFIX).not.toContain('—');
  });
});
