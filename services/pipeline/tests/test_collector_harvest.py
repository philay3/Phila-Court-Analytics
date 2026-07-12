"""Harvest tests (AC-3): the privacy invariant is proven by a fake page whose
row cells RAISE on access to any column other than the pinned docket-number
cell. If the harvester ever touches a caption/participant/DOB cell, ``nth``
raises and the suite fails."""

import pytest

from pipeline.collector.harvest import (
    DOCKET_CELL_INDEX,
    ROW_SELECTOR,
    SHEET_ANCHOR_SELECTOR,
    HarvestedRow,
    harvest_rows,
)

# A wide row template mirroring the live grid (19 columns). Only index 2 is the
# docket-number cell; every other index carries poison text a correct harvester
# must never read (index 4 = Case Caption, 7 = Primary Participant(s), 8 = DOB).
_POISON = "SECRET-DEFENDANT-TEXT"


def _cells(docket_text: str, width: int = 19) -> list[str]:
    row = [_POISON] * width
    row[DOCKET_CELL_INDEX] = docket_text
    return row


class FakeCell:
    def __init__(self, text: str) -> None:
        self._text = text

    def inner_text(self) -> str:
        return self._text


class FakeCells:
    """``nth(i)`` raises for any i other than the pinned docket-cell index —
    the enforced privacy invariant."""

    def __init__(self, texts: list[str]) -> None:
        self._texts = texts

    def count(self) -> int:
        return len(self._texts)

    def nth(self, i: int) -> FakeCell:
        if i != DOCKET_CELL_INDEX:
            raise AssertionError(f"harvester accessed forbidden cell index {i}")
        return FakeCell(self._texts[i])


class FakeAnchor:
    def __init__(self, href: str | None) -> None:
        self._href = href

    def count(self) -> int:
        return 0 if self._href is None else 1

    @property
    def first(self) -> "FakeAnchor":
        return self

    def get_attribute(self, name: str) -> str | None:
        assert name == "href"
        return self._href


class FakeRow:
    def __init__(self, cell_texts: list[str], href: str | None) -> None:
        self._cells = FakeCells(cell_texts)
        self._anchor = FakeAnchor(href)

    def locator(self, selector: str):
        if selector == "td":
            return self._cells
        if selector == SHEET_ANCHOR_SELECTOR:
            return self._anchor
        raise AssertionError(f"unexpected row selector {selector!r}")


class FakeRows:
    def __init__(self, rows: list[FakeRow]) -> None:
        self._rows = rows

    def count(self) -> int:
        return len(self._rows)

    def nth(self, i: int) -> FakeRow:
        return self._rows[i]


class FakePage:
    def __init__(self, rows: list[FakeRow]) -> None:
        self._rows = FakeRows(rows)

    def locator(self, selector: str):
        if selector == ROW_SELECTOR:
            return self._rows
        raise AssertionError(f"unexpected page selector {selector!r}")


def test_harvest_reads_only_docket_cell_and_anchor():
    rows = [
        FakeRow(_cells("MC-51-CR-0000001-2025"), "/x/CpDocketSheet?h=1"),
        FakeRow(_cells("CP-51-CR-0000002-2025"), "/x/CpDocketSheet?h=2"),
        FakeRow(_cells("Traffic Citation TR-000123"), "/x/MdjDocketSheet?h=3"),  # skip
        FakeRow(_cells("MC-51-CR-0000003-2025"), None),  # matched, no anchor
        FakeRow([_POISON, _POISON], None),  # too few cells -> skip via count only
    ]
    result = harvest_rows(FakePage(rows))
    assert result.rows == [
        HarvestedRow("MC", "MC-51-CR-0000001-2025", "/x/CpDocketSheet?h=1"),
        HarvestedRow("CP", "CP-51-CR-0000002-2025", "/x/CpDocketSheet?h=2"),
        HarvestedRow("MC", "MC-51-CR-0000003-2025", None),
    ]
    assert result.skipped_rows == 2


def test_harvest_never_touches_caption_participant_dob_cells():
    # A row where any non-docket access would raise; a full harvest must succeed
    # without touching those columns.
    rows = [FakeRow(_cells("CP-51-CR-0009999-2025"), "/x/CpDocketSheet?h=9")]
    result = harvest_rows(FakePage(rows))  # must not raise
    assert result.rows[0].docket == "CP-51-CR-0009999-2025"


def test_harvest_empty_page():
    result = harvest_rows(FakePage([]))
    assert result.rows == []
    assert result.skipped_rows == 0


def test_forbidden_cell_access_would_fail_loudly():
    # Sanity: prove the fake's guard actually fires, so the invariant test above
    # is meaningful and not vacuously green.
    cells = FakeCells(_cells("MC-51-CR-0000001-2025"))
    with pytest.raises(AssertionError, match="forbidden cell index 4"):
        cells.nth(4)
