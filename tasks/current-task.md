# Task 3.1 — Create Taxonomy Package

## Goal

Create `packages/taxonomy` (`@pca/taxonomy`): the single source of truth for
outcome categories, sentencing categories, and thin-data configuration. Seed
data lives in JSON, a validation script enforces invariants, and a generate
script emits TypeScript and JSON artifacts for downstream consumers.

## Context

- Monorepo, TS base tooling, ESLint/Prettier, and Vitest are already set up.
- TypeScript is installed at the root only; use the root binary.
- Package naming convention is `@pca/*`.
- This package has NO database dependency. Do not touch db/ or migrations.
- `packages/shared` (task 3.2, not this task) will later import the generated
  TypeScript artifact.

## Reminder: return an implementation plan BEFORE writing any code.

## Scope

### 1. Package scaffold

- `packages/taxonomy/` with `package.json` (`@pca/taxonomy`), tsconfig
  extending the root base config, and a README describing the package's role
  and how to regenerate artifacts.

### 2. Seed files (JSON, source of truth)

- `seeds/outcome-categories.json` with exactly these categories:
  dismissed, withdrawn, guilty_plea, guilty_verdict, acquittal, ard,
  diversion, other, unknown.
- `seeds/sentencing-categories.json` with exactly these categories:
  probation, incarceration, fine, restitution, community_service,
  no_further_penalty, costs_fees, other, unknown.
- Every category record has:
  - `code` — stable snake_case identifier (never to be renamed)
  - `displayName` — plain-English public label
  - `definition` — plain-English public definition, one or two sentences
  - `sortOrder` — integer, unique within its file
  - `public` — boolean; `unknown` is `false` in both files, all others `true`
- Definitions must be neutral and descriptive. No prediction, odds, legal
  advice, or ranking language.
- `seeds/thin-data.json`: structure for thin-data policy with PROVISIONAL
  values, e.g. `minSampleSize` for outcome and sentencing distributions
  plus a `provisional: true` flag and a comment field noting thresholds are
  finalized after parser/data review. Keep it minimal.
- `seeds/version.json`: `{ "taxonomyVersion": "1.0.0" }`.

### 3. Validation script (`pnpm --filter @pca/taxonomy validate`)

Validates all seed files and exits non-zero on any failure:

- required fields present and correctly typed
- codes are snake_case, unique within each file
- sortOrder unique within each file
- displayName and definition non-empty
- exactly the expected category code sets (guards accidental deletion)
- definitions contain none of these banned terms (case-insensitive):
  "predict", "odds", "likely", "win rate", "best judge", "worst judge",
  "score", "guarantee"
- taxonomyVersion is valid semver

### 4. Generate script (`pnpm --filter @pca/taxonomy generate`)

- Emits `generated/taxonomy.json` (all categories + thin-data config +
  taxonomyVersion in one document) and `generated/index.ts` (typed constant
  exports, including a `TaxonomyCategory` type and the version string).
- `generated/` is gitignored; generation is deterministic (stable ordering)
  so repeated runs produce identical output.
- Package main/exports point at the generated TS entry.

### 5. Tests (Vitest)

- validation passes on the real seeds
- validation fails on: duplicate code, missing field, banned term,
  unexpected/missing category code
- generate output includes all categories and the version

### 6. Root wiring

- Root scripts: `taxonomy:validate` and `taxonomy:generate` (or fold into
  existing lint/test conventions — state choice in the plan).
- Root README: one short section on the taxonomy package.

## Out of Scope

- Seeding the database (`ref.*` tables) — later task
- packages/shared / API / web integration — task 3.2+
- Finalizing thin-data threshold values
- Charge or judge normalization data
- CI changes (task 5.2 will wire taxonomy validation into CI)
- Turborepo, publishing, changesets

## Files the agent may touch

- `packages/taxonomy/**` (new)
- root `package.json` (scripts only)
- root `README.md` (one section)
- `.gitignore` (only if needed for `generated/`)
- `tasks/worklog.md` (append entry when done)

## Acceptance Criteria

1. `packages/taxonomy` exists as `@pca/taxonomy`, extending root tsconfig.
2. Outcome, sentencing, thin-data, and version seed files exist with the
   exact category sets and fields listed above.
3. `unknown` is `public: false` in both category files; all others `true`.
4. Validation script exists, passes on current seeds, and fails correctly
   on invalid input (covered by tests).
5. Generate script emits deterministic TypeScript and JSON artifacts
   containing all categories, thin-data config, and taxonomyVersion.
6. Vitest tests pass; lint and typecheck pass across the repo.
7. No secrets, PDFs, extracted text, or defendant-identifying data committed.