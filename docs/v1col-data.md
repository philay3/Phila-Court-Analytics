# Collected Data & Privacy Specification

This document details the exact judicial data extracted from Municipal Court (MC) and Court of Common Pleas (CP) docket sheets, how it maps to database tables, and the privacy safeguards applied to avoid storing Personal Identifying Information (PII).

---

## 1. Case Metadata

Extracted from the `CASE INFORMATION` and `STATUS INFORMATION` sections of the docket sheet and written to `parsed.dockets`.

- **Docket Number** (`docket_number`): The primary court case identifier (e.g., `MC-51-CR-...`).
- **Case Status** (`case_status`): The current state of the case (e.g., `Active`, `Closed`, `Deferred`).
- **Filed Date** (`filed_date`): The date the case was officially opened.
- **OTN (Offense Tracking Number)** (`otn`): The unique tracking number assigned by law enforcement at arrest.
- **DC Number (District Control)** (`dc_number`): The police department incident report number.
- **Assigned Judge** (`assigned_judge_raw`): The raw name of the judge currently assigned.
- **Cross-Court Docket Numbers** (`cross_court_dockets`): String list of associated docket numbers (e.g., matching Municipal Court and Court of Common Pleas sheets).
- **County** (`county`): Hardcoded to `Philadelphia`.

---

## 2. Charge Information

Extracted from the `CHARGES` section of the docket sheet and written to `parsed.charges`.

- **Sequence** (`sequence`): The numeric list order of the charge on the docket.
- **Statute Code** (`statute`): The Pennsylvania statute citation (e.g., `18 § 2701`).
- **Grade** (`grade`): The severity level of the charge (e.g., `F1`, `F2` for felonies; `M1`, `M2` for misdemeanors).
- **Offense Description** (`offense`): A text description of the charge (e.g., `Simple Assault`).
- **Raw Disposition** (`disposition_raw`): The outcome of the charge (e.g., `Guilty Plea`, `Withdrawn`, `Dismissed`).
- **Disposition Date** (`disposition_date`): The date the outcome was decided.
- **Disposition Judge** (`disposition_judge_raw`): The judge who ruled on/disposed the charge.
- **Event Name & Date** (`event_name`, `event_date`): Calendared hearings captured specifically for non-terminal (still pending) charges.

---

## 3. Sentencing Information

Extracted from the `DISPOSITION SENTENCING/PENALTIES` section of the docket sheet and written to `parsed.sentences`.

- **Sentence Type** (`sentence_type`): The structured sentence classification:
  - `Confinement`
  - `Probation`
  - `IPP` (Intermediate Punishment Program)
  - `ARD` (Accelerated Rehabilitative Disposition)
  - `No Further Penalty`
  - `Fines and Costs`
- **Sentence Durations** (`min_days`, `max_days`): Minimum and maximum duration limits converted into days.
- **Min Assumed Flag** (`min_assumed`): Set to `true` when a flat sentence is converted (e.g. flat 3 months translates to min 90 days / max 90 days with `min_assumed = true`).
- **Sentence Program** (`program`): Named program requirements (e.g., DUI treatment).
- **Sentence Date** (`sentence_date`): The date the sentence was handed down.
- **Raw Text** (`raw_text`): The exact sentence conditions string parsed from the PDF.

---

## 4. Privacy Invariants & Anonymization

The application adheres to strict privacy rules defined in [CLAUDE.md](../CLAUDE.md) and implemented in [identity.py](../services/pipeline/src/pipeline/identity.py).

### Salted Defendant Hashing

- **The Rule**: Defendant names, dates of birth, or addresses are **never** written to database tables or logs.
- **The Method**:
  1. The parser transiently reads the defendant's full name and birth year from `DEFENDANT INFORMATION` or `CASE PARTICIPANTS`.
  2. It generates a cryptographic SHA-256 hash using a secret salt loaded from `DEFENDANT_HASH_SALT` in the environment.
  3. Only this `defendant_hash` is stored in `parsed.dockets`. This allows data aggregation by unique individual (recidivism statistics) without leaking the actual identities of the individuals.

### Leak Guard & Privacy Sentinels

- **The Rule**: No identifying text must leak into error/warning tables or unstructured notes columns.
- **The Method**:
  - During parsing, the names and birth date are stored in memory as a set of **privacy sentinels**.
  - The check function `parse_docket_checked` (defined in [docket_parser.py](../services/pipeline/src/pipeline/docket_parser.py)) asserts that none of these sentinel values match or leak into any warnings, warnings metadata, or notes columns before the records are permitted to load.
