"""Results-grid harvest for search mode (Task COL-2, PD-3).

The results grid contains defendant-identifying columns — Case Caption (index
4), Primary Participant(s) (index 7), Date Of Birth(s) (index 8). This harvester
reads EXACTLY two things per row and nothing else:

  1. the docket-number cell — column index 2 (pinned from the live DOM: the
     ``thead th`` label at index 2 is "Docket Number", and every CP/MC-51-CR
     data row carries its docket number in that column; index 0 is a second
     "Docket Number" header for the row-expand control, not the number text);
  2. the docket-sheet anchor href — row-scoped ``a[href*='CpDocketSheet']``
     (pinned from the live DOM: the first CP-51-CR row and the first MC-51-CR
     row both resolve to the ``CpDocketSheet`` endpoint; ``MdjDocketSheet``
     appears only on MDJ rows, which never match the CP/MC pattern).

Caption, participant, and DOB cells are NEVER read, printed, logged, or stored.
This is a tested invariant (AC-3), not a comment: the harvest test drives a fake
page whose row objects RAISE on access to any cell other than the pinned
docket-number cell, so the suite fails if this harvester ever touches another
column.

Harvest regex ``(CP|MC)-51-CR-\\d{7}-\\d{4}`` — both courts are always recorded;
fetching is gated downstream by ``--court``. Rows whose docket cell matches
neither pattern (MDJ, traffic, miscellaneous) are counted as ``skipped_rows``
and otherwise ignored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Pinned from the live DOM (COL-2 Step 0 recon, F5 sign-off). See module docstring.
DOCKET_CELL_INDEX = 2
SHEET_ANCHOR_SELECTOR = "a[href*='CpDocketSheet']"
ROW_SELECTOR = "table tbody tr"

CRIM_RE = re.compile(r"(CP|MC)-51-CR-\d{7}-\d{4}")


@dataclass(frozen=True)
class HarvestedRow:
    """One harvested CP/MC-51-CR row — content-free beyond the docket number."""

    court: str  # "CP" or "MC"
    docket: str
    href: str | None


@dataclass(frozen=True)
class HarvestResult:
    rows: list[HarvestedRow]
    skipped_rows: int


def harvest_rows(page) -> HarvestResult:
    """Harvest CP/MC-51-CR (docket, href) pairs from the current results page.

    Reads only the pinned docket-number cell and the row-scoped docket-sheet
    anchor per row (PD-3). A row whose docket cell matches neither court pattern
    — and a row with too few cells to hold the docket column — is counted in
    ``skipped_rows`` and skipped without reading any other cell.
    """
    rows = page.locator(ROW_SELECTOR)
    total = rows.count()
    harvested: list[HarvestedRow] = []
    skipped = 0
    for i in range(total):
        row = rows.nth(i)
        cells = row.locator("td")
        # Guard by count only (no cell text read): a row without the docket
        # column cannot be a case row.
        if cells.count() <= DOCKET_CELL_INDEX:
            skipped += 1
            continue
        text = cells.nth(DOCKET_CELL_INDEX).inner_text() or ""
        match = CRIM_RE.search(text)
        if match is None:
            skipped += 1
            continue
        anchor = row.locator(SHEET_ANCHOR_SELECTOR)
        href = anchor.first.get_attribute("href") if anchor.count() else None
        harvested.append(HarvestedRow(match.group(1), match.group(0), href))
    return HarvestResult(harvested, skipped)
