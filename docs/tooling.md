# Tooling: TypeScript, ESLint, Prettier

Base configuration lives at the repo root. Workspaces extend it; they do not define their own
lint or format setup.

## TypeScript

`tsconfig.base.json` holds the shared compiler options: strict mode, the hardening flags
(`noUncheckedIndexedAccess`, `noImplicitOverride`, `forceConsistentCasingInFileNames`,
`esModuleInterop`, `skipLibCheck`, `isolatedModules`), `target`/`lib` ES2023 for Node 22, and
`module`/`moduleResolution` `NodeNext`.

A new workspace adds its own `tsconfig.json` that extends the base and sets only what is local
to it:

```jsonc
// e.g. services/api/tsconfig.json
{
  "extends": "../../tsconfig.base.json",
  "compilerOptions": {
    "outDir": "dist",
    "rootDir": "src",
  },
  "include": ["src"],
}
```

Each workspace should expose a `typecheck` script (`tsc -p tsconfig.json --noEmit`) in its
`package.json`.

Notes:

- The Next.js app will override `module`/`moduleResolution` (Next manages its own bundler
  settings); everything else still comes from the base.
- No `paths` aliases or project references yet — revisit when `packages/shared` exists.
- The root `tsconfig.json` exists only so `pnpm typecheck` has an input before any workspace
  code exists (it type-parses `eslint.config.mjs`). Do not add application code to it.

## ESLint

One flat config at the root (`eslint.config.mjs`) lints the entire repo:
`@eslint/js` recommended + `typescript-eslint` recommended (non-type-checked), with
`eslint-config-prettier` last to disable formatting rules. Workspaces need no ESLint config of
their own — `pnpm lint` at the root covers them. Type-aware linting can be enabled once
workspace tsconfigs exist.

## Prettier

`.prettierrc` at the root (single quotes, print width 100, otherwise Prettier defaults) applies
everywhere; `.prettierignore` excludes build output, the lockfile, and planning prose
(`docs/planning/`, `tasks/`, `CLAUDE.md`). Workspaces add nothing.

## Root scripts

| Script              | What it does                                                   |
| ------------------- | -------------------------------------------------------------- |
| `pnpm lint`         | `eslint .` over the whole repo                                 |
| `pnpm format`       | `prettier --write .`                                           |
| `pnpm format:check` | `prettier --check .`                                           |
| `pnpm typecheck`    | `tsc -p tsconfig.json` (root config; workspaces get their own) |
