# @pca/taxonomy

Single source of truth for outcome categories, sentencing categories, and
thin-data configuration. Downstream packages (starting with `@pca/shared`)
consume the generated artifacts, never the seed files directly.

## Layout

| Path                               | Purpose                                       |
| ---------------------------------- | --------------------------------------------- |
| `seeds/outcome-categories.json`    | Outcome category records (source of truth)    |
| `seeds/sentencing-categories.json` | Sentencing category records (source of truth) |
| `seeds/thin-data.json`             | Thin-data policy config (provisional values)  |
| `seeds/version.json`               | Taxonomy version (semver)                     |
| `src/`                             | Validation and generation scripts             |
| `generated/`                       | Emitted artifacts — gitignored, never edit    |

Category `code` values are stable identifiers and must never be renamed.

## Commands

```bash
pnpm --filter @pca/taxonomy validate   # check seed invariants, non-zero exit on failure
pnpm --filter @pca/taxonomy generate   # validate, then emit generated/taxonomy.json + generated/index.ts
pnpm --filter @pca/taxonomy test       # vitest
```

Root shortcuts: `pnpm taxonomy:validate` and `pnpm taxonomy:generate`.

## Regenerating artifacts

Edit the seed files, then run `pnpm taxonomy:generate`. Generation is
deterministic (stable ordering, no timestamps), so repeated runs on the same
seeds produce byte-identical output. `generated/` is gitignored; anything
that needs the artifacts must run generate first (the package `typecheck`
script already does).
