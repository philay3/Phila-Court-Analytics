import { describe, expect, it } from 'vitest';
import {
  BROWSE_ALL_CHARGES_LINK_TEXT,
  CHARGE_DIRECTORY_UNAVAILABLE_MESSAGE,
  FEATURED_CHARGES_HEADING,
} from './charge-directory.js';
import { scanPublicCopy } from './copy-safety.js';

describe('charge-directory pinned copy', () => {
  it('pins the DP-5 featured-section strings to their sanctioned values', () => {
    expect(FEATURED_CHARGES_HEADING).toBe('Charges with the largest sample sizes');
    expect(BROWSE_ALL_CHARGES_LINK_TEXT).toBe('Browse all charges');
  });

  it('every pinned string scans clean', () => {
    for (const [name, value] of Object.entries({
      CHARGE_DIRECTORY_UNAVAILABLE_MESSAGE,
      FEATURED_CHARGES_HEADING,
      BROWSE_ALL_CHARGES_LINK_TEXT,
    })) {
      expect(scanPublicCopy(value), `${name} must scan clean`).toEqual([]);
    }
  });

  it('the new DP-5 strings contain no em dash (R4: the rule binds new copy)', () => {
    expect(FEATURED_CHARGES_HEADING).not.toContain('—');
    expect(BROWSE_ALL_CHARGES_LINK_TEXT).not.toContain('—');
  });
});
