import type { Kysely } from 'kysely';
import { describe, expect, it } from 'vitest';
import { OUTCOME_CATEGORIES, SENTENCING_CATEGORIES, TAXONOMY_VERSION } from '@pca/taxonomy';
import type { DefinitionsResponse } from '@pca/shared';
import { buildApp } from '../../app.js';
import type { PublicApiDatabase } from '../../db.js';

const DEFINITIONS_URL = '/api/v1/public/definitions';

// Poison handle: any use of the database throws. Every test in this file
// injects it, so a 200 anywhere is proof the handler chain performs no
// database access — regardless of whether DATABASE_URL is set.
function poisonDb(): Kysely<PublicApiDatabase> {
  return new Proxy({} as Kysely<PublicApiDatabase>, {
    get(_target, property) {
      throw new Error(`definitions endpoint touched the database (accessed ${String(property)})`);
    },
  });
}

function testApp() {
  return buildApp({ logger: false, db: poisonDb() });
}

async function getDefinitions() {
  const response = await testApp().inject({ method: 'GET', url: DEFINITIONS_URL });
  return response;
}

describe('GET /definitions', () => {
  it('returns 200 with no database access (poison DB injected)', async () => {
    const response = await getDefinitions();
    expect(response.statusCode).toBe(200);
  });

  it('returns exactly taxonomyVersion, outcomes, and sentencing', async () => {
    const body = (await getDefinitions()).json<DefinitionsResponse>();
    expect(Object.keys(body).sort()).toEqual(['outcomes', 'sentencing', 'taxonomyVersion']);
    expect(body.outcomes.length).toBeGreaterThan(0);
    expect(body.sentencing.length).toBeGreaterThan(0);
  });

  it('every entry has exactly code, displayName, definition, sortOrder', async () => {
    const body = (await getDefinitions()).json<DefinitionsResponse>();
    for (const entry of [...body.outcomes, ...body.sentencing]) {
      expect(Object.keys(entry).sort()).toEqual(['code', 'definition', 'displayName', 'sortOrder']);
      expect(typeof entry.code).toBe('string');
      expect(typeof entry.displayName).toBe('string');
      expect(typeof entry.definition).toBe('string');
      expect(Number.isInteger(entry.sortOrder)).toBe(true);
    }
  });

  it('contains exactly the public taxonomy categories and no internal ones', async () => {
    const body = (await getDefinitions()).json<DefinitionsResponse>();

    const internalOutcomes = OUTCOME_CATEGORIES.filter((c) => !c.public).map((c) => c.code);
    const internalSentencing = SENTENCING_CATEGORIES.filter((c) => !c.public).map((c) => c.code);
    expect(internalOutcomes.length).toBeGreaterThan(0);
    expect(internalSentencing.length).toBeGreaterThan(0);

    const outcomeCodes = body.outcomes.map((entry) => entry.code);
    const sentencingCodes = body.sentencing.map((entry) => entry.code);
    expect(outcomeCodes).toEqual(
      expect.arrayContaining(OUTCOME_CATEGORIES.filter((c) => c.public).map((c) => c.code)),
    );
    expect(sentencingCodes).toEqual(
      expect.arrayContaining(SENTENCING_CATEGORIES.filter((c) => c.public).map((c) => c.code)),
    );
    for (const code of internalOutcomes) {
      expect(outcomeCodes).not.toContain(code);
    }
    for (const code of internalSentencing) {
      expect(sentencingCodes).not.toContain(code);
    }
  });

  it('orders both arrays by sortOrder ascending', async () => {
    const body = (await getDefinitions()).json<DefinitionsResponse>();
    for (const entries of [body.outcomes, body.sentencing]) {
      const sortOrders = entries.map((entry) => entry.sortOrder);
      expect(sortOrders).toEqual([...sortOrders].sort((a, b) => a - b));
    }
  });

  it('reports the taxonomy artifact version exactly', async () => {
    const body = (await getDefinitions()).json<DefinitionsResponse>();
    expect(body.taxonomyVersion).toBe(TAXONOMY_VERSION);
  });

  it('contains no prediction, odds, ranking, or legal-advice language', async () => {
    const response = await getDefinitions();
    // Belt-and-braces copy-safety check against the actual response body.
    // Word-boundary regexes, not substrings, so innocent text ("withdrew",
    // "losses") can never false-positive as copy evolves.
    const forbiddenPatterns = [
      /\bpredict(?:s|ed|ion|ions|ive)?\b/i,
      /\bodds\b/i,
      /\blikelihood\b/i,
      /\bprobabilit(?:y|ies)\b/i,
      /\bchances?\b/i,
      /\brank(?:s|ed|ing|ings)?\b/i,
      /\bbest\b/i,
      /\bworst\b/i,
      /\brecommend(?:s|ed|ation|ations)?\b/i,
      /\badvice\b/i,
      /\bguarantee(?:s|d)?\b/i,
      /\bwin(?:s|ning)?\b/i,
      /\blos(?:e|es|ing)\b/i,
    ];
    for (const pattern of forbiddenPatterns) {
      expect(response.body).not.toMatch(pattern);
    }
  });
});
