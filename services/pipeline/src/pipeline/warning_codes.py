"""Warning-code vocabulary, severity map, and review_needed derivation (Task 18.1).

This is the SINGLE source of truth for the parser/envelope warning vocabulary.
No other module defines warning strings; every emitter imports the codes from
here. The set is closed: the eleven codes below are the whole vocabulary, and a
test asserts emitted codes are a subset of them. Adding a code requires
plan-level approval — do not invent codes in code.

Warnings carry STRUCTURAL CONTEXT ONLY (decision 2): a code plus an optional
section name, charge sequence number, page number, or field name. They NEVER
carry raw docket text, defendant-related values, or captured spans. ``make_warning``
is the only constructor and, by accepting only those four optional fields, makes
a text-carrying warning unrepresentable by construction.

review_needed (decision 3) is a DERIVED BOOLEAN from the code->severity map
below — never a numeric score, never a 0.00-1.00 confidence. A code is either
``review`` (its presence flags the document for human review) or ``info`` (an
observation that does not, on its own, require review).

Severity map rationale:

- ``review`` — the extracted data may be wrong, incomplete, or a parse failure a
  human must adjudicate: LOW_TEXT_EXTRACTION (extraction may be incomplete),
  MISSING_CHARGE_SECTION and UNSUPPORTED_FORMAT (parse failures),
  MISSING_DISPOSITION_DATE (a disposed charge lacking its date suggests a parse
  miss), SUSPECT_JUDGE_LINE and SUSPECTED_AMENDED_CHARGE (18.2 hardening signals),
  SENTINEL_COLLISION (18.3 third-party name guard: a name-shaped judge capture
  collided with an identifying sentinel and was nulled — a human confirms the
  intended judge value), UNKNOWN_NOT_FINAL_DISPOSITION (18.5 event-grain routing:
  a Not-Final event's routing is decided by its FIRST charge line's disposition
  token; a first-line token in neither routing frozenset — or an ARD_CLASS token
  stranded on a non-first line of an UNROUTED event — is novel/unclassified
  vocabulary at the decision point and may be a genuinely un-routed disposition a
  human must adjudicate).
- ``info`` — a truthful observation that review cannot improve:
  UNPARSEABLE_DURATION (usually a legitimate non-numeric term such as "Life";
  raw_text is preserved), NON_TERMINAL_CASE (a held/non-terminal case legitimately
  has null disposition/sentence dates), and MISSING_SENTENCE_DATE. The last is
  ``info`` because an undated sentence fact is mechanically excluded by the Sprint 7
  date-range gate: review cannot recover a date the sheet does not print, so
  flagging it for review would create work that cannot change the outcome.
"""

from __future__ import annotations

from collections.abc import Iterable

# --- The eleven codes (locked; additions require plan approval) -------------
LOW_TEXT_EXTRACTION = "LOW_TEXT_EXTRACTION"
MISSING_CHARGE_SECTION = "MISSING_CHARGE_SECTION"
UNPARSEABLE_DURATION = "UNPARSEABLE_DURATION"
MISSING_DISPOSITION_DATE = "MISSING_DISPOSITION_DATE"
MISSING_SENTENCE_DATE = "MISSING_SENTENCE_DATE"
SUSPECT_JUDGE_LINE = "SUSPECT_JUDGE_LINE"
SUSPECTED_AMENDED_CHARGE = "SUSPECTED_AMENDED_CHARGE"
NON_TERMINAL_CASE = "NON_TERMINAL_CASE"
UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
SENTINEL_COLLISION = "SENTINEL_COLLISION"
# 18.5: novel/unclassified disposition token at an event-grain routing decision.
UNKNOWN_NOT_FINAL_DISPOSITION = "UNKNOWN_NOT_FINAL_DISPOSITION"

# Severity levels.
SEVERITY_REVIEW = "review"
SEVERITY_INFO = "info"

# Code -> severity. Every defined code appears exactly once (asserted by test).
SEVERITY: dict[str, str] = {
    LOW_TEXT_EXTRACTION: SEVERITY_REVIEW,
    MISSING_CHARGE_SECTION: SEVERITY_REVIEW,
    UNSUPPORTED_FORMAT: SEVERITY_REVIEW,
    MISSING_DISPOSITION_DATE: SEVERITY_REVIEW,
    SUSPECT_JUDGE_LINE: SEVERITY_REVIEW,
    SUSPECTED_AMENDED_CHARGE: SEVERITY_REVIEW,
    SENTINEL_COLLISION: SEVERITY_REVIEW,
    UNKNOWN_NOT_FINAL_DISPOSITION: SEVERITY_REVIEW,
    UNPARSEABLE_DURATION: SEVERITY_INFO,
    MISSING_SENTENCE_DATE: SEVERITY_INFO,
    NON_TERMINAL_CASE: SEVERITY_INFO,
}

# The closed vocabulary: the whole set of legal warning codes.
WARNING_CODES: frozenset[str] = frozenset(SEVERITY)

# The only structural fields a warning may carry (decision 2). Anything outside
# this set — and any free text — is unrepresentable through ``make_warning``.
_WARNING_CONTEXT_FIELDS = ("section", "charge_sequence", "page", "field")


def make_warning(
    code: str,
    *,
    section: str | None = None,
    charge_sequence: int | None = None,
    page: int | None = None,
    field: str | None = None,
) -> dict[str, object]:
    """Build a structural-only warning dict.

    ``code`` must be one of the defined codes. Only the four optional structural
    fields are accepted, and only the non-None ones are included, so a warning
    can never carry raw docket text, a defendant value, or a captured span.
    """
    if code not in WARNING_CODES:
        raise ValueError(f"unknown warning code: {code!r}")
    warning: dict[str, object] = {"code": code}
    if section is not None:
        warning["section"] = section
    if charge_sequence is not None:
        warning["charge_sequence"] = charge_sequence
    if page is not None:
        warning["page"] = page
    if field is not None:
        warning["field"] = field
    return warning


def derive_review_needed(codes: Iterable[str]) -> bool:
    """True iff any code has ``review`` severity.

    ``codes`` is the flat list of codes in play for one document (its warning
    codes plus, on a failed envelope, the error code — both drawn from this same
    vocabulary). An unknown code raises rather than being silently ignored.
    """
    result = False
    for code in codes:
        if code not in SEVERITY:
            raise ValueError(f"unknown warning code: {code!r}")
        if SEVERITY[code] == SEVERITY_REVIEW:
            result = True
    return result
