# Product Requirements Document: Philadelphia Court Outcomes Analytics

## Goals

The product should help users understand historical aggregate outcomes and sentencing patterns in Philadelphia criminal court cases.

The product must:

- allow charge search
- allow optional judge filtering
- show Philadelphia-wide charge results
- show judge-specific results with Philadelphia baseline where available
- include outcome distributions
- include sentencing distributions
- use charge-level analytics
- show sample size on every figure
- surface thin data
- avoid prediction, odds, legal advice, and judge-ranking language
- expose only aggregate public data

## Background

The product is inspired by public court analytics tools such as Virginia Court File, but scoped to Philadelphia criminal court data.

The data source is public docket sheet PDFs from the Pennsylvania UJS portal. The application must parse, normalize, review, and aggregate docket information before displaying public results.

## Functional Requirements

### FR1: Charge Search

Users can search by:

- common charge name
- raw docket charge text
- statute/offense code where available
- aliases and variants

The system returns normalized charge suggestions.

### FR2: Optional Judge Search

Users may optionally search/select a judge.

Judge search is not required for charge-only results. If no judge is selected, the product shows Philadelphia-wide historical data for the charge.

### FR3: Charge-Only Result

The system displays Philadelphia-wide aggregate data for a selected charge.

The result includes:

- charge name
- geography label
- sample size
- date range
- outcome distribution
- sentencing distribution when available
- thin-data indicator
- responsible-use notice
- definitions and methodology links

### FR4: Judge-Specific Result

The system displays judge-specific aggregate data for a selected charge and judge when available.

The result includes:

- charge name
- judge name
- judge-specific outcome distribution
- judge-specific sentencing distribution where available
- Philadelphia-wide baseline
- sample sizes for judge-specific and baseline data
- date ranges
- thin-data indicators
- responsible-use notice

### FR5: Judge-Specific Unavailable Fallback

If judge-specific data is unavailable, the product should not dead-end.

It should:

- explain that judge-specific aggregate data is unavailable
- offer the charge-only Philadelphia-wide result
- avoid internal parser/review/source details
- avoid prediction language

### FR6: Outcome Distribution

The product must support outcome categories such as:

- dismissed
- withdrawn
- guilty plea
- guilty verdict
- acquittal
- ARD
- diversion
- other supported outcomes

Each category should show count and percentage.

### FR7: Sentencing Distribution

The product must support sentencing categories such as:

- probation
- incarceration
- fine
- restitution
- community service
- no further penalty
- costs / fees
- other supported sentencing outcomes

Sentencing sample size may differ from outcome sample size and must be shown separately.

### FR8: Charge-Level Analytics

Outcome and sentencing facts must be attributed at the charge level, not only the docket level.

Ambiguous attribution should create review items and should not silently enter public aggregates.

### FR9: Thin Data Handling

Every public result should include thin-data status.

Thin data should be surfaced through:

- badge
- callout
- sample size
- explanation

Exact thresholds are to be finalized after parser/data review.

### FR10: Public Definitions and Methodology

The product must include:

- definitions page
- methodology page
- data coverage page
- responsible-use language
- public explanation of sample size and thin data

### FR11: Admin Review

Admin users can review parser, normalization, and attribution issues.

Admin actions include:

- approve
- correct
- exclude
- mark needs more review

Every admin write action must create an audit event.

### FR12: Aggregate Publication

Public API should read only from published/completed aggregate runs.

Failed or in-progress aggregate runs must not affect current public results.

## Nonfunctional Requirements

### Performance

- Public result pages should be fast.
- Public result APIs should read precomputed aggregates.
- Search should be responsive.
- Charts should not block table rendering.

### Reliability

- Pipeline failures should not break public pages.
- Public API serves last valid published aggregate.
- Aggregate rollback is supported.

### Security and Privacy

- Public API exposes aggregate-only data.
- Raw PDFs are private.
- Extracted text is private.
- Defendant names and docket numbers are not public.
- Admin routes require authentication.
- Admin write actions are audited.

### Accessibility

- Target WCAG 2.2 AA.
- Autocomplete must support keyboard navigation.
- Charts need table equivalents.
- Critical meaning cannot rely on color only.
- Definitions must not rely on hover only.

### Transparency

- Sample size shown on every figure.
- Date range shown on result pages.
- Thin-data state shown.
- Methodology and definitions available.

## MVP Epics

1. Foundation and repository setup
2. Seeded public UI/API
3. Parser proof of concept
4. Normalization and charge-level attribution
5. Admin review workflow
6. Aggregate generation and publication
7. Staging validation
8. Launch readiness

## Launch Gates

The MVP should not publicly launch until:

- parser fixtures pass
- charge-level attribution is validated
- sentencing attribution is validated or clearly limited
- public aggregate validation passes
- admin review workflow works
- public forbidden-field tests pass
- raw PDFs and extracted text are private
- responsible-use language is reviewed
- methodology and definitions are complete
- source-access/compliance review is complete
- staging public/admin flows pass
- monitoring and rollback are active

MVP data coverage starts on January 1, 2025. Outcome aggregates include eligible charge-level outcomes with disposition dates on or after January 1, 2025. Sentencing aggregates include eligible charge-level sentence facts with sentencing dates on or after January 1, 2025. Earlier-filed cases may be included if the relevant disposition or sentencing event occurred on or after January 1, 2025.