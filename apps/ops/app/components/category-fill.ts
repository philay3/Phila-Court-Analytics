/**
 * Deterministic categorical fill assignment — a copy of
 * apps/web/app/components/category-fill.ts for the relocated ops dashboard
 * (task STATIC-2a). Apps share no code, so the mapping is duplicated verbatim;
 * the DistributionKind type is declared locally instead of imported from the
 * web app's definition-anchor module. No user-facing strings live here.
 */
export type DistributionKind = 'outcome' | 'sentencing';

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
