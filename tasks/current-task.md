# Current Task: 1.1 — Initialize Monorepo

> Reminder: respond with an implementation plan first. Do not write code until the plan is approved. See CLAUDE.md.

## Goal

A runnable pnpm-workspace monorepo skeleton exists with the agreed folder structure, root scripts, README setup instructions, and a .gitignore that enforces the privacy rules. No application code yet.

## Context

This is the first implementation task (backlog FDN-001.1). It creates the structure every later task builds inside. Planning docs are in `docs/`; the folder layout follows the "Monorepo Structure" section of `docs/architecture.md`.

## Scope

- Initialize the repo as a pnpm workspace (pnpm-workspace.yaml at root).
- Create the folder structure with placeholder README.md files (one line each describing the folder's purpose):
  - `apps/web/`
  - `apps/api/`
  - `services/pipeline/`
  - `packages/shared/`
  - `packages/taxonomy/`
  - `packages/ui/`
  - `db/`
  - `infra/`
  - `scripts/`
  - `tests/`
  - (`docs/` and `tasks/` already exist — leave their contents alone)
- Root `package.json` with:
  - `"private": true`
  - workspace-aware root scripts: `dev`, `build`, `lint`, `typecheck`, `test` (use recursive pnpm invocations, e.g. `pnpm -r run build`; they may no-op today since no packages define these scripts yet)
  - `engines` field pinning Node >=22
- `.npmrc` with `engine-strict=true`
- Root `.gitignore` covering at minimum: `node_modules/`, build output dirs (`dist/`, `.next/`, `__pycache__/`, `.pytest_cache/`), `.env` and `.env.*` (but NOT `.env.example`), coverage output, OS junk (`.DS_Store`), and privacy-critical patterns: `*.pdf`, `fixtures/`, `extracted-text/`, and any `*.local.*` files.
- Root `README.md` with: project one-liner, prerequisites (Node 22 LTS, pnpm, Python 3.12, Docker Desktop), clone-and-install steps, workspace layout table, and a short "Privacy rules" section stating that fixture PDFs, extracted docket text, and secrets are never committed.

## Files in scope

- `pnpm-workspace.yaml`
- `package.json`
- `.npmrc`
- `.gitignore`
- `README.md`
- placeholder `README.md` inside each new folder listed above

Nothing else. Do not modify anything in `docs/` or `tasks/` except appending the worklog entry at the end.

## Acceptance criteria

- [ ] Repo contains `apps/web`, `apps/api`, `services/pipeline`, `packages/shared`, `packages/taxonomy`, `packages/ui`, `db`, `docs`, `infra`, `scripts`, `tests`
- [ ] `pnpm-workspace.yaml` exists and covers `apps/*`, `packages/*`, `services/*`
- [ ] Root scripts `dev`, `build`, `lint`, `typecheck`, `test` exist and `pnpm install` + each script runs without error (no-ops are fine)
- [ ] README includes local setup steps and the privacy rules section
- [ ] `.gitignore` blocks `.env` files, PDFs, and fixture/extracted-text directories
- [ ] No secrets or production data committed
- [ ] Worklog entry appended to `tasks/worklog.md`

## Out of scope

- Any TypeScript config (Task 1.2)
- Any Fastify/Next.js/Python code (Tasks 1.3, 4.1, 4.2)
- ESLint/Prettier setup (Task 1.2)
- Docker Compose (Task 2.1)
- CI workflow (Task 5.2)
- Turborepo — do not add it
- Installing any dependencies beyond pnpm workspace basics (root package.json should have zero or near-zero deps)

## Verification

Human runs:

```
pnpm install
pnpm lint && pnpm typecheck && pnpm test && pnpm build
git status
```

Expected: install succeeds, scripts exit 0 (even as no-ops), `git status` shows no ignored junk staged, folder tree matches the layout above.

## Notes / open questions

- If the agent believes a placeholder `package.json` is needed inside any workspace folder for the recursive scripts to exit cleanly, it should say so in the plan rather than silently adding them.

---

## Status

- Handed off: [date]
- Plan approved: pending
- Completed: pending