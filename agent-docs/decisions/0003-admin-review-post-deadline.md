# ADR 0003: Admin Review Deferred to Post-Deadline Future Work

Status: Accepted
Date: 2026-07-13

## Context

The original roadmap included an administrative review capability: an
authenticated internal surface for reviewing flagged records, correcting
attributions, and auditing changes before they influence published
aggregates. Sprint 6 planning (sprint-6-plan.md, locked scope) explicitly
deferred it, and Task 28.2 requires the deferral to be documented.

## Decision

Admin review is NOT built for the MVP launch. It is post-deadline future
work. The MVP ships with structural exclusion instead of human review:

- Eligibility is decided on the facts at build time (Sprint 5):
  `public_eligible` / `judge_specific_eligible` plus reason codes. The
  aggregator only reads these flags (Sprint 6 SD-1); it never re-judges.
- Ambiguous or unclear records are therefore excluded from aggregates
  automatically — they can never reach the public API, so the absence of
  a human review step cannot leak an uncertain figure.
- `review.queue_items` and the fact-layer review flags continue to be
  populated, so the future admin surface starts with a backlog of real
  flagged records rather than a cold start.

The public methodology copy states the user-facing consequence (no
manual correction of individual figures in this version; planned as
future work) without internal-process vocabulary — the methodology route
tests forbid words like "review" and "workflow" as internal detail.

## Scope of the future work (not committed to a sprint)

- Admin authentication and an internal-only surface (never the public API)
- Review queue triage over `review.queue_items`
- Correction workflow with an audit trail
- Re-aggregation path so corrections flow into a NEW aggregate run
  (published runs stay immutable; the publish swap is the only activation
  mechanism)

## Consequences

- Data quality control before launch rests on structural eligibility,
  validation (`pipeline validate-aggregates`), and the privacy scan —
  all publish-blocking.
- Individual erroneous source records can only be corrected by
  re-collection/re-parse and a fresh fact-build + aggregate run, not by
  hand-editing.
