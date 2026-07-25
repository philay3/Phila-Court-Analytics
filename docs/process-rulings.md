# Process rulings — durable record

**What this file is.** The on-disk landing for process rulings adjudicated in
planning chat. It exists because of the finding inside a finding on 2026-07-25:
a real ruling (the 36.0 worklog waiver) could not be verified by anyone reading
the repo, because it lived only in a chat relay and an adjudication file that
never persisted. **Chat rulings are not durable.** From this entry forward,
process rulings are recorded here at the time they are made.

**Scope.** Process and standing rulings only — how work is run, recorded, and
gated. Content rulings about a specific phase's design belong in that phase's
report and the planning docs. Architecture decisions belong in `docs/decisions/`.

**Placement note.** `docs/` root, per `CLAUDE.md` ("Documentation you generate …
goes elsewhere under `docs/`"). Not an ADR: this is a running log, not a single
architecture decision, so it takes no `decisions/` number. Move it if you'd
rather it be numbered.

---

## PR-1 — Worklog entry waived for Task 36.0 and 36.0-A (read-only recons)

**Ruled:** planning chat, Task 36.0 plan adjudication ("the Q1 ruling"), restated
and confirmed 2026-07-25.

**Ruling.** A read-only recon task writes **no `tasks/worklog.md` entry**. Its
outcomes ride the worklog entry of the phase's first build commit.

**Status: intended deviation from `CLAUDE.md`.** Workflow step 6 makes a worklog
entry mandatory and part of the same commit. That rule assumes a task that
commits code. A recon commits nothing, so there is no commit for the entry to be
part of, and an entry written ahead of the build would record findings before
they are adjudicated. The deviation is deliberate, scoped to read-only recon
tasks, and this record is its basis.

**Why it is recorded here.** The pre-check on 2026-07-25 could not verify the Q1
ruling from disk — the 36.0 report cites plan fixes F1–F4 and rulings Q2 and Q4,
with no Q1 anywhere. The ruling was real; the record was not. That gap is what
PR-2 closes.

---

## PR-2 — Process rulings are recorded on disk (standing)

**Ruled:** 2026-07-25.

**Ruling.** A process ruling made in planning chat is written to disk — this file
or `docs/board.md` — at the time it is made. A ruling that exists only in chat is
treated as unverifiable by any later reader, including the agent executing
against it.

**Consequence for agents.** If a task cites a ruling that cannot be found on
disk, that is a reportable finding, not a blocker: proceed, and name the ruling as
unverified. Do not infer its content.

---

## PR-3 — F3: corpus census at both ends of a read-only session (standing)

**Ruled:** Task 36.0 plan adjudication (plan fix F3), confirmed standing 2026-07-25.

**Ruling.** Every read-only session over the canonical corpus takes a docket and
charge census at open and at close. If they differ, every affected figure is
labeled to its census. A session whose corpus moved underneath it does not
produce acceptance-grade figures without that labeling.

**Live context at the time of ruling.** `~/court-data/refresh-intake-2026-07-22/`
was at 7,083 files and growing; nothing from it may be loaded mid-session.

---

## PR-4 — Charge-text hygiene, with the class (iii) carve-out (standing)

**Ruled:** 2026-07-25 (finding S17 of the 36.0-A pre-check).

**Ruling.** Statute citations and offense descriptions **may** appear in reports
and planning-chat relays. They are statutory text carrying no personal
information; this follows the 32.3 disposition-string precedent directly.

**Carve-out, non-negotiable.** Charge text classified as — or suspected of being
— a fragment, parse artifact, or glued column reports **counts plus a structural
signature** (length, character-class composition, tripped predicate) with the
**raw form withheld or hash-prefixed**, unless individually cleared. Rationale:
that class is by definition where the capture is *not* clean statutory phrasing,
and the 34.3 column-concatenation evidence shows adjacent docket columns do get
glued into captured text. It is the one place defendant-adjacent text could ride
into a report otherwise cleared to print charge text.

**Enforcement is mechanical, not discretionary.** Implemented as a fail-closed
predicate in the reporting instrument (see `render_form()` /
`contamination_signals()` in `~/court-data/recon-36.0-A/funnel_census_a.py`),
so a contaminated form cannot print by oversight.

Everything else in §6.5 is unchanged: no docket numbers in any output, in any arm.

---

## PR-5 — Read-only DB sessions run in Claude Code, not Cowork (standing)

**Ruled:** 2026-07-25.

**Ruling.** Sessions requiring queries against canonical `pca` are executed by
Claude Code. Cowork sessions run in an isolated cloud sandbox with no network
path to the local database and no `psql` — the block is structural, not
configuration.

**Division of labour.** Cowork: spec amendment, query-set authoring, assembly of
returned output, verification, and findings. Claude Code: execution under
`PGOPTIONS="-c default_transaction_read_only=on"` with both posture
confirmations and the F3 census. Hand-running large query sets is the worst
option and is not the fallback.

**Consequence for specs.** A spec whose items require the database names Claude
Code as executor. A Cowork session handed such a spec reports the block, runs
everything that does not need the DB, and returns the remainder as a query set.
