# @pca/shared

Single source of truth for **public API contracts**. Public response shapes are defined
here as [TypeBox](https://github.com/sinclairzx81/typebox) schemas with derived static
types, so `@pca/api` gets runtime JSON Schema validation and `@pca/web` gets
compile-time types from one definition.

**Rule: public contracts live here and nowhere else.** If a public response shape is
needed, it is added to this package — never declared ad hoc in an app or service.

This package is pure schemas + types: no database, no Fastify, no runtime services.

## Layout

- `src/public/categories.ts` — category-code schemas derived from `@pca/taxonomy`
- `src/public/common.ts` — shared building blocks (distributions, sample size, date range, taxonomy version, thin-data status)
- `src/public/search.ts` — charge/judge search contracts
- `src/public/results.ts` — charge-only and judge-specific result contracts
- `src/index.ts` — the package's only public entry point

## Naming convention

Schemas are camelCase values with a `Schema` suffix; types are the PascalCase name
derived via `Static`:

```ts
import { chargeOnlyResultSchema, type ChargeOnlyResult } from '@pca/shared';
// ChargeOnlyResult === Static<typeof chargeOnlyResultSchema>
```

## Category codes

Outcome and sentencing category codes are derived from the `@pca/taxonomy` generated
artifact — a `Type.Union` of `Type.Literal`s built from the exported category lists.
Hand-maintained duplicate code lists are forbidden; a test guards against drift.

Only categories flagged `public: true` in the taxonomy are accepted by public schemas.
Internal buckets (e.g. `unknown`) fail schema validation by design, so they can never
leak into a public response — the same schema-as-privacy-wall posture as
`additionalProperties: false`, which every object schema in this package sets.

## Privacy boundary (hard rule)

The following must never appear in any public schema, under any name: defendant names,
docket numbers, source document IDs, storage keys or paths, raw or extracted text,
parser internals (confidence scores, review flags, parser versions), and internal
record IDs from raw/parsed/fact/review/audit layers.

## String formats

Schemas use JSON Schema `format: 'date'` and `format: 'date-time'`. TypeBox's `Value`
module only enforces formats the host application registers (`FormatRegistry`); Fastify
enforces them via Ajv. Tests in this package register minimal checkers in
`src/test-support/formats.ts`.

## Fresh clone / build ordering

This package imports `@pca/taxonomy`'s generated artifact, which is gitignored. Root
`typecheck` and `test` run `pnpm generate` first, so root scripts work in any order —
see the root [README](../../README.md#generated-artifacts). For package-scoped runs
(e.g. `pnpm --filter @pca/shared test`), run `pnpm generate` at the repo root first.
