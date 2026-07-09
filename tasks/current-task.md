# Task 11.1 — Workspace Package Build + Runtime Fix

## Goal

Make the workspace packages (`@pca/shared`, `@pca/taxonomy`, `@pca/db`)
consumable by plain Node.js at runtime and by Next.js `app/` code at build
time. Concretely: `pnpm --filter @pca/api start` must serve requests under
plain node against built output, and `apps/web` must be able to import
`@pca/shared` in `app/` code and pass `next build`.

## Context

Recon (pre-sprint, read-only) confirmed the root cause: all three workspace
packages ship raw TypeScript source whose `.js`-extension internal imports
resolve only under tooling (tsx, tsc, bundlers). Plain node dies on the
first re-export. This broke the `start` script silently through all of
Sprint 2 (dev flows use tsx watch, so nothing noticed) and blocks Sprint 3
frontend work, which needs `@pca/shared` imports in `app/` code.

This task fixes the packaging/runtime story. It is the gate for Phase 11:
tasks 11.2 (API client) and 11.3 (Tailwind foundation) both depend on it,
and the Sprint 3 E2E CI job (15.2) will boot the API via the fixed `start`
path on every run.

## Standing decisions that bind this task

- `transpilePackages`-only is REJECTED as the mechanism. It would paper
  over the web import while leaving `start` broken, and Sprint 9 production
  requires a plain-node or bundled runtime regardless. Do not propose it.
- The expected mechanism shape is per-package `dist` builds + `exports`
  maps, but you propose the actual mechanism in your implementation plan
  for review. If you believe a different mechanism is superior, argue it
  in the plan — do not implement it unilaterally.
- TypeScript is installed at root only; workspaces use the root binary.
- `registerFormats()` from `@pca/shared` must remain `buildApp`'s first
  statement; nothing about the build change may alter that behavior.
- No behavior change to any package's public API surface.

## Required plan coverage

Your implementation plan (submitted BEFORE writing any code) must cover,
explicitly and per-package:

1. `@pca/shared` — build output, exports map, how tests/consumers resolve it
2. `@pca/taxonomy` — the generated-artifacts interplay: how `generated/`
   (gitignored, produced by `pnpm generate`) composes with the package
   build; fresh-clone ordering
3. `@pca/db` — build output plus any Kysely type-generation interplay
4. Root script ordering: how a fresh clone guarantees `generate` and any
   new package builds run before typecheck/test/build of consumers
5. CI changes: which jobs gain build steps, in what order
6. What happens to `dev` workflows (tsx watch for the API, `next dev` for
   web) — these must be UNCHANGED
7. How `apps/web` importing `@pca/shared` in `app/` code is proven: in
   this task via a trivial page, or explicitly deferred to 11.2's client
   module — state which
8. Watch-out inventory: declaration maps, `.js`-extension import handling
   in emitted output, Vitest resolution of built vs source, and any
   `pnpm` `allowBuilds` implications

## Scope

- Build configuration for the three packages (tsconfigs, package.json
  `exports`/`main`/`types`, build scripts)
- Root orchestration scripts and any ordering guarantees
- CI workflow updates for new build steps
- A minimal proof that `next build` succeeds with a `@pca/shared` import
  from `app/` code (if proven here rather than 11.2)
- Removal of any now-dead resolution workarounds made obsolete by the fix

## Acceptance criteria

1. `pnpm --filter @pca/api build` followed by `pnpm --filter @pca/api start`
   serves requests under plain node — the recon repro is dead. Include the
   verification transcript in your report.
2. A trivial `app/` page (or the 11.2 client, stated explicitly in the
   plan) importing `@pca/shared` passes `next build`.
3. Fresh-clone ordering works: from a clean checkout, root scripts
   guarantee `generate` and package builds run before typecheck/test/build
   of consumers. Verify by simulating (e.g., wiping `dist/` and
   `generated/`) and running the root pipeline.
4. `dev` workflows (tsx watch, next dev) are unchanged and verified working.
5. CI is updated for any new build steps; all gates green (lint, format,
   typecheck, tests, taxonomy validation, forbidden-field suite, copy
   safety suite, pytest).
6. No behavior change to any package's public API surface; all existing
   test suites pass without modification to test assertions (test *setup*
   may change if resolution requires it — call it out if so).
7. Worklog entry appended: mechanism chosen, deviations, findings, and any
   forward-looking notes for 11.2/11.3.

## Out of scope

- Any frontend feature work (11.2+)
- Tailwind installation (11.3)
- `transpilePackages` as the mechanism (rejected; see standing decisions)
- Turborepo or any build-orchestration tooling adoption
- Changes to package public APIs, error shapes, or endpoint behavior
- Touching `services/pipeline` (Python is unaffected)
- Bundling the API app itself (plain tsc build + node is sufficient)

## Files you may touch

- `packages/shared/**`, `packages/taxonomy/**`, `packages/db/**`
  (build config, package.json, tsconfig — not source logic except import
  specifiers if the mechanism requires it)
- `apps/api/package.json`, `apps/api/tsconfig.json` (build/start scripts,
  resolution config)
- `apps/web/next.config.ts`, one trivial proof page under `apps/web/app/`
  if proving the import here
- Root `package.json` scripts, root tsconfig if needed
- `.github/workflows/**` (CI build steps)
- `tasks/worklog.md`

## Process

Submit your implementation plan first and stop. Do not write code until
the plan is approved.