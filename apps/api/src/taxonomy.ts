import { OUTCOME_CATEGORIES, SENTENCING_CATEGORIES } from '@pca/taxonomy';
import { PUBLIC_ERROR_CODES } from '@pca/shared';
import { publicError } from './public-error.js';

export interface CategoryPresentation {
  displayName: string;
  sortOrder: number;
}

function publicCategoryMap(
  categories: readonly {
    code: string;
    displayName: string;
    sortOrder: number;
    public: boolean;
  }[],
): Map<string, CategoryPresentation> {
  return new Map(
    categories
      .filter((category) => category.public)
      .map((category) => [
        category.code,
        { displayName: category.displayName, sortOrder: category.sortOrder },
      ]),
  );
}

const PRESENTATION = {
  outcome: publicCategoryMap(OUTCOME_CATEGORIES),
  sentencing: publicCategoryMap(SENTENCING_CATEGORIES),
} as const;

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
