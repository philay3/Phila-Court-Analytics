import { OUTCOME_CATEGORIES, SENTENCING_CATEGORIES, type TaxonomyCategory } from '@pca/taxonomy';
import { PUBLIC_ERROR_CODES, type DefinitionEntry } from '@pca/shared';
import { publicError } from './public-error.js';

export interface CategoryPresentation {
  displayName: string;
  sortOrder: number;
}

// The single public filter for taxonomy categories: everything this module
// exposes (presentation maps, definition entries) derives from these arrays,
// sorted by sortOrder ascending.
function publicCategories(categories: readonly TaxonomyCategory[]): TaxonomyCategory[] {
  return categories
    .filter((category) => category.public)
    .toSorted((a, b) => a.sortOrder - b.sortOrder);
}

const PUBLIC_CATEGORIES = {
  outcome: publicCategories(OUTCOME_CATEGORIES),
  sentencing: publicCategories(SENTENCING_CATEGORIES),
} as const;

function presentationMap(
  categories: readonly TaxonomyCategory[],
): Map<string, CategoryPresentation> {
  return new Map(
    categories.map((category) => [
      category.code,
      { displayName: category.displayName, sortOrder: category.sortOrder },
    ]),
  );
}

const PRESENTATION = {
  outcome: presentationMap(PUBLIC_CATEGORIES.outcome),
  sentencing: presentationMap(PUBLIC_CATEGORIES.sentencing),
} as const;

function definitionEntries(categories: readonly TaxonomyCategory[]): DefinitionEntry[] {
  return categories.map(({ code, displayName, definition, sortOrder }) => ({
    code,
    displayName,
    definition,
    sortOrder,
  }));
}

/**
 * Public-only definition entries for GET /public/definitions, computed once at
 * module load (the response is static per deploy). The internal `public` flag
 * is stripped here; the response schema rejects it as defense in depth.
 * Mutable arrays because Fastify's reply type for the response schema expects
 * them; nothing mutates these in practice.
 */
export const PUBLIC_DEFINITIONS: {
  outcomes: DefinitionEntry[];
  sentencing: DefinitionEntry[];
} = {
  outcomes: definitionEntries(PUBLIC_CATEGORIES.outcome),
  sentencing: definitionEntries(PUBLIC_CATEGORIES.sentencing),
};

export type CategoryKind = keyof typeof PRESENTATION;

/**
 * Resolves a stored aggregate category code for public presentation. The maps
 * hold `public: true` taxonomy entries only, so a code unknown to the
 * taxonomy artifact and a known-but-internal code (e.g. "unknown") are the
 * same integrity failure: INTERNAL_ERROR — never a fabricated display name.
 * Naming the code here is safe: the central handler replaces every 5xx
 * message with a generic one, so it reaches server logs only.
 */
export function resolvePublicCategory(kind: CategoryKind, code: string): CategoryPresentation {
  const presentation = PRESENTATION[kind].get(code);
  if (!presentation) {
    throw publicError(
      PUBLIC_ERROR_CODES.INTERNAL_ERROR,
      `aggregate row carries unknown or non-public ${kind} category code "${code}"`,
    );
  }
  return presentation;
}
