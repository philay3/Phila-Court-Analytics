import { describe, expect, it } from 'vitest';
import { scanPublicCopy } from './copy-safety.js';
import {
  CHARGES_DIRECTORY_ERROR_BODY,
  CONTENT_PAGE_FAILURE_HEADINGS,
  ERROR_BOUNDARY_COPY,
} from './web-failure-copy.js';

describe('web failure-state copy pinned for the export gate (STATIC-2c)', () => {
  it('pins the sanctioned strings', () => {
    expect(ERROR_BOUNDARY_COPY).toEqual({
      heading: 'Something went wrong',
      body: 'We could not load this page. Please try again.',
      retryText: 'Try again',
    });
    expect(CHARGES_DIRECTORY_ERROR_BODY).toBe('Available charges could not load.');
    expect(CONTENT_PAGE_FAILURE_HEADINGS).toEqual({
      definitions: 'Definitions are unavailable',
      methodology: 'Methodology is unavailable',
      dataCoverage: 'Data coverage is unavailable',
    });
  });

  it('every string scans clean', () => {
    const all = {
      ...ERROR_BOUNDARY_COPY,
      CHARGES_DIRECTORY_ERROR_BODY,
      ...CONTENT_PAGE_FAILURE_HEADINGS,
    };
    for (const [name, value] of Object.entries(all)) {
      expect(scanPublicCopy(value), `${name} must scan clean`).toEqual([]);
    }
  });
});
