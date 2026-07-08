# Decision 0001: PDF Extractor — pdfplumber

Date: 2026-07-08
Status: Accepted
Task: 5.3 (Sprint 1 extractor evaluation)

## Decision

pdfplumber is the extraction library for the production pipeline. The
`extract-text` pipeline stage (Sprint 4) will be built on pdfplumber output.

## Evaluation

Harness (Task 5.1) ran pymupdf, pdfplumber, and pypdf against 20 real UJS
docket fixtures (CP and MC, 3–25 pages). Metrics were automated; readability
was judged by human side-by-side reading of text dumps against source PDFs
across a 5–6 file sample including both multi-disposition heavy files.

- pdfplumber: charge tables and disposition/sentencing blocks matched the
  visual docket layout on every file checked. Best readability across CP,
  MC, large multi-disposition, and small dockets.
- pypdf: acceptable charge tables, second overall.
- pymupdf: scrambled charge tables consistently. Fastest (~13x over
  pdfplumber) but speed is a non-factor at MVP batch scale.

## Supporting factors

- Incumbency: the Capstone parser (Sprint 4 port source) was built against
  pdfplumber output.
- License: pdfplumber is MIT; pymupdf is AGPL, which would have raised
  source-offering questions for a public-facing service.

## Known limitation

The fixture corpus contained only clean, text-native PDFs — zero scanned or
image-only dockets. The needs_ocr_or_review path was exercised only by
synthetic tests. Revisit if a scanned docket surfaces.

## Consequences

- Sprint 4 extraction is pdfplumber-based; parser port proceeds against its
  known output shape and documented failure modes.
- pymupdf and pypdf remain dependencies of the evaluation harness only;
  they must not be imported by production pipeline stages.
