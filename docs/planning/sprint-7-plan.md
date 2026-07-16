# Sprint 7 Plan: Real-Data Hardening + Launch Package

**Fuses the draft Sprints 7 and 8 into one launch sprint.** The draft
plans were written without visibility into what Sprints 3 and 6 already
shipped; this plan supersedes them where they conflict.

## Sprint 7 Goal

Take the live real-data product from "the publish swap worked" to
"shipped": no fake or seeded residue anywhere a user can reach, the one
known data-quality defect fixed and republished, the UI verified against
real distributions (not just seeds), the queued contract items closed,
honest date disclosures in place, a documented demo path, a submission
package, and the product deployed online under the controlled-launch
model.

By the end of Sprint 7:

- no fake judge, fake alias, or seeded aggregate row is reachable from
  any public surface; the live database holds real data only
- the "Held for Court" outcome-fact defect is fixed with full pipeline
  discipline and a fresh aggregate run is published
- every public page has been walked against real data and defects found
  are fixed — real category tails, real charge-name lengths,
  thin-everywhere judge pages, mobile, accessibility
- the queued contract items are closed: test-database guard,
  `CHARGE_RESULT_UNAVAILABLE_MESSAGE` migration, duration-display
  resolution
- date-range disclosures reflect the shipping model: honest coverage
  labels, no implied completeness
- a demo script with real slugs exists and a full submission package
  (README, setup, limitations, future work) is done
- the product is deployed and reachable online, noindex, with the
  launch-blocking configuration items resolved
- the sprint closes with an exit demo run against the deployed product

Sprint 7 does **not** build admin review (ADR 0003 stands), does not
enable indexing, and does not add data machinery beyond the one
sanctioned fix in 29.3.

---

## Current State (what this sprint builds on)

Sprint 6 closed 2026-07-13 (PR #47). The public app serves published
aggregate run **286b0058** — real Philadelphia data end-to-end with zero
API/UI code change: charge search, charge-only results,
judge-specific-where-available results, all unavailable arms, and
coverage/methodology reading the real run. Corpus at close: 6,640
dockets (2,931 CP + 3,709 MC); fact build run 8ded6328. Judge-specific
coverage is almost entirely thin at launch (a finding, not a failure —
coverage copy already carries it honestly). Methodology and
data-coverage copy were refreshed in 28.2 (SD-15 disclosure,
judge-thinness honesty, structural-exclusion framing, seeded-data
disclosure retired, admin review documented as future work per
ADR 0003).

Collection continues in parallel. The aggregator is re-runnable: any
intake landed during this sprint can ride the 29.3 republish without
code change.

**Numbers discipline (carried from 28.2, applies sprint-wide):** no
figure is pinned in code, tests, or copy. Every count is a snapshot of
the run being published. Counts quoted in this plan describe the state
at planning time and are never acceptance values.

---

## Locked Sprint 7 Scope

### In Scope

- Seed sweep: fake judges, fake judge aliases, and seeded aggregate
  rows/run removed from the live database; demo charges retained as
  promoted roster members (22.2 standing decision)
- Test-database guard: vitest global-setup asserts a test-dbname
  pattern before touching `aggregate_runs` (queued at 28.2 close)
- "Held for Court" MC outcome-fact fix: full pipeline discipline,
  fact rebuild, fresh aggregate run generated/validated/published
- Systematic real-data verification walkthrough of every public page
  (desktop + mobile + keyboard/a11y spot checks) with defect fixes
- `CHARGE_RESULT_UNAVAILABLE_MESSAGE` migration to `@pca/shared`
  (queued since Sprint 3)
- Duration-display resolution: close the queued question against what
  actually reaches public surfaces
- Launch copy + date-disclosure pass (framing review; most mechanical
  work landed in 28.2)
- Demo script with real slugs + demo data guardrails
- Submission package: README, setup instructions, known limitations,
  future work
- Deployment decisions + go-live under the controlled-launch model,
  including the launch-blocking configuration items (API base-URL
  default guard, production secrets handling, noindex verification,
  rate-limiting decision)
- Exit demo against the deployed product

### Out of Scope

- admin review UI, admin auth, correction workflow, audit dashboard
  (ADR 0003 — post-launch future work)
- **DB taxonomy tables** (`ref.outcome_categories` /
  `ref.sentencing_categories`) — DEFERRED with a named landing:
  post-launch, triggered by the first taxonomy version bump or the
  arrival of a second taxonomy writer. Rationale: nothing consumes
  them today — taxonomy serves from `@pca/taxonomy` artifacts,
  category codes are compile-time-checked imports, aggregates store
  `taxonomy_version` as a string, and validate-aggregates checks codes
  against the package before publish. FK integrity earns its cost only
  when versions multiply or writers do.
- SEO / indexing enablement — noindex stays (controlled launch)
- product analytics
- OCR, automated broad ingestion changes, external services
- raw-PDF retention decision (raw PDFs live under `~/court-data/`
  locally and are not part of the deployment; the decision stays
  deferred)
- chart libraries or visual redesign (table + bar contract unchanged)
- numeric confidence anything (rejected since Sprint 4; still rejected)
- parser or normalization module changes beyond the one sanctioned
  29.3 fix — any other surfacing defect is stop-and-report
- `db:reset` / volume wipes — PROHIBITED (real corpus on the volume)

---

## Sprint 7 Standing Decisions

These extend the Sprint 1–6 decisions and are locked:

1. **Sweep deletes live rows; seed scripts stay for test environments.**
   The sweep removes fake judges, their aliases, and the invalidated
   seeded aggregate run + its rows from the live `pca` database. The
   TypeScript seed scripts in `db/seeds/` are NOT deleted — CI (vitest
   global-setup, the E2E job) builds fresh databases from them and the
   E2E suite's flows depend on deterministic seeded data. The agent's
   plan must prove the sweep and CI seeding cannot collide (the sweep
   targets the live DB by explicit intent; CI targets fresh databases).
2. **The rollback target is surrendered deliberately.** Deleting the
   seeded run removes the invalidated-rollback option Sprint 6
   preserved. This is accepted: the real run is proven live, and after
   29.3 a second real run exists — real runs are now each other's
   rollback targets under the existing published-run model. Rolling
   back to fabricated data was never a real option for a launched
   product anyway.
3. **Re-seeding the live database must be impossible to do by
   accident.** The 28.2 incident class (test tooling re-activating the
   seeded run against the real DB) is closed structurally: the
   test-database guard (29.2) asserts a test-dbname pattern before any
   test-path write to `aggregate_runs`, and the agent's 29.1 plan must
   state what happens if `db:seed` is pointed at the live DB post-sweep
   (guard, refuse, or documented-safe — proposed in the plan, decided
   in planning chat).
4. **The 29.3 fix is the sprint's only sanctioned data-machinery
   change.** It follows full pipeline discipline: mechanism proposed
   from recon and approved in planning chat before code; corpus-level
   verification proving the diff set is exactly the intended class;
   fact rebuild; reconciliation gates; generate → validate → publish
   through the existing commands. Any unexplained diff is
   stop-and-report. Any OTHER data defect surfacing during the sprint
   is stop-and-report, adjudicated in planning chat — never fixed
   ride-along.
5. **Republish uses existing machinery only.** A new aggregate run
   invalidating the prior real run in one transaction — the Sprint 6
   publish path, including the StaleValidatedRunError guard. No new
   publish code.
6. **Real-data defects found in 30.1 are triaged, not auto-fixed.**
   UI/copy/formatting defects fix in-task; anything touching data,
   eligibility, or aggregates routes to stop-and-report per decision 4.
7. **Launch model: controlled.** Deployed, reachable, noindex,
   honest date-range disclosures. Indexing, analytics, and outreach
   are post-launch decisions. "Online" does not mean "promoted."
8. **Deployment decisions are made in planning chat, not in an agent
   plan.** Hosting targets, domain, database hosting, secrets handling,
   and the rate-limiting decision are human decisions (31.3 opens with
   a decision gate). The agent implements what's decided.
9. **Phase numbering continues from Sprint 6: Phases 29–31.**

---

## MVP Data Range (restated)

Coverage starts **2025-01-01**, inherited through fact eligibility.
The public product carries honest date-range disclosures: every result
shows its date range from run metadata, data-coverage states the
window, and no copy implies completeness beyond what the published run
contains. Ongoing collection widens subsequent runs without code
change.

---

## Recon required before implementation (Claude has no repo access)

The agent's plans must confirm from actual code — any mismatch with
this plan is stop-and-report:

1. **29.1:** How seeded rows are identified (the `db/seeds/` slug
   registry per the Sprint 2/22.2 decisions); whether any FK from real
   data references a seeded row (expected: none — facts FK to roster
   charges, and demo charges are retained); what `db:seed` does when
   run against a post-sweep live DB; how the CI E2E job and vitest
   global-setup source their databases.
2. **29.2:** Where vitest global-setup touches `aggregate_runs` and
   what DB-name information is available at that point.
3. **29.3:** Where "Held for Court" values actually enter outcome
   facts — which parsed field carries them, what the disposition map
   currently does with them, how many facts are affected and at what
   eligibility level, and whether the right fix point is the map, the
   fact builder, or both. The mechanism is proposed from this recon
   and approved in planning chat before any code.
4. **30.2:** Whether any duration data (min/max days, `min_assumed`)
   reaches `analytics.*` rows or any public API payload at all. The
   queued duration-display question resolves against this fact.
5. **31.3:** Current `API_BASE_URL` default handling (the §5
   localhost-default item), what env vars each deployable needs, and
   what the production build path requires that CI doesn't already
   prove.

---

# Phase 29 — Residue + Data Quality

## Task 29.1 — Seed Sweep

Remove all fake/seeded rows from the live database. Fake judges are
currently visible in the live public judge autocomplete — this is the
launch-blocking defect of the phase.

Acceptance criteria:

1. Sweep tooling identifies seeded rows via the `db/seeds/` slug/code
   registry (the established upsert-key mechanism) — never by name
   pattern or guesswork.
2. Fake judges and their aliases are deleted from `ref.*` in the live
   DB; demo charges and their aliases are retained per the 22.2
   standing decision (promoted roster members; real facts may FK to
   them).
3. The invalidated seeded aggregate run and all its aggregate rows are
   deleted (standing decision 2: rollback target surrendered
   deliberately, stated in the worklog).
4. Post-sweep verification (agent-run, raw output verbatim): public
   judge search returns zero seeded judges for the known fake-name
   queries; charge search still returns the retained demo charges;
   the active published run is untouched; all four public result
   endpoint types still serve correctly.
5. The `db:seed`-against-live-DB question is resolved per the approved
   plan (standing decision 3) and the resolution is documented.
6. CI is proven unaffected: E2E and API suites still green (they build
   from seeds in fresh databases; the sweep never runs in CI).
7. Sweep is idempotent — re-running against a swept DB is a no-op
   reported as such.
8. Console hygiene: counts and slugs only (seeded slugs are fake and
   safe; no real-data content is implicated).
9. All repo gates green.

## Task 29.2 — Test-Database Guard

Closes the 28.2 incident class (queued at sprint-6 close): API test
runs pointed at the real DB would re-seed and re-activate a seeded run
via vitest global-setup.

Acceptance criteria:

1. Vitest global-setup asserts a test-dbname pattern (the established
   `PIPELINE_TEST_DATABASE_URL` dbname-pattern convention is the
   reference model) before any operation that writes `aggregate_runs`
   or seed data; a non-matching database name fails loudly with a
   clear message before any write.
2. The guard covers every test entry path that touches the database —
   the agent's recon enumerates them (API suite global-setup, E2E job
   setup, any others found).
3. A deliberate-failure test proves the guard actually blocks (a
   non-test dbname is rejected), not merely exists.
4. CI unaffected and green; local test workflows documented if any
   env-var expectations change.
5. All repo gates green.

## Task 29.3 — "Held for Court" Fix + Fact Rebuild + Republish

The banked data-quality defect: non-terminal MC bind-overs are
producing outcome facts in public categories, polluting live
distributions with rows that aren't outcomes.

Acceptance criteria:

1. Recon report first (recon item 3): where the values enter, current
   map behavior, affected-fact counts by eligibility level, proposed
   fix point. Mechanism approved in planning chat before code.
2. The fix lands with full delta discipline: corpus-level verification
   proving the diff set is exactly the intended class (held-for-court
   rows stop producing outcome facts / stop reaching public
   categories, per the approved mechanism); every diff attributable;
   unattributable diffs are stop-and-report.
3. Tier-1 synthetic coverage: an MC held-for-court fixture proves the
   new behavior; goldens updated with the explicit flag + worklog
   note.
4. Fact rebuild executes on the current corpus (including any intake
   landed by this task) under a new `fact_build_runs` run;
   reconciliation gates pass; anomalies adjudicated in planning chat.
5. A new aggregate run is generated, validated, and published through
   the existing commands; the prior real run is invalidated in the
   same transaction; post-publish verification (raw output verbatim)
   shows the public endpoints serving the new run and the
   held-for-court pollution gone from affected distributions.
6. If intake grew the corpus, counts are formally restated (worklog +
   planning chat) per the SD-14 protocol.
7. Data-coverage metadata reflects the new run (no hardcoded counts
   anywhere — existing dynamic behavior verified, not rebuilt).
8. All repo gates green.

---

# Phase 30 — Real-Data UI Hardening + Queued Closures

## Task 30.1 — Real-Data Verification Walkthrough + Defect Fixes

Every UI state was built and tested against seeded data; real data is
shaped differently (more categories per distribution, longer charge
names, thin-everywhere judge pages, real category tails, larger search
result sets). This task is the systematic pass bglad's draft calls
"hardening," done once, against the deployed-candidate build.

Acceptance criteria:

1. A documented walkthrough matrix executed against the live run:
   homepage search (charge + judge autocompletes with real rosters);
   high-sample charge pages; thin-data charge pages; the
   sentencing-unavailable charge class; solid judge pair; thin judge
   pairs; judge-unavailable pairs; all three content pages; the about
   page. Each cell checked on desktop and mobile viewports.
2. Distribution rendering verified against real shapes: full category
   tails render correctly in tables and bars; counts + percentages +
   sample sizes present on every figure; date ranges present on every
   result; long charge/judge display names don't break layout.
3. Keyboard and screen-reader spot checks on the walkthrough pages
   (full WCAG re-audit not required — the E2E axe-core suite stands;
   this is a real-content sanity pass: heading structure, table
   headers, bar text equivalents with real values).
4. Defects triaged per standing decision 6: UI/copy/formatting fixes
   land in this task with tests where the defect class warrants one;
   anything touching data or aggregates is stop-and-report.
5. Findings worklogged: what was checked, what was found, what was
   fixed, what was escalated.
6. E2E suite still green (seeded CI data unchanged); all repo gates
   green.

## Task 30.2 — Queued Contract Closures

Two small queued items, one task.

Acceptance criteria:

1. **Message-constant migration:** `CHARGE_RESULT_UNAVAILABLE_MESSAGE`
   moves to `@pca/shared` per the §5 queue item, joining the other
   pinned literals; web imports it (never re-typed); the copy-safety
   scanner covers it; no behavior change.
2. **Duration-display resolution:** the queued question closes against
   recon item 4. If no duration data reaches public surfaces (the
   expected finding given categorical aggregates), the closure is
   documented — worklog + a methodology-adjacent note if user-facing
   clarity requires it — and the 360-day-year display question is
   formally retired for the MVP. If duration data DOES reach a public
   surface, stop-and-report: display units become a planning-chat
   decision before any rendering work.
3. Tests updated where imports moved; all repo gates green.

## Task 30.3 — Launch Copy + Date-Disclosure Pass

The 28.2 refresh did the heavy lifting; this is the launch framing
review under the resolved shipping model.

Acceptance criteria:

1. A full read of all public copy as served (methodology,
   data-coverage, definitions, about, result-page notices, unavailable
   arms, error messages) against the controlled-launch framing: honest
   date-range disclosure, no implied completeness, no residual
   "demo"/"seeded" framing anywhere, judge-thinness honesty intact,
   SD-15 disclosure intact.
2. Any copy edits land as shared constants under scanner coverage
   (existing rules; no new mechanism).
3. Both copy gates pass: mechanical scanner AND human framing review
   in planning chat.
4. The responsible-use review item from the §5 Sprint 9 queue is
   satisfied by this pass and marked closed (it was substantially done
   in 28.2; this formalizes it for launch).
5. All repo gates green.

---

# Phase 31 — Launch Package + Ship

## Task 31.1 — Demo Script + Demo Data Guardrails

bglad's S7-001, now writable with real slugs.

Acceptance criteria:

1. `docs/demo-script.md` exists with the exact demo path: known
   high-sample charge search → charge-only result (distributions,
   sample size, date range) → thin-data example → judge filter →
   judge-specific result beside baseline → judge-unavailable pair →
   sentencing-unavailable charge → remove-filter flow → methodology →
   data-coverage (2025-01-01 visible) → mobile view.
2. Every step names its real slug/URL from the currently published
   run, with expected on-screen outcomes described in copy-safe terms.
3. A staleness note: the script is a snapshot of a published run;
   republishing may shift thin-data flags and counts; the script
   states how to re-verify (one command / one walkthrough) rather
   than pinning numbers.
4. Known limitations relevant to a live demo are listed (judge
   thinness, MC/CP coverage shape, sentencing-unavailable classes).
5. Copy-safe throughout (it may be shown publicly); no docket numbers,
   no internals.

## Task 31.2 — Submission Package

bglad's Sprint 8, minus what already exists.

Acceptance criteria:

1. Root README rewritten for an outside reader: what the product is
   (historical aggregate distributions, not predictions, not legal
   advice), the controlled-launch state, the architecture at a
   paragraph level, and pointers into `docs/`.
2. Setup instructions verified by a fresh-clone dry run (agent-run):
   boot sequence, env expectations (`.env.example` complete), local
   URLs — the documented path actually works.
3. Known-limitations document consolidated from the honest disclosures
   already written (POC report, normalization report, methodology):
   one launch-facing summary, no overclaiming, no new claims.
4. Future-work document: admin review (ADR 0003), DB taxonomy tables
   (named landing: first taxonomy version bump or second writer),
   indexing/SEO, raw-PDF retention, richer visuals, coverage
   expansion.
5. Screenshots only if wanted for the submission — decided in planning
   chat, not assumed.
6. All copy gates apply to anything public-facing; all repo gates
   green.

## Task 31.3 — Deployment Decisions + Go-Live

The least pre-specified work in the sprint by design: it opens with a
decision gate, not a spec.

**Decision gate (planning chat, before any implementation):**

- hosting target for web (Next.js), API (Fastify), and PostgreSQL
- domain and TLS
- production secrets handling (`DATABASE_URL`, `DEFENDANT_HASH_SALT`
  posture for production — noting the salt is a pipeline concern and
  the deployed app may not need it at all; recon confirms what the
  API/web actually require)
- how the production database gets its data (the aggregate/ref layers
  are the only thing the public app reads — the deployment data path
  is a decision: managed Postgres loaded from the local run vs. other)
- rate limiting: implement `RATE_LIMITED` now or accept the
  controlled-launch exposure with a documented decision
- monitoring minimum for launch (uptime + error visibility; full
  monitoring stack is out of scope)

**Implementation acceptance criteria (post-decisions):**

1. The §5 localhost `API_BASE_URL` default is guarded or replaced —
   a production build cannot silently point at localhost.
2. Web and API deploy from production builds (the CI-proven `start`
   path); environment configuration documented; no secrets in the
   repo.
3. The production database serves the published run per the decided
   data path; the public endpoints verified against the deployed
   product (raw output verbatim).
4. noindex verified live on the deployed product (controlled launch).
5. Production smoke walkthrough: the 31.1 demo script executed
   end-to-end against the deployed URL.
6. Privacy boundary re-verified on the deployed product: forbidden-
   field spot checks against live endpoints; no internal IDs, paths,
   or parser details reachable.
7. Rollback story stated: what happens if the deploy is bad (at
   minimum: DNS/hosting-level rollback + the published-run model for
   data).
8. All decisions and their rationale recorded in a deployment ADR or
   equivalent doc.

## Task 31.4 — Human Step: Exit Demo + Sprint Close

Chops runs the exit demo against the DEPLOYED product and reviews in
the planning chat:

1. Deployed URL loads; noindex confirmed.
2. Judge autocomplete: zero fake judges; real roster names only.
3. Charge search → high-sample charge-only result: distributions,
   sample sizes, date range, responsible-use notice.
4. Thin-data example renders the warning.
5. Judge-specific result beside its baseline; a thin judge pair; a
   judge-unavailable pair falls back safely.
6. Sentencing-unavailable charge renders outcome + callout.
7. An affected held-for-court distribution shows the post-29.3 shape
   (pollution gone).
8. Methodology + data-coverage live: honest date window, current run
   metadata, no seeded/demo framing.
9. Demo script followed start-to-finish without deviation.
10. Submission package walkthrough (README, setup, limitations,
    future work).
11. Test-database guard demonstrated (deliberate-failure output).
12. Full CI green.

Sprint 7 closes here. Post-launch queue opens (collection cadence,
indexing decision, admin review, taxonomy-table landing trigger).

---

## Sprint 7 Definition of Done

1. No fake judge, alias, or seeded aggregate row exists in the live
   database; public search surfaces real rosters only; demo charges
   retained per the standing decision.
2. Accidental re-seeding of the live DB is structurally blocked (guard
   proven by deliberate failure).
3. The held-for-court fix is live: mechanism approved in planning
   chat, delta-disciplined, fact-rebuilt, republished; affected public
   distributions no longer carry bind-over pollution.
4. Every public page verified against real data on desktop and mobile;
   defects fixed or adjudicated; findings worklogged.
5. `CHARGE_RESULT_UNAVAILABLE_MESSAGE` lives in `@pca/shared`; the
   duration-display question is formally closed.
6. All public copy passes both gates under launch framing; honest
   date-range disclosures throughout; responsible-use review closed.
7. Demo script exists with real slugs and a staleness protocol.
8. Submission package complete; setup instructions proven by fresh
   clone.
9. The product is deployed: production builds, guarded base URL, live
   published run, noindex, privacy spot checks passed, rollback story
   stated, decisions recorded.
10. The exit demo ran against the deployed product and passed.
11. No public surface exposes raw docket data, defendant data, source
    documents, parser internals, fact IDs, or review data.
12. CI green throughout; no real-docket content entered the repo tree.
13. Sprint closed in the planning chat.

---

## Sprint 7 Risks (with mitigations)

1. **The sweep breaks something that silently depended on seeded
   rows** → recon item 1 enumerates dependents before deletion; CI
   proves the test path; post-sweep endpoint verification proves the
   live path; idempotent tooling means a partial sweep can re-run.
2. **The held-for-court fix has a wider blast radius than intended** →
   full delta discipline: mechanism approved before code, corpus
   verification proving the diff set is exactly the intended class,
   stop-and-report on anything unattributed.
3. **Republish surprises the live app** → existing validated publish
   machinery only (including the stale-run guard); generation and
   publication stay separate; the prior real run remains as the
   invalidated rollback target.
4. **Real data breaks layouts in ways seeds never did** → that's what
   30.1 exists to find, with a documented matrix instead of ad-hoc
   clicking; fixes are scoped UI work; data surprises escalate.
5. **Deployment expands into a swamp** → the decision gate keeps
   choices human and explicit; scope is fixed at "controlled launch
   minimum" (deployed, noindex, verified, rollback stated); everything
   else is post-launch queue.
6. **Copy drifts back toward demo framing during edits** → all edits
   land as shared constants under the scanner; human framing review is
   a required gate; 30.3 reads copy as served, not as written.
7. **Ongoing collection shifts counts mid-sprint** → numbers
   discipline: nothing pinned; the demo script carries a staleness
   protocol; republish rides 29.3 or waits for the post-launch
   cadence.

---

## Handoff to Post-Launch

Sprint 7 ends the pre-launch roadmap. The post-launch queue at close:

- collection cadence + republish rhythm (existing machinery; a
  scheduling decision, not a build)
- indexing/SEO decision (noindex lift is a deliberate future call)
- admin review (ADR 0003)
- DB taxonomy tables (landing trigger: first taxonomy version bump or
  second taxonomy writer)
- raw-PDF retention decision
- richer chart visuals revisit (table contract unchanged)
- MC/CP coverage expansion and judge-coverage deepening