# Front-End / UX Specification: Philadelphia Court Outcomes Analytics

## UX Vision

The product should feel like a neutral civic data tool, not a legal prediction engine, not a crime site, and not a judge-ranking platform.

The experience should help users answer:

> Historically, what happened in Philadelphia cases involving this charge?

And, optionally:

> What does the historical distribution look like when this judge is selected, compared with the Philadelphia-wide baseline?

## Design Principles

1. Clarity over drama
2. Charge-first, judge-optional
3. Context before conclusion
4. Distributions, not predictions
5. Sample size always visible
6. Thin data surfaced plainly
7. Plain-English definitions
8. Accessible charts and tables
9. Neutral, non-ranking tone
10. Public privacy by design

## Target Personas

### Non-lawyer user

Needs plain-English labels, low jargon, clear caveats, and visible sample size.

### Attorney or legal professional

Needs fast search, accurate labels, definitions, date range, and baseline context.

### Researcher/journalist/civic user

Needs methodology, data coverage, definitions, and limitations.

### Admin/data reviewer

Needs review queues, parser context, correction actions, and audit visibility.

## Information Architecture

Public pages:

- `/`
- `/search`
- `/charges/[chargeSlug]`
- `/charges/[chargeSlug]/judge/[judgeSlug]`
- `/methodology`
- `/definitions`
- `/data-coverage`
- `/about`

Admin pages:

- `/admin`
- `/admin/imports`
- `/admin/review-queue`
- `/admin/review-queue/[itemId]`
- `/admin/normalization/charges`
- `/admin/normalization/judges`
- `/admin/aggregate-runs`
- `/admin/audit`

## Core User Flows

### Charge-Only Lookup

1. User lands on homepage.
2. User enters a charge.
3. User selects charge from suggestions.
4. User lands on Philadelphia-wide charge result page.
5. User sees outcome distribution, sentencing distribution, sample size, date range, thin-data status, and responsible-use copy.

### Charge + Judge Lookup

1. User selects a charge.
2. User optionally selects a judge.
3. User lands on judge-specific result page.
4. User sees judge-specific distribution beside Philadelphia-wide baseline.
5. User can remove judge filter and return to charge-only result.

### Judge-Specific Unavailable Flow

1. User selects charge and judge.
2. System has no judge-specific aggregate.
3. User sees a safe unavailable state.
4. User is directed to Philadelphia-wide charge result.

## Homepage Requirements

Homepage should include:

- primary charge search
- optional judge input
- short responsible-use statement
- links to methodology and data coverage
- simple explanation that results are historical aggregates

Judge input must not feel required.

## Charge-Only Result Page

Must show:

- charge display name
- “Philadelphia-wide historical result” label
- sample size
- date range
- thin-data badge/callout where applicable
- outcome distribution chart/table
- sentencing distribution chart/table
- definitions links
- methodology summary
- responsible-use notice
- optional “Add judge filter” control

## Judge-Specific Result Page

Must show:

- charge display name
- judge display name
- judge-specific sample size
- Philadelphia baseline sample size
- judge-specific outcome distribution
- Philadelphia baseline outcome distribution
- judge-specific sentencing distribution where available
- Philadelphia baseline sentencing distribution where available
- thin-data callouts
- responsible-use notice

Avoid labels like “better,” “worse,” “harsher,” or “more lenient.”

## Key Components

Search:

- `ChargeSearchInput`
- `JudgeSearchInput`
- `SearchForm`
- `ChargeDisambiguationList`
- `SearchSuggestionList`
- `SelectedJudgeFilterChip`

Results:

- `ResultSummaryCard`
- `ResponsibleUseNotice`
- `ThinDataBadge`
- `ThinDataCallout`
- `SampleSizeLabel`
- `DateRangeLabel`
- `OutcomeDistributionSection`
- `SentencingDistributionSection`
- `BaselineComparisonSection`
- `ResultUnavailableState`
- `MethodologySummaryPanel`
- `DefinitionsDrawer`

Charts:

- `OutcomeBarChart`
- `SentencingBarChart`
- `BaselineComparisonChart`
- `AccessibleChartWrapper`
- `ChartDataTable`

Admin:

- `AdminShell`
- `ImportBatchTable`
- `ReviewQueueTable`
- `ReviewItemDetail`
- `RawExtractedTextPanel`
- `ParsedFieldsPanel`
- `NormalizedFieldsPanel`
- `ReviewActionForm`
- `AggregateRunTable`
- `AuditEventTable`

## Visual Language

Use:

- calm civic tone
- restrained color palette
- clear typography
- card-based result sections
- charts paired with tables
- badges for thin data and sample size

Avoid:

- dramatic colors implying danger
- red/green moral judgments
- ranking visuals
- predictive probability language
- “score” displays

## Approved Public Language

Preferred:

- historical outcome distribution
- historical sentencing distribution
- Philadelphia-wide result
- judge-specific result
- sample size
- thin data
- not legal advice
- not a prediction

Avoid:

- odds
- likely sentence
- predict
- best judge
- worst judge
- judge score
- win rate
- guaranteed result

## Accessibility Requirements

- WCAG 2.2 AA target
- keyboard-accessible autocomplete
- visible labels
- accessible drawer focus management
- chart table equivalents
- no hover-only critical information
- no color-only meaning
- screen-reader-friendly result summaries
- mobile-first readable order

## Responsive Behavior

On mobile, result pages should prioritize:

1. result summary
2. responsible-use notice
3. thin-data callout
4. outcome table
5. sentencing table
6. charts
7. definitions
8. methodology

## SEO and Indexing

Initial defaults:

- homepage may index after review
- methodology may index after review
- definitions may index after review
- data coverage may index after review
- charge-only result pages default to `noindex`
- judge-specific result pages default to `noindex`
- admin pages always `noindex`
