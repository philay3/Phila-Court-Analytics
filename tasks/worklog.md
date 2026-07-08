# Worklog

## Task 1.1 — Initialize Monorepo (FDN-001.1)

- **Date:** 2026-07-07
- **What was built:** pnpm-workspace monorepo skeleton: `pnpm-workspace.yaml` (covers `apps/*`, `packages/*`, `services/*`), root `package.json` (`private: true`, `packageManager: pnpm@11.10.0`, `engines.node >=22`, recursive `dev`/`build`/`lint`/`typecheck`/`test` scripts), `.npmrc` with `engine-strict=true`, privacy-enforcing `.gitignore`, root `README.md` (setup, layout table, privacy rules), placeholder READMEs in all ten workspace folders. Zero dependencies.
- **Files touched:** `pnpm-workspace.yaml`, `package.json`, `.npmrc`, `.gitignore`, `README.md`, `pnpm-lock.yaml` (generated), `apps/web/README.md`, `apps/api/README.md`, `services/pipeline/README.md`, `packages/shared/README.md`, `packages/taxonomy/README.md`, `packages/ui/README.md`, `db/README.md`, `infra/README.md`, `scripts/README.md`, `tests/README.md`
- **Deviations from plan:** none.
- **Notes for next task:** No placeholder `package.json` files exist in workspace folders — `pnpm -r run <script>` exits 0 with no packages, so none were needed. Task 1.2 (TypeScript/ESLint config) will add the first real package manifests. `.gitignore` uses `!.env.example` negation; keep that if patterns are edited. CLAUDE.md references `docs/current-task.md` but the task file actually lives at `tasks/current-task.md`.
