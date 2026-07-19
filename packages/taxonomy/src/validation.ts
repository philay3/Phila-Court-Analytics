import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

export interface TaxonomyCategory {
  code: string;
  displayName: string;
  definition: string;
  sortOrder: number;
  public: boolean;
}

export interface SeedFiles {
  outcome: unknown;
  sentencing: unknown;
  version: unknown;
}

export const EXPECTED_OUTCOME_CODES: readonly string[] = [
  'dismissed',
  'withdrawn',
  'guilty_plea',
  'guilty_verdict',
  'acquittal',
  'ard',
  'diversion',
  'other',
  'unknown',
];

export const EXPECTED_SENTENCING_CODES: readonly string[] = [
  'probation',
  'incarceration',
  'fine',
  'restitution',
  'community_service',
  'no_further_penalty',
  'costs_fees',
  'other',
  'unknown',
];

export const BANNED_TERMS: readonly string[] = [
  'predict',
  'odds',
  'likely',
  'win rate',
  'best judge',
  'worst judge',
  'score',
  'guarantee',
];

const SNAKE_CASE = /^[a-z]+(_[a-z]+)*$/;

// Official semver regex from semver.org — avoids adding a dependency.
const SEMVER =
  /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$/;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function validateCategoryFile(
  fileLabel: string,
  data: unknown,
  expectedCodes: readonly string[],
): string[] {
  const errors: string[] = [];
  if (!Array.isArray(data)) {
    return [`${fileLabel}: expected a JSON array of category records`];
  }

  const seenCodes = new Set<string>();
  const seenSortOrders = new Set<number>();

  data.forEach((entry, index) => {
    const label = `${fileLabel}[${index}]`;
    if (!isRecord(entry)) {
      errors.push(`${label}: expected an object`);
      return;
    }

    const { code, displayName, definition, sortOrder, public: isPublic } = entry;

    if (typeof code !== 'string' || code.length === 0) {
      errors.push(`${label}: "code" must be a non-empty string`);
    } else {
      if (!SNAKE_CASE.test(code)) {
        errors.push(`${label}: code "${code}" is not snake_case`);
      }
      if (seenCodes.has(code)) {
        errors.push(`${fileLabel}: duplicate code "${code}"`);
      }
      seenCodes.add(code);
    }

    if (typeof displayName !== 'string' || displayName.trim().length === 0) {
      errors.push(`${label}: "displayName" must be a non-empty string`);
    }

    if (typeof definition !== 'string' || definition.trim().length === 0) {
      errors.push(`${label}: "definition" must be a non-empty string`);
    } else {
      const lower = definition.toLowerCase();
      for (const term of BANNED_TERMS) {
        if (lower.includes(term)) {
          errors.push(`${label}: definition contains banned term "${term}"`);
        }
      }
    }

    if (typeof sortOrder !== 'number' || !Number.isInteger(sortOrder)) {
      errors.push(`${label}: "sortOrder" must be an integer`);
    } else {
      if (seenSortOrders.has(sortOrder)) {
        errors.push(`${fileLabel}: duplicate sortOrder ${sortOrder}`);
      }
      seenSortOrders.add(sortOrder);
    }

    if (typeof isPublic !== 'boolean') {
      errors.push(`${label}: "public" must be a boolean`);
    }
  });

  for (const expected of expectedCodes) {
    if (!seenCodes.has(expected)) {
      errors.push(`${fileLabel}: missing expected category code "${expected}"`);
    }
  }
  for (const code of seenCodes) {
    if (!expectedCodes.includes(code)) {
      errors.push(`${fileLabel}: unexpected category code "${code}"`);
    }
  }

  return errors;
}

export function validateVersion(data: unknown): string[] {
  const fileLabel = 'version.json';
  if (!isRecord(data)) {
    return [`${fileLabel}: expected a JSON object`];
  }
  const version = data.taxonomyVersion;
  if (typeof version !== 'string' || !SEMVER.test(version)) {
    return [`${fileLabel}: "taxonomyVersion" must be a valid semver string`];
  }
  return [];
}

export function validateAll(seeds: SeedFiles): string[] {
  return [
    ...validateCategoryFile('outcome-categories.json', seeds.outcome, EXPECTED_OUTCOME_CODES),
    ...validateCategoryFile(
      'sentencing-categories.json',
      seeds.sentencing,
      EXPECTED_SENTENCING_CODES,
    ),
    ...validateVersion(seeds.version),
  ];
}

const SEEDS_DIR = fileURLToPath(new URL('../seeds/', import.meta.url));

function readSeed(fileName: string): unknown {
  return JSON.parse(readFileSync(`${SEEDS_DIR}${fileName}`, 'utf8')) as unknown;
}

export function loadSeeds(): SeedFiles {
  return {
    outcome: readSeed('outcome-categories.json'),
    sentencing: readSeed('sentencing-categories.json'),
    version: readSeed('version.json'),
  };
}
