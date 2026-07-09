# Task 11.3 — Tailwind v4 Styling Foundation

## Goal

Install and configure Tailwind CSS v4 for `apps/web`, migrate the 4.1 design
tokens into Tailwind's CSS-first `@theme` configuration, and restyle the
existing layout shell (header/nav/main/footer) with a calm civic visual tone.
This is the styling foundation every Phase 12–14 page builds on.

## Context

- Sprint 3 standing decision: **Tailwind v4, CSS-first config.** The 4.1
  design tokens (currently in `globals.css`) migrate into `@theme`.
  Semantic-HTML discipline from 4.1 is preserved — Tailwind styles the
  existing structure; it does not replace it with class-soup divs.
- **No component UI library** (no shadcn, no Radix themes, no DaisyUI). Plain
  Tailwind utilities on semantic HTML.
- Next.js 16 App Router with Turbopack; React 19. Tailwind v4 integrates via
  `@tailwindcss/postcss` — the plan must state the exact integration
  mechanism and confirm it works under both `next dev` (Turbopack) and
  `next build`.
- **pnpm allowBuilds discipline**: Tailwind v4 depends on the native binary
  package `@tailwindcss/oxide`, which pnpm will refuse to build without
  explicit approval. The implementation plan MUST name every allowBuilds /
  `onlyBuiltDependencies` entry it intends to add, with a one-line reason
  each. `sharp` remains false/absent.
- Carried 11.1 constraint: `pnpm run build:packages` must run before web
  development touching `@pca/*` imports. `next dev`/`next build` resolve
  dist, not source.
- Visual language (front-end-spec): calm civic tone, restrained palette,
  clear typography, card-friendly foundations. Avoid dramatic colors,
  red/green moral judgment colors, ranking visuals, or anything predictive-
  feeling. This is a neutral civic data tool.

## Scope

1. **Install Tailwind v4** in `apps/web` with the PostCSS integration;
   handle allowBuilds entries deliberately (named in plan, approved before
   implementation).
2. **Token migration**: move the 4.1 design tokens from `globals.css` custom
   properties into `@theme` (colors, spacing/typography tokens as they
   exist). `globals.css` is reduced to: the Tailwind import, `@theme` tokens,
   and a minimal base-element layer (body defaults, focus-visible styles,
   any element resets 4.1 established). No page-specific styles remain
   there.
3. **Shell restyle**: apply Tailwind utilities to the existing layout shell —
   header, nav, main content container, footer. Calm civic palette,
   restrained accent color, readable max-width content column, clear visible
   focus states on all interactive elements (focus must not regress —
   keyboard focus visibility is an accessibility requirement, not polish).
4. **Verify both dev and prod paths**: `next dev` renders styled pages;
   `next build` succeeds; existing web tests (copy guard + any others) stay
   green.

## Out of Scope

- Any new pages, routes, or components (Phase 12–14 work)
- Result-page, chart/bar, or distribution styling (13.1)
- Homepage search layout (12.1) — the shell only, not the search surface
- Component UI libraries of any kind
- Dark mode
- Animation/motion libraries
- Any public copy changes — if a copy change seems necessary, STOP and ask;
  do not edit copy in this task
- Image processing / `sharp` (stays false)
- CI E2E work (15.2)

## Files the agent may touch

- `apps/web/package.json`
- `apps/web/postcss.config.*` (new)
- `apps/web/app/globals.css`
- `apps/web/app/layout.tsx` and existing shell components under `app/`
- Root `package.json` / `pnpm-workspace.yaml` ONLY for the approved
  allowBuilds entries
- CI workflow ONLY if a new build step is genuinely required (state why in
  the plan; none is expected)

## Acceptance Criteria

1. Tailwind v4 is installed and working: `next dev` (Turbopack) serves
   styled pages and `next build` completes cleanly.
2. All allowBuilds / `onlyBuiltDependencies` additions were named in the
   approved plan; no unapproved entries appear; `sharp` remains
   false/absent.
3. The 4.1 design tokens live in `@theme`; `globals.css` contains only the
   Tailwind import, `@theme` tokens, and minimal base element styles. No
   dead/duplicated token definitions remain.
4. The layout shell (header/nav/main/footer) is restyled: restrained civic
   palette, readable content column, clear typography hierarchy.
5. Visible focus states exist on every interactive shell element
   (keyboard-tab walkthrough confirms; `:focus-visible` styling present).
6. Semantic HTML is unchanged: no structural elements replaced with styled
   divs; heading/nav/landmark structure identical before and after.
7. No public copy was added, removed, or edited; the copy-guard test passes
   unchanged.
8. All gates green: typecheck, lint, format:check, all workspace tests,
   `next build`.
9. Worklog entry appended: what was installed, the token mapping decisions,
   any Tailwind v4 / Turbopack quirks discovered (these matter for Phase
   12–14 tasks).

## Process

Submit an implementation plan BEFORE writing code. The plan must include:

1. Exact Tailwind v4 integration mechanism (packages, PostCSS config shape)
   and confirmation of the Turbopack path.
2. Every allowBuilds entry to be added, with reasons.
3. The token mapping: each existing 4.1 token → its `@theme` destination
   (a short table is fine).
4. Which shell files will be edited and the intended visual direction in a
   few sentences.
5. Confirmation that `build:packages` ordering is respected and no copy
   will change.