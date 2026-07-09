import type { Kysely } from 'kysely';
import { describe, expect, it } from 'vitest';
import {
  GUARDED_DISCLAIMER_PHRASES,
  METHODOLOGY_SECTION_KEYS,
  scanPublicCopy,
  type MethodologyResponse,
} from '@pca/shared';
import { buildApp } from '../../app.js';
import type { PublicApiDatabase } from '../../db.js';
import { METHODOLOGY_CONTENT } from '../../content/methodology.js';

const METHODOLOGY_URL = '/api/v1/public/methodology';

// Poison handle: any use of the database throws. Every test in this file
// injects it, so a 200 anywhere is proof the handler chain performs no
// database access — regardless of whether DATABASE_URL is set.
function poisonDb(): Kysely<PublicApiDatabase> {
  return new Proxy({} as Kysely<PublicApiDatabase>, {
    get(_target, property) {
      throw new Error(`methodology endpoint touched the database (accessed ${String(property)})`);
    },
  });
}

async function getMethodology() {
  const app = buildApp({ logger: false, db: poisonDb() });
  return app.inject({ method: 'GET', url: METHODOLOGY_URL });
}

describe('GET /methodology', () => {
  it('returns 200 with no database access (poison DB injected)', async () => {
    const response = await getMethodology();
    expect(response.statusCode).toBe(200);
  });

  it('contains exactly the ten required sections', async () => {
    const body = (await getMethodology()).json<MethodologyResponse>();
    expect(Object.keys(body).sort()).toEqual(['sections']);
    expect(Object.keys(body.sections).sort()).toEqual([...METHODOLOGY_SECTION_KEYS].sort());
  });

  it('every section has exactly a non-empty heading and body', async () => {
    const body = (await getMethodology()).json<MethodologyResponse>();
    for (const key of METHODOLOGY_SECTION_KEYS) {
      const section = body.sections[key];
      expect(Object.keys(section).sort()).toEqual(['body', 'heading']);
      expect(section.heading.trim().length, `${key} heading`).toBeGreaterThan(0);
      expect(section.body.trim().length, `${key} body`).toBeGreaterThan(0);
    }
  });

  it('serves the content module verbatim (nothing stripped by serialization)', async () => {
    const body = (await getMethodology()).json<MethodologyResponse>();
    expect(body).toEqual(METHODOLOGY_CONTENT);
  });

  it('states the disclaimers explicitly', async () => {
    const body = (await getMethodology()).json<MethodologyResponse>();
    const notPrediction = `${body.sections.notPrediction.heading} ${body.sections.notPrediction.body}`;
    const notLegalAdvice = `${body.sections.notLegalAdvice.heading} ${body.sections.notLegalAdvice.body}`;
    expect(notPrediction).toMatch(/not a prediction/i);
    expect(notLegalAdvice).toMatch(/not legal advice|does not provide legal advice/i);
  });

  it('names the UJS portal source and the 2025-01-01 event-date anchor', async () => {
    const body = (await getMethodology()).json<MethodologyResponse>();
    expect(body.sections.dataSource.body).toMatch(/Unified Judicial System|UJS/);
    expect(body.sections.dataSource.body).toMatch(/Philadelphia/);
    expect(body.sections.dataRange.body).toMatch(/January 1, 2025/);
    expect(body.sections.dataRange.body).toMatch(/not the filing date/i);
  });

  it('contains no forbidden term outside the guarded disclaimer phrases', async () => {
    const response = await getMethodology();
    // All canonical terms come from the shared scanner (mask-then-scan).
    expect(scanPublicCopy(response.body)).toEqual([]);

    // Deliberate route-specific additions BEYOND the shared scanner:
    // methodology copy is held to a stricter vocabulary than the sitewide
    // locked list. None of these duplicates a locked term — bare best/worst/
    // win are intentionally broader than the locked "best judge"/"worst
    // judge"/"win rate" multi-word terms. Same mask-then-scan discipline,
    // using the shared guarded phrases.
    let text = response.body;
    for (const phrase of GUARDED_DISCLAIMER_PHRASES) {
      const escaped = phrase.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      text = text.replace(new RegExp(escaped, 'gi'), ' ');
    }
    const routeSpecificPatterns = [
      /\blikelihood\b/i,
      /\bprobabilit(?:y|ies)\b/i,
      /\bchances?\b/i,
      /\brank(?:s|ed|ing|ings)?\b/i,
      /\bbest\b/i,
      /\bworst\b/i,
      /\brecommend(?:s|ed|ation|ations)?\b/i,
      /\badvice\b/i,
      /\bwin(?:s|ning)?\b/i,
      /\blos(?:e|es|ing)\b/i,
    ];
    for (const pattern of routeSpecificPatterns) {
      expect(text).not.toMatch(pattern);
    }
  });

  it('mentions no internal system detail', async () => {
    const response = await getMethodology();
    const lowered = response.body.toLowerCase();
    // Substrings, not word boundaries: 'extract' catches extraction/extracted.
    for (const forbidden of ['parser', 'confidence', 'extract', 'review', 'workflow']) {
      expect(lowered, `internal detail leaked: ${forbidden}`).not.toContain(forbidden);
    }
  });
});
