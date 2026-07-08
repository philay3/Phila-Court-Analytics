import { describe, expect, it } from 'vitest';

import { buildArtifacts } from './build.js';
import { EXPECTED_OUTCOME_CODES, EXPECTED_SENTENCING_CODES, loadSeeds } from './validation.js';

describe('buildArtifacts', () => {
  const artifacts = buildArtifacts(loadSeeds());

  it('emits JSON containing all categories, thin-data config, and the version', () => {
    const parsed = JSON.parse(artifacts.taxonomyJson) as {
      taxonomyVersion: string;
      outcomeCategories: Array<{ code: string }>;
      sentencingCategories: Array<{ code: string }>;
      thinData: { provisional: boolean };
    };

    expect(parsed.taxonomyVersion).toBe('1.0.0');
    expect(parsed.outcomeCategories.map((c) => c.code).sort()).toEqual(
      [...EXPECTED_OUTCOME_CODES].sort(),
    );
    expect(parsed.sentencingCategories.map((c) => c.code).sort()).toEqual(
      [...EXPECTED_SENTENCING_CODES].sort(),
    );
    expect(parsed.thinData.provisional).toBe(true);
  });

  it('emits TypeScript containing all category codes and the version', () => {
    for (const code of [...EXPECTED_OUTCOME_CODES, ...EXPECTED_SENTENCING_CODES]) {
      expect(artifacts.indexTs).toContain(`"code": "${code}"`);
    }
    expect(artifacts.indexTs).toContain('export const TAXONOMY_VERSION = "1.0.0"');
    expect(artifacts.indexTs).toContain('export interface TaxonomyCategory');
  });

  it('is deterministic across runs', () => {
    const again = buildArtifacts(loadSeeds());
    expect(again.taxonomyJson).toBe(artifacts.taxonomyJson);
    expect(again.indexTs).toBe(artifacts.indexTs);
  });

  it('orders categories by sortOrder', () => {
    const parsed = JSON.parse(artifacts.taxonomyJson) as {
      outcomeCategories: Array<{ sortOrder: number }>;
    };
    const orders = parsed.outcomeCategories.map((c) => c.sortOrder);
    expect(orders).toEqual([...orders].sort((a, b) => a - b));
  });
});
