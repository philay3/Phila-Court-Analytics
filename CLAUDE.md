# CLAUDE.md — Coding Agent Rules for Philadelphia Court Outcomes Analytics

You are the implementation agent for this project. Planning and task sequencing happen elsewhere; your job is to execute the task defined in `docs/current-task.md` — nothing more.

## The workflow (non-negotiable)

1. Read `docs/current-task.md`.
2. Respond with an IMPLEMENTATION PLAN first. Do not write or modify any code until the human explicitly approves the plan.
3. Your plan must include:
   - your understanding of the goal in one or two sentences
   - the files you will create or modify (exact paths)
   - the approach, including any libraries you'll add and why
   - how each acceptance criterion in the task will be satisfied
   - anything ambiguous or missing that you need answered
4. After approval, implement exactly the approved plan. If you discover mid-implementation that the plan needs to change, STOP and say so — do not silently deviate.
5. When done, report: what you built, how to run/verify it, and which acceptance criteria are met.

## Scope discipline

- Do ONLY what `docs/current-task.md` asks. Do not refactor, rename, "improve," or scaffold ahead, even if it seems helpful.
- Do not touch files outside the "Files in scope" list in the task, except trivially necessary ones (e.g., lockfile updates) — and call those out.
- If the task seems to require out-of-scope changes, stop and ask.
- Do not add dependencies beyond those the task or approved plan names.

## Privacy and safety rules (hard rules, never violate)

- NEVER commit: secrets, .env files with real values, API keys, raw docket PDFs, extracted docket text, defendant names, docket numbers, or any production court data.
- Fixture PDFs live OUTSIDE the repo. Code references them via a configurable, gitignored path. If you need fixtures to test, ask the human to run it locally.
- Never log raw docket text or defendant-identifying data to console, test output, or CI.
- Public API code must never expose raw, parsed, fact, review, audit, or source-document data — aggregate-only.

## Stack (locked — do not substitute)

- Monorepo: pnpm workspaces (no Turborepo yet)
- API: Fastify + TypeScript (strict mode), TypeBox for validation
- DB: PostgreSQL, Kysely + Kysely Migrator, explicit SQL where sensible
- Web: Next.js (App Router), React, TypeScript
- Pipeline: Python 3.12, pytest; extractor candidates PyMuPDF / pdfplumber / pypdf
- Node 22 LTS
- CI: GitHub Actions

## Conventions

- Strict TypeScript everywhere; no `any` without a comment justifying it.
- Migrations: explicit, ordered, documented naming convention (see db/README once it exists).
- Tests accompany the code they test within the same task when the task's acceptance criteria call for them.
- Keep commits scoped to the current task; reference the task ID in commit messages (e.g., "task 2.2: add Kysely migration runner").
- No prediction, odds, legal-advice, or judge-ranking language anywhere in user-facing copy.

## Reference docs

Planning docs live in `docs/`. Consult them for context, but `docs/current-task.md` defines what you build. If the docs and the task conflict, ask.