# Known limitations

A launch-facing summary of what the data does and does not cover. This
document consolidates disclosures already made in three places — the
[parser proof-of-concept report](parser-proof-of-concept.md), the
[normalization and attribution report](normalization-attribution-report.md),
and the methodology and data-coverage copy served by the application itself —
into one place. It makes no new claims; the source documents remain the
authoritative detail, and each section names where its content comes from.

## Coverage and time window

_Sources: served methodology and data-coverage copy; normalization report
§10._

- Coverage begins on January 1, 2025, anchored to disposition and sentencing
  event dates, not filing dates. Earlier history is absent. A case filed
  earlier is included only when its qualifying event happened on or after that
  date.
- Collection is ongoing. The covered records are a growing subset of
  Philadelphia criminal cases, and figures change as newly collected records
  are aggregated.
- Coverage includes misdemeanor and felony charges, along with summary-graded
  charges when they are part of a criminal case; standalone summary citations
  are not collected. Charges from cases still awaiting a final outcome do not
  appear until one is recorded.
- The date window is the dominant reason the publicly eligible sample is far
  smaller than the collected corpus: records are collected by filing and
  docketing date, but eligibility is decided by disposition and sentencing
  date, so "collected" and "eligible" differ by disposition timing, not by
  error.

## Court coverage: Common Pleas and Municipal Court

_Source: normalization report §7, §9._

- Most Municipal Court charge volume consists of "Held for Court" bind-overs
  — cases that move on to the Court of Common Pleas for resolution. Those
  bind-over outcomes map to non-public categories, so none of them reaches
  public figures. This is the Municipal Court behaving as the lower court:
  its contribution to public data is the smaller slice of cases that
  terminate there.
- Bind-over cases whose Common Pleas counterpart has not yet been collected
  form an unresolved linkage tail. That tail is a coverage signal (the reason
  Common Pleas collection is the priority), not a defect.
- Whether "Held for Court" should be modeled as a non-terminal state rather
  than mapped to a (non-public) outcome category is an open
  taxonomy-semantics question, flagged for adjudication. Today it is
  contained: nothing from it leaks into public data.

## Exclusion, not correction

_Sources: normalization report §9, §10; served methodology copy; ADR 0003._

- Public eligibility is decided by explicit boolean gates with
  machine-readable reason codes. There are no confidence scores anywhere in
  the pipeline. "Unmatched" is a recorded state that produces a review item
  and an ineligible fact — never a silent inclusion.
- Charges, dispositions, and judges that do not normalize against the curated
  rosters are excluded from public figures and routed to review. The rosters
  were curated against a corpus dominated by Common Pleas records, so newer
  Municipal Court vocabulary carries a normalization tail; closing it is
  roster and mapping curation work.
- Records whose outcome or judge attribution is unclear are excluded
  automatically rather than resolved by hand, and no figure is adjusted or
  corrected manually after aggregation in this version — a manual review
  process is deliberately deferred future work (ADR 0003).

## Judge attribution

_Source: normalization report §6, §10._

- Attribution is conservative, with exactly one path per fact: the
  disposition-judge value when it matches a real roster entry; otherwise the
  assigned-judge value only under a documented single-judge, roster-matched
  rule; otherwise the fact is left unattributed. Name-shaped values that are
  not judges resolve to unmatched and route to review — never guessed.
- Unattributed judges never block charge-only figures; they only gate the
  judge-specific surface.
- Judge attribution is complete on the Common Pleas side; the Municipal Court
  side carries a tail that is not yet roster-attributable, so the
  judge-specific surface is thinner there and is sized honestly per cell
  rather than presented as uniform.

## Thin data

_Sources: served methodology copy; normalization report §11._

- When a figure rests on a small sample it is labeled as thin data and shown
  with that warning rather than hidden. Small samples can shift noticeably as
  new cases arrive.
- At this stage most judge-specific figures are thin: the thin-data warning
  is the norm for judge-level results, and judge-level coverage deepens as
  collection continues.
- Eligible cells are generally small because of the date window (above); this
  is expected and disclosed, not an anomaly.

## Sentencing figures

_Sources: served methodology copy; normalization report §9, §10._

- The sentencing sample counts sentence components, not sentenced charges. A
  single sentencing event can include several components (for example
  probation plus a fine), each counted as its own entry. Sentencing samples
  are a distinct population from outcome samples and can be smaller or
  larger; a charge with an outcome but no sentence component is normal, not
  an error. Sentencing figures may be unavailable for some charges.
- Sentencing dates are recorded independently of disposition dates: the two
  usually coincide, but a small share of sentencing dates fall earlier, and
  whether a sentencing event is inside the covered period is decided by the
  sentencing date itself.
- Monetary amounts are extracted with a deliberate false-negative bias:
  amount coverage is low, and a monetary component with no parseable amount
  still maps its category (category mapping never depends on amount
  parsing). Whether amount-based views ship at all is an open decision.

## Extraction and parsing

_Sources: parser proof-of-concept report §7–§10; served methodology copy._

- Docket sheets are summaries and may be amended after we aggregate them.
- One unsupported docket format class is known: such documents are
  quarantined rather than parsed, and quarantined documents produce no facts.
- OCR is unimplemented. The collected corpus is text-native; a scanned or
  low-text page would be flagged for review rather than silently processed,
  but that path has been exercised only by synthetic tests. The decision is
  revisited if a scanned docket appears.
- Restitution is not a distinct parsed sentence component: it survives only
  inside the raw text of fines-and-costs lines. Its taxonomy mapping is named
  future work in the source report.
- Sentence durations are normalized internally on a 360-day-year convention
  (day = 1, month = 30, year = 360), with the raw source text always
  retained, so no source information is lost by normalization.
- Judge-slot values in raw dockets carry no identity validation at parse
  time. Obvious non-judge captures are guarded out, and the durable
  protection is downstream: values that do not match the judge roster are
  excluded from public data (see Judge attribution above).
- The third-party name privacy guard is pattern-based and covers the two
  known judge-label contexts only; there is no NER-grade name detection.
  Other contexts rely on a fail-closed leak assertion and upstream capture
  bounds. This is stated in the source report as a documented limitation,
  without overclaim.

## Aggregation categories

_Source: served methodology copy._

- Aggregation groups many distinct raw dispositions into broad categories,
  and some charges have little or no data yet. Where the data is thin, the
  figures say so.
- Every figure is a historical aggregate: it summarizes groups of past cases
  as a whole and never describes an individual case. These figures are
  historical summaries — they are not a prediction of any future outcome,
  and this site does not provide legal advice.
