"""Docket-number-range enumeration (Task COL-1, decision 5).

Coverage is expressed as a docket-number range: court + year + start sequence
+ count, each number formatted ``MC-51-CR-#######-YYYY`` with a 7-digit
zero-padded sequence. Every attempted number is a coverage data point, so
enumeration is deterministic and gap-free over the requested range.

Only Philadelphia Municipal Court criminal dockets (``MC-51-CR``) are in scope
for this task; CP ranges are explicitly out of scope, so ``COURT_PREFIXES``
carries the single supported prefix and any other court is rejected.
"""

from __future__ import annotations

# Court code -> full docket prefix. Philadelphia county is 51, criminal type
# is CR. Kept as an explicit table so an out-of-scope court fails loudly
# rather than silently formatting a wrong prefix.
COURT_PREFIXES = {"MC": "MC-51-CR"}

# A 7-digit zero-padded sequence tops out at this value.
_MAX_SEQUENCE = 9_999_999


def format_docket(court: str, year: int, seq: int) -> str:
    """Format one docket number as ``MC-51-CR-#######-YYYY``.

    Raises ``ValueError`` for an unsupported court or an out-of-range sequence
    (sequences are 1-based and must fit the 7-digit field).
    """
    try:
        prefix = COURT_PREFIXES[court]
    except KeyError:
        supported = ", ".join(sorted(COURT_PREFIXES))
        raise ValueError(
            f"unsupported court {court!r}; supported: {supported}"
        ) from None
    if not 1 <= seq <= _MAX_SEQUENCE:
        raise ValueError(f"sequence {seq} out of range 1..{_MAX_SEQUENCE}")
    return f"{prefix}-{seq:07d}-{year:04d}"


def docket_range(court: str, year: int, start_seq: int, count: int) -> list[str]:
    """Return ``count`` consecutive docket numbers from ``start_seq`` upward.

    Raises ``ValueError`` on a non-positive start/count or if the range would
    overflow the 7-digit sequence field.
    """
    if start_seq < 1:
        raise ValueError(f"start_seq must be >= 1, got {start_seq}")
    if count < 1:
        raise ValueError(f"count must be >= 1, got {count}")
    end_seq = start_seq + count - 1
    if end_seq > _MAX_SEQUENCE:
        raise ValueError(
            f"range {start_seq}..{end_seq} overflows 7-digit sequence field"
        )
    return [format_docket(court, year, seq) for seq in range(start_seq, end_seq + 1)]
