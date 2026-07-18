/**
 * Deterministic categorical fill assignment (task DP-2, acceptance
 * criterion 8). Purely presentational: maps a served category code to one
 * of the eight Tol-muted fill utilities defined in the @theme block. The
 * mapping is a fixed code→token table keyed by taxonomy sortOrder, so the
 * same category always renders the same color regardless of the data —
 * color identifies categories, never valence (design integrity rule).
 *
 * Grey (cat-8) is pinned to `other` in both taxonomies; any unmapped code
 * (a future taxonomy addition) deterministically falls back to grey too.
 * No user-facing strings live here.
 */
import type { DistributionKind } from '../lib/definition-anchor';

const OUTCOME_FILL: Readonly<Record<string, string>> = {
  dismissed: 'bg-cat-1',
  withdrawn: 'bg-cat-2',
  guilty_plea: 'bg-cat-3',
  guilty_verdict: 'bg-cat-4',
  acquittal: 'bg-cat-5',
  ard: 'bg-cat-6',
  diversion: 'bg-cat-7',
  other: 'bg-cat-8',
};

const SENTENCING_FILL: Readonly<Record<string, string>> = {
  probation: 'bg-cat-1',
  incarceration: 'bg-cat-2',
  fine: 'bg-cat-3',
  restitution: 'bg-cat-4',
  community_service: 'bg-cat-5',
  no_further_penalty: 'bg-cat-6',
  costs_fees: 'bg-cat-7',
  other: 'bg-cat-8',
};

export function categoryFillClass(kind: DistributionKind, categoryCode: string): string {
  const map = kind === 'outcome' ? OUTCOME_FILL : SENTENCING_FILL;
  return map[categoryCode] ?? 'bg-cat-8';
}
