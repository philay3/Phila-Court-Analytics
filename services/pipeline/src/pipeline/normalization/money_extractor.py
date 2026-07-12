"""Monetary amount extraction (Task 22.5).

The FIRST real consumer of the 22.1 money model
(:class:`~pipeline.normalization.models.MoneyExtractionResult`). Pure and DB-free:
one function, :func:`extract_amount`, turns a sentence component's ``raw_text``
into an integer-cents amount (or leaves it unset with a warning). No re-parsing of
durations, no DB, no float arithmetic — integer cents only.

``$``-REQUIRED regex (LOCKED at the 22.5 map gate)
--------------------------------------------------
Part A recon proved the ``$``-optional candidate matched sentence DURATION figures
("11.00 months", "23.00 months") en masse — of corpus components carrying a `.NN`
decimal, ~all were duration-adjacent and only ~5 corpus-wide were not. So a money
token MUST carry a ``$``; durations never do. :data:`MONEY_TOKEN` is that locked
regex and is the ONE money-regex definition project-wide (the recon/coverage tool
imports it from here).

Four-branch triage (option (b), LOCKED)
---------------------------------------
Over the DISTINCT ``$``-amounts in ``raw_text`` (distinct-by-value: the same amount
written twice is ONE amount — never sum, never take-max):

1. **no ``$`` at all** -> ``amount_cents`` unset, NO warning (amount legitimately
   absent; e.g. a bare "Fines and Costs" line). The caller emits no money item.
2. **``$`` present but 0 parseable amounts** -> ``amount_cents`` unset +
   ``NORM_UNPARSEABLE_AMOUNT`` (money present but unreadable). Caller emits a
   ``money_unparseable`` item.
3. **exactly one distinct amount** -> ``amount_cents`` SET, no warning.
4. **two or more distinct amounts** -> ``amount_cents`` unset +
   ``NORM_UNPARSEABLE_AMOUNT`` (the sheet asserts no single total; we do not invent
   one). Caller emits a ``money_unparseable`` item.

The category mapping stands in all four branches — an unreadable amount never drops
the fact. The mapper runs this ONLY on monetary components (a ``costs_fees`` base or
a ``restitution`` additive); a stray ``$`` on a non-monetary component is not read.
"""

from __future__ import annotations

import re

from pipeline.normalization.models import MoneyExtractionResult
from pipeline.normalization.vocab import NORM_UNPARSEABLE_AMOUNT

# `$`-required money token (LOCKED, 22.5 map gate). Three shapes, tried in order so
# a comma-grouped or decimal amount is consumed whole before the bare-integer arm:
#   $1,234 / $1,234.56 / $12,345,678.00   comma-grouped, optional cents
#   $500.00 / $1234.56                    `$` + `.NN` decimal
#   $500 / $1234                          `$` + bare integer (whole dollars)
MONEY_TOKEN = re.compile(r"\$\d{1,3}(?:,\d{3})+(?:\.\d{2})?|\$\d+\.\d{2}|\$\d+")

# A currency indicator: the presence of a `$`. A `$` with no parseable MONEY_TOKEN
# after it is branch 2 (present-but-unreadable), distinct from branch 1 (no `$`).
_CURRENCY_INDICATOR = re.compile(r"\$")


def token_to_cents(token: str) -> int:
    """Convert one :data:`MONEY_TOKEN` match to integer cents.

    Strips the leading ``$`` and any thousands commas. A ``.NN`` suffix is exactly
    two digits by construction, so its value is whole cents; a token with no
    decimal is whole dollars (``* 100``). Integer arithmetic only — no float ever
    touches the money path.
    """
    s = token.lstrip("$").replace(",", "")
    if "." in s:
        dollars, frac = s.split(".")
        return int(dollars) * 100 + int(frac)
    return int(s) * 100


def distinct_amounts(text: str) -> set[int]:
    """The set of DISTINCT integer-cent amounts in ``text`` (``$``-required).

    Distinct-by-value: "``$500 ... $500``" yields ``{50000}`` (one amount), so the
    same amount repeated is a single-amount (branch 3) SET, not a multiple.
    """
    return {token_to_cents(m.group(0)) for m in MONEY_TOKEN.finditer(text)}


def extract_amount(raw_text: str) -> MoneyExtractionResult:
    """Extract a single monetary amount from ``raw_text`` per the locked triage.

    Returns a :class:`MoneyExtractionResult` whose ``amount_cents`` is set ONLY for
    the exactly-one-distinct-amount branch; branches 2 and 4 carry
    ``NORM_UNPARSEABLE_AMOUNT`` (caller -> ``money_unparseable`` item), and branch 1
    carries neither an amount nor a warning (amount legitimately absent).
    """
    amounts = distinct_amounts(raw_text)
    if len(amounts) == 1:
        (cents,) = tuple(amounts)
        return MoneyExtractionResult(raw_text=raw_text, amount_cents=cents)
    # 0 or >=2 distinct amounts: the amount is unset. It is "unparseable" (a review
    # item) iff a `$` is present at all — branch 2 ($ but nothing parseable) or
    # branch 4 (>=2 distinct); branch 1 (no `$`) is a legitimate absence.
    if not amounts and not _CURRENCY_INDICATOR.search(raw_text):
        return MoneyExtractionResult(raw_text=raw_text, amount_cents=None)
    return MoneyExtractionResult(
        raw_text=raw_text,
        amount_cents=None,
        warnings=(NORM_UNPARSEABLE_AMOUNT,),
    )
