# CLAUDE.md — Philadelphia Court Outcomes Analytics

Public analytics on Philadelphia criminal court outcomes. A Python 3.12
pipeline parses docket PDFs into Postgres; a Fastify/TypeScript API serves
aggregate-only data to a Next.js frontend. pnpm workspaces monorepo, Node 22.
Real court data and operational artifacts live under `~/court-data/`, outside
the repo. Planning docs in `docs/planning/` are human-maintained — don't edit
them.

## Session start

Read `docs/board.md` first — it holds current state, priorities, and open
threads. Update it whenever things change: work lands, a decision gets made,
a new problem surfaces.

## Rules

1. **Nothing derived from real dockets ever enters the repo tree.** No docket
   text, docket numbers, or defendant-identifying data in code, fixtures,
   tests, comments, commit messages, or docs — hash-prefix IDs and CPCMS
   vocabulary only in committed artifacts and console output. You may freely
   read and run tools over `~/court-data/`, and may source
   `DEFENDANT_HASH_SALT` from the repo-root `.env`, but never echo, log, or
   write its value.

2. **Be careful with anything that re-parses the corpus or republishes
   results.** Show the diff first — what changes and by how much — and wait
   for a go-ahead before running it.

3. **Copy stays honest.** No prediction, odds, legal-advice, or judge-ranking
   language anywhere in user-facing copy.

4. **Tests pass before deploy.** Any fix that changes data comes with a
   before/after number.

## Git

Commit straight to main. Small, scoped commits with plain messages.
