# Task 3.2 — Create Shared API Types Package

## Goal

Create `packages/shared` (`@pca/shared`): the single source of truth for
public API contracts. Public response shapes are defined as TypeBox schemas
with derived static types, so `@pca/api` gets runtime JSON Schema validation
and `@pca/web` gets compile-time types from one definition. Category codes
are derived from `@pca/taxonomy` generated artifacts — never re-declared.

## Context

- Monorepo, TS base tooling, ESLint/Prettier, Vitest are set up. TypeScript
  lives at the root only; use the root binary.
- `@pca/taxonomy` exists (task 3.1). Its `generate` script emits TypeScript
  and JSON artifacts into its `generated/` directory, including outcome
  categories, sentencing categories, and the taxonomy version string.
  ESLint already ignores `**/generated/`.
- TypeBox is the locked validation library (already used in `@pca/api` for
  the /health schema). This package makes it the contract layer.
- This package has NO database dependency and NO Fastify dependency. It is
  pure schemas + types.
- `@pca/api` and `@pca/web` will import from this package starting in
  Sprint 2. Do NOT modify apps/api or apps/web in this task.

## Reminder: return an implementation plan BEFORE writing any code.

## Scope

### 1. Package scaffold

- `packages/shared/` with `package.json` (`@pca/shared`), tsconfig extending
  the root base config, README describing the package's role and the rule
  that public contracts live here and nowhere else.
- Dependencies: `@sinclair/typebox`, and workspace dependency
  `@pca/taxonomy` (`workspace:*`).

### 2. Common building blocks (`src/public/common.ts` or similar)

TypeBox schemas + derived static types for:

- `SampleSize` — integer, minimum 0.
- `DateRange` — object with `start` and `end`, ISO date strings
  (`format: 'date'`), `additionalProperties: false`.
- `TaxonomyVersion` — string (semver-shaped; a pattern check is acceptable,
  exact semver grammar is not required).
- `ThinDataStatus` — boolean.
- `DistributionEntry` — object: `categoryCode` (from taxonomy codes — see
  rule below), `displayName` (string), `count` (integer ≥ 0), `percentage`
  (number 0–100). `additionalProperties: false`. Counts and percentages are
  ALWAYS returned together, never one without the other.
- `Distribution` — object wrapping: `entries` (array of DistributionEntry),
  `sampleSize`, `dateRange`, `thinData`. Each distribution carries its OWN
  sample size, date range, and thin-data status, because sentencing sample
  size differs from outcome sample size.

### 3. Category code derivation rule

- Outcome category codes and sentencing category codes used in schemas MUST
  be derived from the `@pca/taxonomy` generated TypeScript artifact (e.g.
  build a `Type.Union` of `Type.Literal`s from the exported code list, or
  equivalent).
- Hand-maintained duplicate lists of category codes are FORBIDDEN in this
  package. If the generated artifact does not export what you need, stop and
  report — do not work around it by copying values.

### 4. Public search contracts (`src/public/search.ts`)

- `ChargeSuggestion` — `chargeId`, `displayName`, `slug`. Nothing else.
- `ChargeSearchResponse` — array of suggestions (+ any envelope fields you
  propose in the plan).
- `JudgeSuggestion` — `judgeId`, `displayName`, `slug`.
- `JudgeSearchResponse` — same pattern.
- All objects `additionalProperties: false`.

### 5. Public result contracts (`src/public/results.ts`)

- `ChargeOnlyResult` — includes: charge display name, geography label
  (string, e.g. "Philadelphia-wide"), outcome `Distribution`, optional
  sentencing `Distribution`, `taxonomyVersion`, `lastRefreshed`
  (ISO date-time string).
- `JudgeSpecificResult` — includes: charge display name, judge display
  name, judge-specific outcome `Distribution`, optional judge-specific
  sentencing `Distribution`, baseline outcome `Distribution`, optional
  baseline sentencing `Distribution`, `taxonomyVersion`, `lastRefreshed`.
- All objects `additionalProperties: false`.

### 6. Privacy boundary (hard rule)

The following fields must not exist anywhere in public schemas, under any
name: defendant names, docket numbers, source document IDs, storage keys or
paths, raw or extracted text, parser internals (confidence scores, review
flags, parser versions), and internal record IDs from raw/parsed/fact/
review/audit layers. If an acceptance criterion seems to require one of
these, stop and report.

### 7. Exports

- Package exports schemas (values) AND static types (via `Static<typeof X>`)
  from a clean index. Consumers should be able to
  `import { ChargeOnlyResult, chargeOnlyResultSchema } from '@pca/shared'`
  (exact naming convention: propose in the plan, keep it consistent).

### 8. Root generate script (build ordering)

- Add root script `"generate": "pnpm -r run generate"`.
- Update root `typecheck` and `test` scripts to run `pnpm run generate`
  first, so a fresh clone can run root scripts in any order and always
  typecheck against fresh taxonomy artifacts.
- `@pca/shared` itself needs no generate step; the recursive script simply
  finds `@pca/taxonomy`'s.

### 9. Tests (Vitest)

- Validation round-trip tests: valid sample payloads pass schema validation
  (use TypeBox's Value module or a JSON Schema validator — propose in plan).
- Rejection tests: unknown extra property on each top-level response schema
  is REJECTED (this is the additionalProperties test — one per top-level
  schema minimum).
- A test asserting category codes in the schema match the taxonomy generated
  artifact exactly (guards against drift if derivation is ever refactored).
- Percentage bounds and negative-count rejection tests.

## Out of Scope

- Modifying `apps/api` or `apps/web` in any way (they adopt this package in
  Sprint 2).
- Definitions / methodology / data-coverage response schemas (Sprint 2).
- Judge-specific-unavailable structured response (PUB-003.3, Sprint 2).
- Admin API contracts of any kind.
- Error response schema (already lives in `@pca/api` from task 1.3; it will
  be lifted into shared later, not now).
- Any database, Kysely, or Fastify code.
- Seeded data of any kind.

## Files the agent may touch

- `packages/shared/**` (new)
- Root `package.json` (scripts: add `generate`, modify `typecheck`, `test`)
- `tasks/worklog.md` (append entry on completion)
- `agent-docs/**` if documenting anything

Do NOT touch: `docs/` (human-only), `apps/**`, `db/**`,
`services/**`, `packages/taxonomy/**` (read its generated artifact, don't
modify it — if it lacks an export you need, STOP and report).

## Acceptance Criteria

1. `packages/shared` exists as `@pca/shared` with workspace dep on
   `@pca/taxonomy`.
2. Public search and result schemas exist as TypeBox schemas with derived
   static types, exported from the package index.
3. Result types require sample size, date range, thin-data status, taxonomy
   version, and counts + percentages together — enforced by schema, not
   convention.
4. Outcome and sentencing distributions each carry independent sample size,
   date range, and thin-data status.
5. Category codes are derived from `@pca/taxonomy` generated artifacts with
   zero hand-duplicated code lists; a test guards this.
6. Every public object schema sets `additionalProperties: false`, with
   rejection tests proving it.
7. No forbidden field (privacy boundary list) appears in any public schema.
8. Root `generate` script exists; root `typecheck` and `test` run generation
   first; fresh-clone ordering documented in the package or root README.
9. `pnpm lint`, `pnpm typecheck`, `pnpm test`, `pnpm format:check` all pass
   from the root.
10. Worklog entry appended.