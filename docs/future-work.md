# Future work

Named work that is deliberately not built yet. Each item carries its landing
or trigger where one exists. Nothing here is a commitment to a date; the list
exists so deferred decisions stay visible instead of silently forgotten.

1. **Admin review.** An authenticated internal surface for reviewing flagged
   records, correcting attributions, and auditing changes before they
   influence published aggregates. Deliberately deferred: the MVP ships
   structural exclusion instead (unclear records are excluded automatically,
   never corrected by hand). Landing:
   [ADR 0003](decisions/0003-admin-review-post-deadline.md) — post-deadline
   future work, with the review queue already accumulating typed,
   deduplicated items as its input.

2. **Database-backed taxonomy tables.** Outcome and sentencing taxonomy
   currently lives in versioned seed JSON in `packages/taxonomy/`. Landing
   trigger: the first taxonomy version bump or the arrival of a second
   taxonomy writer — whichever comes first.

3. **Indexing / SEO.** The site ships with deliberate site-wide `noindex`
   (controlled launch). Lifting it is a deliberate future call, decided
   explicitly — not a default that expires.

4. **Raw-PDF retention.** A retention policy decision for collected source
   PDFs, which today live outside the repository on the operator's machine.

5. **Richer chart visuals.** A revisit of result visualizations beyond the
   current presentation. The table contract (every figure available as an
   accessible table) is unchanged by any future visual work.

6. **Coverage expansion.** Deepening Common Pleas and Municipal Court
   collection and judge-level coverage. The unresolved Municipal Court
   bind-over linkage tail (see
   [known-limitations](known-limitations.md)) is the standing signal for
   where collection goes next.

7. **Autocomplete pre-hydration input gap.** Server-rendered search
   comboboxes are visible before client handlers attach, so characters typed
   in the brief window before hydration completes are dropped. Framework-
   inherent behavior, recorded as a queue item rather than a defect.

8. **Stale in-progress aggregate-run housekeeping.** Aggregate runs that were
   generated but never published remain in the runs table with an
   in-progress status. They are harmless to the public product — the API's
   predicate selects only the active published run — but a housekeeping
   decision (mark, remove, or leave) is queued.

9. **Collection cadence and republish rhythm.** How often collection runs and
   how often a new aggregate run is published. The machinery exists; this is
   a scheduling decision, not a build.

10. **Sprint-plan document publication.** The sprint 4–7 plan documents are
    currently unpublished. Publishing them includes updating their path
    references to the consolidated documentation tree (one known stale
    reference to the retired `agent-docs` directory in the sprint-5 plan).
