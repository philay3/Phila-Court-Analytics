# Project Brief: Philadelphia Court Outcomes Analytics

## Project Summary

Philadelphia Court Outcomes Analytics is a public-facing web application that helps users understand historical aggregate outcomes in Philadelphia criminal court cases.

Users search for a criminal charge and may optionally add a judge. The product then displays historical distributions for:

- case outcomes
- sentencing outcomes
- Philadelphia-wide charge results
- judge-specific charge results, where available
- Philadelphia-wide baseline comparisons

The application must clearly communicate that it shows historical distributions, not predictions, legal advice, or guarantees.

## Core Product Concept

A user enters or selects a criminal charge. The system returns Philadelphia-wide historical aggregate data for that charge.

The user may optionally enter or select a judge. If judge-specific aggregate data is available, the system shows the judge-specific historical distribution beside the Philadelphia-wide baseline for the same charge.

The product should include both outcome and sentencing distributions, including categories such as dismissal, withdrawal, guilty plea, guilty verdict, acquittal, ARD, diversion, probation, incarceration, fines, restitution, and other supported outcomes.

## MVP Scope

The MVP is limited to:

- Philadelphia criminal court data
- public docket sheet PDFs from Pennsylvania UJS as the initial source
- charge-level aggregate analytics
- historical outcome distributions
- historical sentencing distributions
- optional judge-specific filtering
- public aggregate-only display
- admin review tools for parser/normalization/attribution issues

## Out of Scope for MVP

The MVP does not include:

- civil court analytics
- statewide coverage
- individual case lookup
- defendant lookup
- attorney recommendations
- legal advice
- prediction or risk scoring
- judge rankings
- “best judge” or “worst judge” features
- automated broad ingestion before source-access/compliance review

## Primary Users

### Non-lawyer users

People charged with an offense, their family members, or members of the public who want a plain-English view of historical outcomes.

### Attorneys and legal professionals

Defense attorneys or other legal professionals who want a quick historical aggregate reference.

### Researchers, journalists, and civic users

People interested in public court outcome patterns.

### Internal reviewers/admins

Team members who review parser output, normalize data, correct mappings, and approve or exclude uncertain records.

## Key Product Principles

1. Charge-first search
2. Judge is optional
3. Charge-only Philadelphia-wide result is first-class
4. Judge-specific result includes Philadelphia baseline
5. Sentencing distributions are included
6. Every figure shows sample size
7. Thin data is surfaced, not hidden
8. Public output is aggregate-only
9. No defendant-identifying information is exposed publicly
10. Historical distributions are not predictions
11. The system must support methodology, definitions, and responsible-use copy

## Data Source

Initial source:

- public docket sheet PDFs from Pennsylvania UJS

The system should support manual import first. Broad automated ingestion should not proceed until source-access, compliance, retention, and rate-limit questions are reviewed.

## Technical Direction

Recommended architecture:

- Next.js / React / TypeScript frontend
- TypeScript backend API using Fastify
- PostgreSQL database
- Python data pipeline for PDF ingestion, extraction, parsing, normalization, attribution, and aggregation
- private S3-compatible object storage for raw PDFs and extracted text
- shared taxonomy and API schema packages
- admin review workflow
- aggregate publication and rollback controls

## Success Criteria

The MVP is successful when:

- a user can search by charge
- charge-only Philadelphia-wide results load
- optional judge-specific results load when available
- outcome and sentencing distributions are visible
- sample size and date range are visible
- thin-data states are visible
- methodology and definitions are available
- public API exposes aggregate-only data
- parser proof of concept validates charge-level outcome and sentence extraction
- admin review workflow can handle ambiguous records
- source-access/compliance review is complete before broad ingestion
