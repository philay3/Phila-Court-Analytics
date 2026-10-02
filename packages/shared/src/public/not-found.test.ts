import { describe, expect, it } from 'vitest';
import { scanPublicCopy } from './copy-safety.js';
import {
  ROOT_NOT_FOUND_HEADING,
  ROOT_NOT_FOUND_HOME_LINK_TEXT,
  ROOT_NOT_FOUND_MESSAGE,
} from './not-found.js';

describe('root not-found pinned copy (STATIC-2b)', () => {
  it('pins the sanctioned strings', () => {
    expect(ROOT_NOT_FOUND_HEADING).toBe('Page not found');
    expect(ROOT_NOT_FOUND_MESSAGE).toBe(
      'No page exists at this address. It may name a charge or judge that is not in the published data, or the link may be out of date.',
    );
    expect(ROOT_NOT_FOUND_HOME_LINK_TEXT).toBe('Return to search');
  });

  it('every string scans clean and carries no em dash', () => {
    for (const [name, value] of Object.entries({
      ROOT_NOT_FOUND_HEADING,
      ROOT_NOT_FOUND_MESSAGE,
      ROOT_NOT_FOUND_HOME_LINK_TEXT,
    })) {
      expect(scanPublicCopy(value), `${name} must scan clean`).toEqual([]);
      expect(value).not.toContain('—');
    }
  });
});
