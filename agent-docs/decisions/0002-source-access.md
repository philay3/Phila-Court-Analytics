# ADR 0002: Source Access — UJS Portal Collection

Status: Accepted
Date: 2026-07-10

## Context

The MVP's data source is public docket sheet PDFs from the Pennsylvania
UJS portal. Automated collection (the Capstone Playwright collector) was
parked pending a source-access/compliance review (a Sprint 9 launch
gate). That review is now complete.

## Review performed

1. Academic review: compliance review conducted as part of a course
   requirement, in consultation with a lawyer. Conclusion: the docket
   sheets are public information; collection is acceptable provided it
   does not disrupt the portal's operation.
2. Independent counsel: reviewed with the project's own lawyer.
   Conditions set: no more than 4 hours of continuous collection per
   session; a break between sessions; no more than 8 hours of
   collection per day.

## Decision

Automated collection is UNPARKED under the following conditions:

- **Session cap:** ≤ 4 hours continuous collection per session.
- **Daily cap:** ≤ 8 hours total collection per day.
- **Non-disruption:** collection must not degrade portal service.
  Per counsel: occasional rate limits or blocks are acceptable and
  expected; they are NOT a violation. The stop condition is being
  blocked a large number of times consecutively — a sustained block
  streak ends the run. An individual rate limit is handled by a
  2-minute cooldown before resuming.
- **Batch pacing (initial parameters, ours to tune):** ~40 dockets
  per batch, then a 4-minute cooldown, repeating. These numbers are
  the agreed starting point discussed with counsel, to be re-evaluated
  against observed portal behavior after the baseline run — they are
  operational parameters, not fixed legal conditions.
- **Timing:** weekends are the preferred collection window — counsel
  was explicit that weekend collection, when the portal has no
  business traffic, is cleared. Weekday collection remains within the
  session/daily caps but weekends are the default posture.
- **Observability:** collection runs must show live progress —
  batches completed, dockets attempted, hits/misses, rate-limit
  events, cooldowns in progress. Operator must be able to see what
  the run is doing at all times.
- **Run logging:** every run logs timestamps, docket numbers
  attempted, and outcomes — the good-faith record of collection
  behavior.
- **Output boundary:** collected PDFs land under ~/court-data/, never
  in any repo; they enter the pipeline via the manual-import path
  (hashing, dedupe, metadata).
- **Throttle review first:** before the first automated run, the
  Capstone collector's pacing behavior is reviewed and, if needed,
  patched to enforce the caps and pacing above in code, not by
  operator attention.

## Enumeration strategy

Coverage is tracked by docket-number ranges, not date ranges. Docket
numbers are sequential per court/year (e.g. CP-51-CR-#######-YYYY),
so range enumeration yields a true denominator: hits AND misses are
logged, and coverage is expressible as "N of M dockets in range."
This feeds the public data-coverage page and Sprint 7 aggregation.

## Open items

- **Written confirmation on bot-check handling:** counsel's conditions
  covered duration and disruption. Whether the collector's handling of
  the portal's bot checks was specifically covered is to be confirmed
  in writing before extended/regular collection. Not blocking a single
  short baseline run.
- **Multi-operator rotation:** distributing collection hours across
  multiple people was discussed as a future option. Deferred; requires
  the written confirmation above to address whether rotation is
  consistent with the intent of the hours conditions.
- **Raw PDF retention:** remains a separate Sprint 9 launch-gate
  decision; not resolved by this ADR.

## Consequences

- The Sprint 9 "source-access/compliance review" launch gate is
  pre-cleared, subject to the open items above.
- The first automated run is a one-hour baseline run (own task,
  scheduled after task 18.3), conducted on a WEEKEND per counsel's
  explicit clearance, using docket-number enumeration, 40-docket
  batches with 4-minute cooldowns, 2-minute rate-limit cooldowns,
  and stop-on-sustained-block-streak.
- The standing decision "collector stays PARKED" is superseded by
  this ADR.
