"""Docket parser — ported from Capstone (17.2), hardened in 18.2 and 18.3.

This began as a behavior-preserving PORT (Task 17.2). Task 18.2 landed the first
targeted hardening changes: a junk-judge guard (Item 1), a disposition line-wrap
capture fix (Item 2), and an amended/downgraded/replaced charge warning signal
(Item 3). Task 18.3 adds held-case ``event_date``/``event_name`` capture on
non-terminal charges, a ``min_assumed`` annotation on filled sentence bounds, and
a third-party name guard that nulls-and-flags a judge capture colliding with an
identifying sentinel (SENTINEL_COLLISION). Output VALUES deliberately diverge
from the Capstone baseline for the hardened cases, and 18.3 adds two conditional
record fields (``event_date``/``event_name`` on non-terminal charges,
``min_assumed`` on filled sentences) — the first record-SCHEMA change since the
port, so the record's internal ``parser_version`` is 2. Task 32.2 moves
``disposition_date`` to the Final Disposition EVENT-line date (the judge-line
date is the sheet's Sentence Date column and now feeds sentence components
only, except under an ARD-routed Not-Final event) and drops seq-99,999
placeholder rows in the CHARGES section — parse-behavior changes, no schema
change (envelope 5 -> 6, record ``parser_version`` stays 2). See
tasks/worklog.md for the defect inventory and the declared per-task delta
classes.

The hardening items emit structural-only warnings (18.1 vocabulary; 18.3 adds
SENTINEL_COLLISION with plan approval) surfaced as the third element of
``parse_docket_text``'s return tuple; they NEVER carry docket text.

Pure stdlib only: no pdfplumber import anywhere in this module's path. The
PDF-opening wrapper ``parse_docket`` lives in ``docket_parser_pdf``. The
identifying-string hash and the two privacy assertions come from the 16.1
ported ``pipeline.identity`` surface; the small parse helpers come from
``pipeline.helpers``. The salt is supplied by the caller (severed config).
"""

from __future__ import annotations

import re
from datetime import datetime

from pipeline.helpers import GRADES, ParseError, parse_date, to_days
from pipeline.identity import (
    assert_no_leak,
    assert_related_cases_clean,
    collides_with_sentinels,
    hash_defendant,
)

# 32.2: the held-form vocabulary is the 29.3 SINGLE authority — imported, never
# re-listed (F2 discipline). ``outcome_mapper`` is pure (stdlib only), so this
# import adds no DB or pdfplumber path to the parser.
from pipeline.normalization.outcome_mapper import HELD_FOR_COURT_DISPOSITIONS
from pipeline.warning_codes import (
    SENTINEL_COLLISION,
    SUSPECT_JUDGE_LINE,
    SUSPECTED_AMENDED_CHARGE,
    UNKNOWN_NOT_FINAL_DISPOSITION,
    make_warning,
)

HEADERS = [
    "CASE INFORMATION",
    "RELATED CASES",
    "STATUS INFORMATION",
    "CALENDAR EVENTS",
    "DEFENDANT INFORMATION",
    "CASE PARTICIPANTS",
    "BAIL INFORMATION",
    "CHARGES",
    "DISPOSITION SENTENCING/PENALTIES",
    "COMMONWEALTH INFORMATION",
    "ATTORNEY INFORMATION",
    "CASE FINANCIAL INFORMATION",
    "ENTRIES",
]

# Sections recognized so their lines stop folding into a neighbor, but whose
# content is not turned into output fields (Phase 7, MC sheets). CASE
# PARTICIPANTS is still scanned for the transient defendant name used only to
# build the hash; nothing from these sections lands in the record.
SKIP_SECTIONS = {
    "CASE PARTICIPANTS",
    "BAIL INFORMATION",
    "CASE FINANCIAL INFORMATION",
}

# The defendant name (transient, hash only) prints under CASE PARTICIPANTS on
# MC sheets and, on CP sheets, under a CASE PARTICIPANTS subheader that used to
# fold into DEFENDANT INFORMATION. Search both so the hash basis is unchanged
# now that CASE PARTICIPANTS is its own section.
NAME_SECTIONS = ("DEFENDANT INFORMATION", "CASE PARTICIPANTS")

DISPO_SKIP_HEADERS = {
    "DISPOSITION SENTENCING/PENALTIES",
    "Disposition",
    "Case Event Disposition Date Final Disposition",
    "Sequence/Description Offense Disposition Grade Section",
    "Sentencing Judge Sentence Date Credit For Time Served",
    "Sentence/Diversion Program Type Incarceration/Diversionary Period Start Date",
    "Sentence Conditions",
}


# --- Item 1: junk judge guard (Task 18.2) -----------------------------------
# A judge slot sometimes captures a sentence fragment instead of a name (the
# Capstone artifact). This guard rejects captures matching sentence-component
# patterns. It performs NO judge-identity or name-shape validation ("is this
# value actually a judge" is Sprint 5 normalization). Scope is settled and must
# not expand: the sentence-component keywords (Confinement / Probation / IPP),
# the Min/Max-of slot, duration expressions (number + day/month/year unit), and
# currency amounts. ARD / No Further Penalty / Fines and Costs are deliberately
# excluded because "Ard" is a name-shaped surname.
_JUNK_JUDGE_PATTERNS = (
    re.compile(r"\b(?:Confinement|Probation|IPP)\b", re.IGNORECASE),
    re.compile(r"\b(?:Min|Max)\s+of\b", re.IGNORECASE),
    re.compile(
        r"\b\d+(?:\.\d+)?\s*(?:½|1/2)?\s*(?:years?|months?|days?)\b", re.IGNORECASE
    ),
    re.compile(r"\$|\b\d[\d,]*\.\d{2}\b"),
)


def _is_junk_judge(value: str) -> bool:
    """True if a judge-slot capture matches a sentence-component pattern.

    Sentence-component keyword, Min/Max-of slot, duration expression, or currency
    amount => reject. No name-shape validation (Sprint 5). Empty or name-shaped
    values (including comma-formatted and initialed forms) return False and are
    captured unchanged.
    """
    return any(pattern.search(value) for pattern in _JUNK_JUDGE_PATTERNS)


# --- Item 2: known-truncated disposition repair (Task 18.2) ------------------
# A disposition that wraps across two physical lines is captured truncated. The
# 18.2 corpus rerun proved the continuation line cannot be read safely: the
# disposition column and the re-printed charge-description column wrap together
# and interleave with section-header furniture, so a prose gate swallows
# charge-name wraps and furniture (~535 false positives). The Capstone
# fall-through drop is CORRECT for those lines.
#
# Instead this repairs the truncated CAPTURE deterministically, reading no
# continuation line: each key below is a complete, unambiguous disposition prefix
# that wraps to a known single full form and is never itself a complete
# disposition, so an exact-match truncated capture is rewritten to its full
# string — immune to charge-description wraps and furniture by construction.
# Corpus-evidenced only (the 18.2 rerun's sole true-positive class was exactly
# "Transferred to Another"); grow this table only with the same evidence and the
# same exact-match discipline. Any other truncated disposition is left to the
# downstream map (false-negative bias, deliberate).
_TRUNCATED_DISPOSITION_REPAIRS = {
    "Transferred to Another": "Transferred to Another Jurisdiction",
}


# --- Item 3: amended/downgraded/replaced charge signal (Task 18.2) ----------
# Warning-only: scans the already-parsed disposition_raw for renderings that
# suggest a charge was amended, downgraded, or replaced. Zero parsed-field
# change; charges are never merged, collapsed, or re-keyed. The pattern basis is
# SPECULATIVE-CONSERVATIVE, not documented — it is not backed by a cited CPCMS
# document nor by a corpus observation the agent can read. The patterns are
# retained because the signal is warning-only, zero-field-change, and
# false-positive-improbable inside a disposition_raw value; the completion
# report records the real per-pattern corpus hit counts so the basis becomes
# actual data. False negatives are acceptable; false positives on ordinary
# dockets are a stop-and-report.
_AMENDED_CHARGE_PATTERNS = (
    re.compile(r"\bamended\b", re.IGNORECASE),
    re.compile(r"\bdowngraded\b", re.IGNORECASE),
    re.compile(r"\breplaced\s+by\b", re.IGNORECASE),
    re.compile(r"\bcharge\s+changed\b", re.IGNORECASE),
)


def _matches_amended_charge(disposition_raw: str) -> bool:
    """True if a parsed disposition_raw suggests an amended/downgraded/replaced
    charge. Reads a parsed field only — never page text — so it cannot change any
    parsed value."""
    return any(pattern.search(disposition_raw) for pattern in _AMENDED_CHARGE_PATTERNS)


# --- 18.5: event-grain disposition routing vocabulary -----------------------
# Capstone routed at the EVENT level: a Not-Final event whose case-status row
# contained "ard" disposed EVERY charge line under it, each with its own token.
# 18.4 corrected event_name off the status row, which severed that accidental
# ARD routing (65+ charges lost genuine ARD dispositions). 18.5 restores it
# decoupled from event_name and the status row: a Not-Final event routes iff its
# FIRST charge line's disposition token is in ARD_CLASS_DISPOSITIONS, and a
# routed event disposes ALL its charge lines (each with its own token as
# disposition_raw). Final Disposition events route as always. Latest-valid-event
# -wins is unchanged. Both sets are CPCMS court vocabulary — exact-match only,
# 18.2 repair-table discipline — enumerated from the 1,596-doc corpus scan
# (scripts/scan_disposition_tokens.py); grow only with the same evidence.
#
# ARD_CLASS: the disposition that MUST route under a Not-Final event (a Final
# event on the same docket cannot reproduce it). Corpus counts (distinct charges
# / occurrences): "ARD - County" 65 charges / 94 occ; "RD - County" 1 / 1 — a
# corpus-evidenced strip fragment of "ARD - County" (the DISPOSITION section
# reprints a shorter offense than CHARGES, so the longest-prefix strip eats the
# leading "A"); it is a genuine must-route ARD charge, kept as an exact fragment
# form (never a repair, since the baseline carries the fragment too).
ARD_CLASS_DISPOSITIONS = frozenset(
    {
        "ARD - County",
        "RD - County",
    }
)

# NON_TERMINAL: every other charge-line token observed under a Not-Final event —
# these NEVER trigger routing (a first-line NON_TERMINAL token leaves the event
# held). Pinned VERBATIM from the corpus scan, including strip fragments
# ("ceed/oceed/roceed to Court", "Proceed to Court (ARD", "Proceed to Ct (Nolle
# Prossed") and verbose un-stripped tokens (DUI:* / Permitting*), so that
# UNKNOWN_NOT_FINAL_DISPOSITION warns only on genuinely novel vocabulary. Note
# "Withdrawn" and the wrap token are deliberately absent from ARD_CLASS: they
# only ever dispose as COMPANION (non-first) lines under an already-routed ARD
# event, so event-grain reproduces them without their being routing triggers.
NON_TERMINAL_DISPOSITIONS = frozenset(
    {
        "ARD - County Open",
        "Added by Information",
        "DUI: High Rte of Alc (Bac.10 - <.16) 1st Off Held for Court M 75 § 3802 §§ B*",  # noqa: E501
        "DUI: High Rte of Alc (Bac.10 - <.16) 1st Off Proceed to Court M 75 § 3802 §§ B*",  # noqa: E501
        "DUI: Highest Rte of Alc (BAC .16+) 1st Off Held for Court M 75 § 3802 §§ C*",  # noqa: E501
        "DUI: Highest Rte of Alc (BAC .16+) 1st Off Proceed to Court M 75 § 3802 §§ C*",  # noqa: E501
        "Dismissed - LOE",
        "Dismissed - Rule 600 (Speedy",
        "Guilty",
        "Guilty Plea - Negotiated",
        "Guilty Plea - Non-Negotiated",
        "HP - Held for Court",
        "Held for Court",
        "Held for Court IC",
        "IGJ - Held for Court",
        "Mistrial - Hung Jury",
        "Nolle Prossed",
        "Nolo Contendere",
        "Permitting Violation - Accident Involving Damage Held for Court S 75 § 3743 §§ A-P",  # noqa: E501
        "Permitting Violation - Accident Involving Damage Proceed to Court S 75 § 3743 §§ A-P",  # noqa: E501
        "Proceed to Court",
        "Proceed to Court (ARD",
        "Proceed to Court (Complaint",
        "Proceed to Court (Conviction",
        "Proceed to Court (GP",
        "Proceed to Court (Mistrial)",
        "Proceed to Court (Program",
        "Proceed to Court IC",
        "Proceed to Ct (Nolle Prossed",
        "Quashed",
        "Replacement by Information",
        "Rule 546 - Open",
        "Rule 586 - Open",
        "ceed to Court",
        "oceed to Court",
        "roceed to Court",
    }
)


def _charge_line_token(charge: dict | None, text: str) -> str:
    """The charge-line disposition token: ``text`` minus offense/statute/grade.

    Same strip the disposition loop has always used (longest offense prefix off
    the front, then statute and grade off the tail), factored so event-grain
    routing can inspect the token BEFORE deciding whether the charge routes.
    ``charge`` is the CHARGES-section record for this sequence; ``None`` (an
    unknown sequence — should not occur under a real event) yields ``""``.
    """
    if charge is None:
        return ""
    offense = charge["offense"] or ""
    matched_prefix = ""
    for i in range(len(offense), 0, -1):
        prefix = offense[:i].strip()
        if text.startswith(prefix):
            matched_prefix = prefix
            break
    remaining = text[len(matched_prefix) :].strip()

    statute = charge["statute"] or ""
    if statute and remaining.endswith(statute):
        remaining = remaining[: -len(statute)].strip()
    grade = charge["grade"] or ""
    if grade and remaining.endswith(grade):
        remaining = remaining[: -len(grade)].strip()
    return remaining


def is_statute_token(tok: str) -> bool:
    tok_clean = tok.strip()
    if not tok_clean:
        return True
    if "§" in tok_clean:
        return True
    # Contains a digit
    if re.search(r"\d", tok_clean):
        return True
    # Length 1 (e.g. single letters like A, or symbols like -)
    if len(tok_clean) == 1:
        return True
    # Roman numerals (case-insensitive)
    if tok_clean.lower() in (
        "i",
        "ii",
        "iii",
        "iv",
        "v",
        "vi",
        "vii",
        "viii",
        "ix",
        "x",
    ):
        return True
    # Check for parenthesized subsections like (a), (1)
    if tok_clean.startswith("(") and tok_clean.endswith(")"):
        return True
    return False


# A related-cases row carries a Caption column with third-party names. It is
# never captured. Every field below is pulled from a bounded pattern (a docket
# regex, the court from the docket prefix, an association reason from a fixed
# vocabulary), so the free-text caption cannot leak by construction.
RELATED_DOCKET_RE = re.compile(r"(?:CP|MC)-\d{2}-[A-Z]{2}-\d{7}-\d{4}")

# Association reason is the last column of a related-cases row, but the value
# is a controlled CPCMS phrase that usually renders on its own wrapped line as
# a grouping heading above the docket rows it covers. Reasons are matched ONLY
# against this fixed vocabulary (longest first), never against free text, so
# the caption column can never leak into the reason. A row with no controlled
# phrase in scope stores association_reason None. Verified against real MC
# sheets in Phase 7 stage 2; extend here if a real sheet prints a new phrase.
ASSOCIATION_REASONS = [
    "Consolidated Defendant Cases Number and Primary Participant",
    "Joined Codefendant Cases Number and Different Primary Participant",
    "Consolidated Defendant Cases",
    "Joined Codefendant Cases",
    "Refiled",
    "Related",
    "Consolidated",
    "Joined",
]


def match_association_reason(line_str: str) -> str | None:
    """Return the controlled association-reason phrase present in the line, or
    None. Controlled vocabulary only, so caption text is never returned."""
    for phrase in ASSOCIATION_REASONS:
        if phrase in line_str:
            return phrase
    return None


def parse_related_cases(lines: list[str]) -> list[dict]:
    """Parse RELATED CASES rows into docket number, court, association reason.

    The caption column (third-party names) is never read. Docket number comes
    from a bounded regex, court from the docket prefix, and association reason
    only from the controlled vocabulary (matched on the docket line or carried
    from the most recent grouping heading). No free text is ever captured.
    """
    entries: list[dict] = []
    current_reason: str | None = None
    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue
        heading = match_association_reason(line_str)
        m = RELATED_DOCKET_RE.search(line_str)
        if not m:
            # A standalone controlled phrase is a grouping heading; carry it to
            # the docket rows that follow.
            if heading:
                current_reason = heading
            continue
        docket = m.group(0)
        entries.append(
            {
                "docket_number": docket,
                "court": detect_court_type(docket),
                "association_reason": heading or current_reason,
            }
        )
    return entries


def detect_court_type(docket_number: str) -> str:
    """Court type from the docket-number prefix (Phase 7). The stem is
    authoritative and always present, so it is preferred over the banner text.
    MC-51 dockets are Municipal Court; everything else (CP-51) is Common Pleas.
    """
    if docket_number.startswith("MC-"):
        return "Municipal Court"
    return "Common Pleas"


def parse_docket_text(
    docket_number: str, pages_text: list[str], *, salt: str
) -> tuple[dict, list[str], list[dict[str, object]]]:
    """Parse already-extracted page text into the record, sentinels, warnings.

    Split out from parse_docket so the section logic can be exercised on
    synthetic text fixtures without a PDF. ``salt`` is caller-supplied and
    threaded straight to ``hash_defendant``; this module never reads the
    environment and does no salt validation of its own (hash_defendant's own
    required-salt check fires instead).

    The third return element is the list of structural-only parse-time warnings
    (18.2 Items 1 and 3: SUSPECT_JUDGE_LINE, SUSPECTED_AMENDED_CHARGE). Each is
    built via ``warning_codes.make_warning`` and carries only structural context
    (section name, charge sequence) — never docket text.
    """
    warnings: list[dict[str, object]] = []

    # Gather transient names from page headers (under "v.")
    v_names = set()
    raw_lines = []

    for text in pages_text:
        page_lines = text.splitlines()
        skip_next = False
        for i, line in enumerate(page_lines):  # noqa: B007 - faithful port; i unused
            line_str = line.strip()
            if skip_next:
                if line_str:
                    v_names.add(line_str)
                skip_next = False
                continue
            if line_str.lower() in ("v.", "v"):
                skip_next = True
                continue
            raw_lines.append(line)

    # Filter out header/footer lines and organize into sections
    sections = {h: [] for h in HEADERS}
    current_section = None

    for line in raw_lines:
        line_str = line.strip()
        if not line_str:
            continue

        # Skip page headers, footers, and disclaimers
        if line_str == "COURT OF COMMON PLEAS OF PHILADELPHIA COUNTY":
            continue
        if line_str == "MUNICIPAL COURT OF PHILADELPHIA COUNTY":
            continue
        if line_str == "DOCKET":
            continue
        if line_str.startswith("Docket Number:"):
            continue
        if line_str == "CRIMINAL DOCKET":
            continue
        if line_str == "Court Case":
            continue
        if line_str == "Commonwealth of Pennsylvania":
            continue
        if re.match(r"^Page \d+ of \d+$", line_str):
            continue
        if re.match(r"^CPCMS .* Printed:.*$", line_str, re.IGNORECASE):
            continue
        if "Recent entries made in the court" in line_str:
            continue
        if "Neither the courts of the Unified Judicial" in line_str:
            continue
        if "System of the Commonwealth of Pennsylvania" in line_str:
            continue
        if "data, errors or omissions on these reports" in line_str:
            continue
        if "only be provided by the Pennsylvania State Police" in line_str:
            continue
        if "Moreover an employer who does not comply" in line_str:
            continue
        if "Information Act may be subject to civil liability" in line_str:
            continue

        if line_str in HEADERS:
            current_section = line_str
        elif current_section is not None:
            sections[current_section].append(line)

    # Extract Defendant Name and Date of Birth
    defendant_name = None
    dob_str = None

    # Transient name and DOB source lines, in section order. CASE PARTICIPANTS
    # is now its own section; on CP sheets the "Defendant" name line lives
    # there, so scanning both keeps the first-match (and thus the hash) exactly
    # as it was when CASE PARTICIPANTS folded into DEFENDANT INFORMATION.
    name_source_lines: list[str] = []
    for header in NAME_SECTIONS:
        name_source_lines.extend(sections.get(header, []))

    # Find DOB
    for line in name_source_lines:
        if "Date Of Birth:" in line or "Date of Birth:" in line:
            m_dob = re.search(r"Date\s+of\s+Birth:\s*([\d/]+)", line, re.IGNORECASE)
            if m_dob:
                dob_str = m_dob.group(1).strip()
                break

    # Find Defendant Name
    for line in name_source_lines:
        m_def = re.match(r"^Defendant\s+(.*)$", line.strip())
        if m_def:
            defendant_name = m_def.group(1).strip()
            break

    # Fallback to v_names if defendant_name is not in CASE PARTICIPANTS
    if not defendant_name and v_names:
        defendant_name = sorted(list(v_names))[0]

    if not defendant_name or not dob_str:
        raise ParseError("Missing defendant name or date of birth")

    try:
        birth_year = int(dob_str.split("/")[-1])
    except Exception as exc:
        raise ParseError("Invalid date of birth format") from exc

    defendant_hash = hash_defendant(defendant_name, birth_year, salt=salt)

    # Compile privacy sentinels
    sentinels = [dob_str, defendant_name]
    for part in re.split(r"[^a-zA-Z]", defendant_name):
        if len(part) >= 3:
            sentinels.append(part)
    for name in v_names:
        sentinels.append(name)
        for part in re.split(r"[^a-zA-Z]", name):
            if len(part) >= 3:
                sentinels.append(part)
    sentinels = sorted(list(set(sentinels)))

    # Parse Case status
    case_status = None
    for line in sections.get("STATUS INFORMATION", []):
        m = re.search(
            r"Case\s+Status:\s*(.*?)(?:\s+Status\s+Date|\s+Processing|\s+Arrest|$)",
            line,
            re.IGNORECASE,
        )
        if m:
            case_status = m.group(1).strip()
            break

    # Parse Case Filed Date, Assigned Judge, OTN, Cross Court Docket Nos
    filed_date = None
    assigned_judge_raw = None
    otn = None
    cross_court_dockets = None
    for line in sections.get("CASE INFORMATION", []):
        if "Judge Assigned:" in line or "Date Filed:" in line:
            m_judge = re.search(
                r"Judge\s+Assigned:\s*(.*?)\s+Date\s+Filed:", line, re.IGNORECASE
            )
            if m_judge:
                candidate = m_judge.group(1).strip()
                # 18.2 Item 1 guard: a sentence fragment in the judge slot is
                # rejected (field left null). 18.3 third-party name guard: a
                # name-shaped capture that whole-token-collides with an
                # identifying sentinel is nulled and flagged SENTINEL_COLLISION
                # (the colliding value never passes through as a judge name).
                # Otherwise the name-shaped capture is kept as before. Only the
                # judge field is affected.
                if candidate and _is_junk_judge(candidate):
                    warnings.append(
                        make_warning(SUSPECT_JUDGE_LINE, section="CASE INFORMATION")
                    )
                elif candidate and collides_with_sentinels(candidate, sentinels):
                    warnings.append(
                        make_warning(SENTINEL_COLLISION, section="CASE INFORMATION")
                    )
                else:
                    assigned_judge_raw = candidate
            m_date = re.search(r"Date\s+Filed:\s*([\d/]+)", line, re.IGNORECASE)
            if m_date:
                filed_date = parse_date(m_date.group(1))
        if "OTN:" in line:
            m_otn = re.search(
                r"OTN:\s*([A-Za-z0-9\s-]+?)(?:\s+LOTN:|\s+Originating|$)",
                line,
                re.IGNORECASE,
            )
            if m_otn:
                otn = m_otn.group(1).strip()
        # Cross Court Docket Nos: the held-to-CP and de-novo linkage. Raw
        # string as printed (docket numbers only; no caption). Captured to the
        # end of the line; null when the label is absent.
        if "Cross Court Docket Nos:" in line:
            m_ccd = re.search(
                r"Cross\s+Court\s+Docket\s+Nos:\s*(.*)$", line, re.IGNORECASE
            )
            if m_ccd:
                val = m_ccd.group(1).strip()
                cross_court_dockets = val if val else None

    # Parse Charges
    parsed_charges = {}
    active_charge = None
    # 32.2 seq-99,999 guard state: True while inside a CPCMS placeholder charge
    # row (printed sequence literal "99,999"), so the row AND its wrapped
    # continuation lines are dropped instead of appending to the last real
    # charge's offense (the C4 leak). Reset by the next real charge row.
    in_placeholder_charge = False

    for line in sections.get("CHARGES", []):
        line_str = line.strip()
        if not line_str:
            continue
        if "Seq." in line_str and "Statute" in line_str:
            continue

        # 32.2 seq-99,999 guard: trailing placeholder rows print the literal
        # sequence "99,999" (comma included), which the real-sequence regex
        # below rejects — so their text used to fall into the offense-
        # continuation append. Byte-exact prefix match on the printed literal
        # plus its following space (18.2 exact-match discipline; false-negative
        # bias — any other placeholder rendering is left alone and surfaces in
        # corpus review, never guessed at).
        if line_str.startswith("99,999 "):
            in_placeholder_charge = True
            continue

        m_seq = re.match(r"^(\d+)\s+(\d+)\s+(.*)$", line_str)
        if m_seq:
            in_placeholder_charge = False
            seq = int(m_seq.group(1))
            rest = m_seq.group(3).strip()

            tokens = rest.split()
            if not tokens:
                continue

            grade = None
            if tokens[0] in GRADES:
                grade = tokens[0]
                tokens = tokens[1:]

            # Indirect Criminal contempt rows lead with an "IC" filing marker
            # in front of the statute. Drop it so statute detection starts at
            # the real statute instead of stopping on a non-statute token.
            if tokens and tokens[0] == "IC":
                tokens = tokens[1:]

            date_idx = -1
            for idx in range(len(tokens) - 1, -1, -1):
                if re.match(r"^\d{2}/\d{2}/\d{4}$", tokens[idx]):
                    date_idx = idx
                    break

            offense_date = None
            otn_val = None
            statute_tokens = []
            offense_tokens = []

            if date_idx != -1:
                offense_date = parse_date(tokens[date_idx])  # noqa: F841 - faithful port; computed, unused
                if date_idx + 1 < len(tokens):
                    otn_val = " ".join(tokens[date_idx + 1 :])  # noqa: F841 - faithful port; computed, unused
                left_tokens = tokens[:date_idx]

                first_offense_idx = len(left_tokens)
                for idx, tok in enumerate(left_tokens):
                    if not is_statute_token(tok):
                        first_offense_idx = idx
                        break
                statute_tokens = left_tokens[:first_offense_idx]
                offense_tokens = left_tokens[first_offense_idx:]
            else:
                first_offense_idx = len(tokens)
                for idx, tok in enumerate(tokens):
                    if not is_statute_token(tok):
                        first_offense_idx = idx
                        break
                statute_tokens = tokens[:first_offense_idx]
                offense_tokens = tokens[first_offense_idx:]

            statute_str = " ".join(statute_tokens)
            offense_str = " ".join(offense_tokens)

            active_charge = {
                "sequence": seq,
                "statute": statute_str if statute_str else None,
                "grade": grade,
                "offense": offense_str if offense_str else None,
                "disposition_raw": None,
                "disposition_date": None,
                "disposition_judge_raw": None,
                "sentences": [],
            }
            parsed_charges[seq] = active_charge
        else:
            # A void placeholder charge ("0 § 0 Unknown Statute ...") can trail
            # a real charge on a line the sequence regex rejects (comma in the
            # OTN). Drop it so it never pollutes the prior charge's offense.
            if "Unknown Statute" in line_str:
                continue
            # 32.2: a wrapped continuation line of a dropped 99,999 placeholder
            # row belongs to that row, not to the last real charge (observed on
            # the N4-03 audit sheet) — drop it with its parent.
            if in_placeholder_charge:
                continue
            if active_charge:
                if active_charge["offense"]:
                    active_charge["offense"] = active_charge["offense"] + " " + line_str
                else:
                    active_charge["offense"] = line_str

    # Parse Dispositions and Sentences
    current_charge_seq = None
    expecting_judge_line = False
    current_sentence_comp = None
    # 18.5 event-grain routing state. ``in_valid_event`` is tri-state:
    #   True  -> the current event routes (a Final Disposition event, or a
    #            Not-Final event whose FIRST charge line's token was ARD_CLASS);
    #   False -> the current event does not route (held);
    #   None  -> inside a Not-Final event whose first charge line has not yet been
    #            seen — the routing decision point.
    # ``in_not_final_event`` distinguishes an unrouted Not-Final event (record held
    # event keys; guard stranded ARD tokens) from a Final event and the pre-event
    # start.
    in_valid_event: bool | None = False
    in_not_final_event = False
    current_event_name = ""
    current_event_date = None
    # 32.2: the judge-line date is the sheet's "Sentence Date" column, kept in
    # this parse-local transient (keyed by charge sequence) as the sentence-
    # component date source. It is written at exactly the same stream events
    # that used to write disposition_date, so component dates are byte-
    # identical to pre-32.2 behavior (Option B, D-C hard zero).
    judge_line_dates: dict[int, object] = {}

    def save_current_sentence():
        nonlocal current_sentence_comp
        if current_sentence_comp and current_charge_seq is not None:
            raw_text = ", ".join(current_sentence_comp["raw_text_parts"])

            min_days = None
            max_days = None
            # 18.3 Item 2 annotation: min_assumed is True when min_days was FILLED
            # from the maximum or from a flat value (min was not itself parsed).
            # It is False when min_days was parsed directly (max may be filled from
            # min) or when both bounds parsed. Parsed values are unchanged — this
            # is a pure annotation, no warning, no review_needed impact.
            min_assumed = False
            type_lower = current_sentence_comp["sentence_type"].lower()

            if type_lower not in ("no further penalty", "fines and costs"):
                min_match = re.search(
                    r"Min of\s+(.*?)(?:Max of|$|,)", raw_text, re.IGNORECASE
                )
                max_match = re.search(
                    r"Max of\s+(.*?)(?:Min of|$|,)", raw_text, re.IGNORECASE
                )

                if min_match:
                    min_days = to_days(min_match.group(1).replace(".00", ""))
                if max_match:
                    max_days = to_days(max_match.group(1).replace(".00", ""))

                if min_days is None and max_days is None:
                    flat_days = to_days(raw_text.replace(".00", ""))
                    if flat_days is not None:
                        min_days = flat_days
                        max_days = flat_days
                        min_assumed = True
                elif min_days is None and max_days is not None:
                    min_days = max_days
                    min_assumed = True
                elif max_days is None and min_days is not None:
                    max_days = min_days

            sentence: dict[str, object] = {
                "sentence_type": current_sentence_comp["sentence_type"],
                "min_days": min_days,
                "max_days": max_days,
                "program": current_sentence_comp["program"],
                "sentence_date": current_sentence_comp["sentence_date"],
                "raw_text": raw_text,
            }
            # Added only when True (absent otherwise) so unaffected sentences stay
            # byte-identical to the Capstone baseline; each occurrence is one
            # declared "min_assumed addition" delta.
            if min_assumed:
                sentence["min_assumed"] = True
            parsed_charges[current_charge_seq]["sentences"].append(sentence)
            current_sentence_comp = None

    disposition_lines = sections.get("DISPOSITION SENTENCING/PENALTIES", [])
    for line in disposition_lines:
        line_str = line.strip()
        if not line_str:
            continue

        if line_str in DISPO_SKIP_HEADERS:
            continue

        # Event header (single-line, canonical CPCMS layout):
        #   "<EventName> <MM/DD/YYYY> <Not Final|Final Disposition>"
        # 18.4 replaced the previous two-line assumption (event name on its own
        # line, then the date at column 0 of the following anchor line). A corpus
        # scan found the date immediately left of the status token on 3,278/3,278
        # anchor lines and at line start on 0 of them, so single-line is canonical
        # and two-line handling is retired (a future real specimen would return it
        # as its own task). line_str is already .strip()ed above, so the "$" anchor
        # tolerates trailing whitespace in the source line.
        event_match = re.search(
            r"(\d{2}/\d{2}/\d{4})\s+(?:Final Disposition|Not Final)$", line_str
        )
        if event_match:
            save_current_sentence()
            current_charge_seq = None
            # event_date is the date token immediately preceding the status token;
            # event_name is the leading text before that date on the same line.
            current_event_date = parse_date(event_match.group(1))
            current_event_name = line_str[: event_match.start()].strip()
            # 18.5: routing is decided by the charge-line disposition TOKEN, not by
            # event_name (the 18.4 regression came from the retired
            # ``"ard" in event_name`` special case). A Final event always routes; a
            # Not-Final event defers its decision to its first charge line.
            if line_str.endswith("Final Disposition"):
                in_valid_event = True
                in_not_final_event = False
            else:
                in_valid_event = None
                in_not_final_event = True
            continue

        charge_match = re.match(r"^(\d+)\s*/\s*(.*)$", line_str)
        if charge_match:
            save_current_sentence()
            seq = int(charge_match.group(1))
            text = charge_match.group(2).strip()
            token = _charge_line_token(parsed_charges.get(seq), text)

            # 18.5 event-grain routing decision, made at the FIRST charge line of a
            # Not-Final event: the event routes iff that token is ARD_CLASS. A
            # non-empty first-line token in NEITHER frozenset is novel vocabulary at
            # the decision point — the event stays held and the charge is flagged.
            if in_valid_event is None:
                if token in ARD_CLASS_DISPOSITIONS:
                    in_valid_event = True
                else:
                    in_valid_event = False
                    if token and token not in NON_TERMINAL_DISPOSITIONS:
                        warnings.append(
                            make_warning(
                                UNKNOWN_NOT_FINAL_DISPOSITION,
                                section="DISPOSITION SENTENCING/PENALTIES",
                                charge_sequence=seq,
                            )
                        )

            if not in_valid_event:
                # 18.3 Item 1: a non-terminal/held event. Record the event name
                # and event date on the charge (LATEST non-terminal event wins;
                # the placement sweep strips these from any charge later disposed,
                # so only a charge that ends the parse undisposed keeps them).
                # NON_TERMINAL_CASE is emitted by the envelope observation layer.
                if seq in parsed_charges:
                    parsed_charges[seq]["event_name"] = current_event_name
                    parsed_charges[seq]["event_date"] = current_event_date
                current_charge_seq = None
                # Non-ARD-first guard: an ARD_CLASS token stranded on a non-first
                # charge line of an UNROUTED Not-Final event is a potentially
                # un-routed genuine ARD disposition (corpus: 0/27 events today) —
                # surface it rather than let it vanish.
                if in_not_final_event and token in ARD_CLASS_DISPOSITIONS:
                    warnings.append(
                        make_warning(
                            UNKNOWN_NOT_FINAL_DISPOSITION,
                            section="DISPOSITION SENTENCING/PENALTIES",
                            charge_sequence=seq,
                        )
                    )
                continue

            # Routed event (Final, or ARD-triggered Not-Final): dispose THIS charge
            # line with its own token as disposition_raw — event grain. A later
            # valid event overwrites it (latest-valid-event-wins), and its judge /
            # sentence lines attach to this sequence below.
            current_charge_seq = seq
            expecting_judge_line = True
            if seq in parsed_charges:
                parsed_charges[seq]["disposition_raw"] = token if token else None
                # 32.2: the disposition date is the Final Disposition EVENT-line
                # date (already captured above), assigned here so the string and
                # the date always come from the SAME block. Guards: Final blocks
                # only (an ARD-routed Not-Final event keeps judge-line dating —
                # decision 4); a non-empty token only (a string-less row must
                # not become disposed-by-date — the date-without-string class is
                # empty and stays empty); a held-for-court form never dates
                # (requirement 4 — don't assign, NEVER clear; a dated held-form
                # row would be a STOP-class rerun finding, not a parser repair).
                if (
                    not in_not_final_event
                    and token
                    and token not in HELD_FOR_COURT_DISPOSITIONS
                ):
                    parsed_charges[seq]["disposition_date"] = current_event_date
            continue

        if current_charge_seq is not None and expecting_judge_line:
            if re.search(r"\d{2}/\d{2}/\d{4}$", line_str):
                judge_match = re.match(r"^(.*?)\s+(\d{2}/\d{2}/\d{4})$", line_str)
                if judge_match:
                    judge_name = judge_match.group(1).strip()
                    disp_date = parse_date(judge_match.group(2))
                    if current_charge_seq in parsed_charges:
                        # 18.2 Item 1 guard: reject a sentence fragment in the
                        # judge slot (leave disposition_judge_raw null). 18.3
                        # third-party name guard: a name-shaped capture that
                        # whole-token-collides with an identifying sentinel is
                        # nulled and flagged SENTINEL_COLLISION. Only the judge
                        # field is affected — the date on this line is still
                        # recorded and control flow is unchanged.
                        if _is_junk_judge(judge_name):
                            warnings.append(
                                make_warning(
                                    SUSPECT_JUDGE_LINE,
                                    section="DISPOSITION SENTENCING/PENALTIES",
                                    charge_sequence=current_charge_seq,
                                )
                            )
                        elif collides_with_sentinels(judge_name, sentinels):
                            warnings.append(
                                make_warning(
                                    SENTINEL_COLLISION,
                                    section="DISPOSITION SENTENCING/PENALTIES",
                                    charge_sequence=current_charge_seq,
                                )
                            )
                        else:
                            parsed_charges[current_charge_seq][
                                "disposition_judge_raw"
                            ] = judge_name
                        # 32.2: the judge-line date is the Sentence Date column.
                        # It always feeds the sentence-component transient; it
                        # supplies disposition_date ONLY under an ARD-routed
                        # Not-Final event (decision 4 carve-out — today's
                        # behavior, unchanged). Final blocks took the event-line
                        # date at the charge line above.
                        judge_line_dates[current_charge_seq] = disp_date
                        if in_not_final_event:
                            parsed_charges[current_charge_seq]["disposition_date"] = (
                                disp_date
                            )
                    expecting_judge_line = False
                    continue
            else:
                is_sent_type = False
                for stype in (
                    "Confinement",
                    "Probation",
                    "ARD",
                    "IPP",
                    "No Further Penalty",
                    "Fines and Costs",
                ):
                    if line_str.lower().startswith(stype.lower()):
                        is_sent_type = True
                        break
                if is_sent_type:
                    expecting_judge_line = False
                else:
                    continue

        if current_charge_seq is not None and not expecting_judge_line:
            matched_type = None
            for stype in (
                "Confinement",
                "Probation",
                "ARD",
                "IPP",
                "No Further Penalty",
                "Fines and Costs",
            ):
                if line_str.lower().startswith(stype.lower()):
                    matched_type = stype
                    break

            if matched_type:
                save_current_sentence()
                # 32.2: the component date comes from the judge-line transient
                # (the Sentence Date column), not from disposition_date — which
                # is now the event-line date. The transient holds exactly what
                # disposition_date held here pre-32.2, so component dates are
                # byte-identical (Option B).
                current_sentence_comp = {
                    "sentence_type": matched_type,
                    "program": line_str,
                    "sentence_date": judge_line_dates.get(current_charge_seq),
                    "raw_text_parts": [line_str],
                }
            elif current_sentence_comp:
                is_continuation = (
                    (
                        any(
                            u in line_str.lower() for u in ("year", "month", "day", "½")
                        )
                        and any(c.isdigit() for c in line_str)
                    )
                    or line_str.lower().startswith("min of")
                    or line_str.lower().startswith("max of")
                )

                if is_continuation:
                    current_sentence_comp["raw_text_parts"].append(line_str)
                else:
                    save_current_sentence()

    save_current_sentence()

    # Format charges as list
    charges_list = sorted(list(parsed_charges.values()), key=lambda x: x["sequence"])

    # 18.3 Item 1 placement invariant (Check-2 fix): event_date/event_name belong
    # ONLY to charges that end the parse undisposed. A charge listed under a
    # non-terminal event but LATER disposed under a terminal event transiently
    # accumulated the event keys on its sequence-keyed dict; strip them here so a
    # disposed charge carries no event keys and terminal output stays byte-
    # identical to the Capstone baseline. A final sweep is used because a charge's
    # disposed/undisposed status is only known once the whole disposition section
    # has been parsed. Held charges are untouched and keep the latest non-terminal
    # event's values.
    for charge in charges_list:
        disposed = (
            charge["disposition_raw"] is not None
            or charge["disposition_date"] is not None
            or charge["disposition_judge_raw"] is not None
        )
        if disposed:
            charge.pop("event_date", None)
            charge.pop("event_name", None)

    # District Control Number from the Case Local Number(s) table. Printed on
    # both CP and MC sheets; null when absent. Scanned across all sections
    # because the table folds into whatever section precedes it.
    dc_number = None
    for section_lines in sections.values():
        for line in section_lines:
            m_dc = re.match(r"^District Control Number\s+(\S+)", line.strip())
            if m_dc:
                dc_number = m_dc.group(1).strip()
                break
        if dc_number:
            break

    # Related cases (MC sheets only; CP sheets have no such section).
    related_cases = parse_related_cases(sections.get("RELATED CASES", []))

    # Item 2: repair a known-truncated disposition capture to its full string
    # (exact-match only; reads no continuation line). Runs before the Item 3 scan
    # so the amended check sees the final disposition_raw.
    for charge in charges_list:
        full = _TRUNCATED_DISPOSITION_REPAIRS.get(charge["disposition_raw"])
        if full is not None:
            charge["disposition_raw"] = full

    # Item 3: amended/downgraded/replaced charge signal. Warning-only; reads the
    # already-parsed disposition_raw and changes no field. Emitted in charge
    # sequence order for a stable warning list.
    for charge in charges_list:
        disposition_raw = charge["disposition_raw"]
        if disposition_raw and _matches_amended_charge(disposition_raw):
            warnings.append(
                make_warning(
                    SUSPECTED_AMENDED_CHARGE,
                    section="CHARGES",
                    charge_sequence=charge["sequence"],
                )
            )

    record = {
        "docket_number": docket_number,
        "parser_version": 2,
        "parsed_at": datetime.now().replace(microsecond=0).isoformat(),
        "case": {
            "county": "Philadelphia",
            "court_type": detect_court_type(docket_number),
            "case_status": case_status,
            "filed_date": filed_date,
            "otn": otn,
            "assigned_judge_raw": assigned_judge_raw,
            "dc_number": dc_number,
            "cross_court_dockets": cross_court_dockets,
            "defendant_hash": defendant_hash,
        },
        "charges": charges_list,
        "related_cases": related_cases,
        "notes": [],
    }

    return record, sentinels, warnings


def parse_docket_checked(
    docket_number: str, pages_text: list[str], *, salt: str
) -> tuple[dict, list[str], list[dict[str, object]]]:
    """Parse and run the privacy assertions at the Capstone post-parse boundary.

    Mirrors ``scripts/parse_fixtures.py`` lines 26-29 in Capstone (parse ->
    assert_no_leak -> assert_related_cases_clean), minus the file/DB IO that
    boundary carried. The assertions deliberately stay OUT of parse_docket_text
    so parse behavior is unchanged; this is the seam a writer (17.3 comparator,
    later loader) calls before persisting a record. Raises RuntimeError if an
    identifying string reached a value or a related-cases entry carries an
    unexpected field.
    """
    record, sentinels, warnings = parse_docket_text(
        docket_number, pages_text, salt=salt
    )
    assert_no_leak(sentinels, record)
    assert_related_cases_clean(record)
    return record, sentinels, warnings
