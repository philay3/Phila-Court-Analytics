# Current Task: 1.2 — TypeScript Base Tooling

> Reminder: respond with an implementation plan first. Do not write code until the plan is approved. See CLAUDE.md.

## Goal

Shared TypeScript, lint, and format configuration exists at the repo root, with strict mode enabled, root scripts wired up, and a documented pattern for workspaces to extend — without scaffolding any app or package code.

## Context

Backlog item FDN-001.2. Task 1.1 created the pnpm-workspace skeleton with placeholder folders only; no workspace has a package.json yet. This task creates the base configs that every later workspace (API, web, shared, taxonomy) will extend. The extension itself happens in those later tasks — here we only prove the tooling runs cleanly at the root.

## Standing decisions that apply

- TypeScript strict mode (locked per sprint-1-plan.md)
- Node 22 LTS
- Lint/format: ESLint 9 flat config + typescript-eslint + Prettier (new decision, this task)
- Plain pnpm workspaces; no Turborepo

## Scope

1. **`tsconfig.base.json`** at repo root:
   - `strict: true` plus the usual hardening flags: `noUncheckedIndexedAccess`, `noImplicitOverride`, `forceConsistentCasingInFileNames`, `esModuleInterop`, `skipLibCheck`, `isolatedModules`
   - `target` / `lib` appropriate for Node 22 (ES2023)
   - `module`/`moduleResolution` suitable for a modern ESM monorepo (agent should state its choice and reasoning in the plan — e.g. `NodeNext` — knowing Next.js will use its own bundler settings later)
   - No `paths` aliases yet (deferred until shared packages exist)
2. **ESLint** flat config (`eslint.config.js` or `.mjs`) at root:
   - typescript-eslint recommended rules
   - Prettier compatibility (eslint-config-prettier)
   - ignores: `node_modules`, build output dirs, `docs/`, `tasks/`
3. **Prettier**: `.prettierrc` (agent proposes sensible defaults in plan) + `.prettierignore`
4. **Root package.json updates**:
   - devDependencies: typescript, eslint, typescript-eslint, prettier, eslint-config-prettier
   - scripts: `lint` (eslint .), `format` (prettier --write), `format:check` (prettier --check), `typecheck` (should exit cleanly today even with no TS source files — agent to state how, e.g. a root tsconfig.json that extends the base with an empty/placeholder include)
5. **Docs**: short section in root README (or `docs/tooling.md`) explaining how a new workspace extends `tsconfig.base.json` and inherits lint/format — the pattern tasks 1.3+ will follow.
6. **Verification** the agent must run and report:
   - `pnpm lint` exits 0
   - `pnpm format:check` exits 0
   - `pnpm typecheck` exits 0

## Acceptance criteria

- [ ] `tsconfig.base.json` exists with strict mode and the flags above
- [ ] ESLint 9 flat config exists and runs cleanly at root
- [ ] Prettier config + ignore file exist; format check passes
- [ ] Root scripts `lint`, `format`, `format:check`, `typecheck` all exit 0
- [ ] Extension pattern documented for future workspaces
- [ ] All new dependencies are devDependencies at the root
- [ ] `pnpm-lock.yaml` updated and committed
- [ ] No app/package code, no workspace package.jsons, no CI changes
- [ ] Worklog entry appended to `tasks/worklog.md`

## Out of scope

- Any workspace-level package.json or tsconfig (that's 1.3 onward)
- Fastify, Next.js, or any application dependencies
- CI workflow (Phase 5.2)
- Path aliases / project references (revisit when packages/shared exists)
- lint-staged / husky / git hooks (decide later if wanted; do not add now)
- Editor config beyond a simple `.editorconfig` (optional; agent may propose one line-item in plan)

## Files in scope

- `tsconfig.base.json` (new)
- `tsconfig.json` (new, root, only if needed for typecheck to run)
- `eslint.config.js` / `.mjs` (new)
- `.prettierrc`, `.prettierignore` (new)
- `.editorconfig` (optional, new)
- `package.json`, `pnpm-lock.yaml` (root, modified)
- `README.md` or `docs/tooling.md` (modified/new, docs only)

Nothing else.

## Notes / open questions for the agent's plan

- State the chosen `module`/`moduleResolution` and why.
- State how `typecheck` exits cleanly with no source files yet.
- If any ESLint rule set choice is opinionated (e.g. stylistic rules), flag it rather than silently adding.

---

## Status

- Handed off: [date]
- Plan approved: pending
- Completed: pending