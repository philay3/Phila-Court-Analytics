"""Tests for the multi-table --field extension of distinct_values (Task 22.3).

Covers the fully-qualified field parser, the per-field report body (values
present), and the per-field row denominator (each field keeps its own table's row
count) — all without a database.
"""

from __future__ import annotations

from collections import Counter

import pytest

from pipeline.reports.distinct_values import (
    build_field_report,
    parse_field,
)


def test_parse_field_splits_qualified_identifier():
    assert parse_field("parsed.dockets.assigned_judge_raw") == (
        "parsed.dockets",
        "assigned_judge_raw",
    )


@pytest.mark.parametrize(
    "field",
    ["parsed.charges", "a.b.c.d", "parsed.dockets.bad-column", "parsed.DOCKETS.col"],
)
def test_parse_field_rejects_malformed_or_unsafe(field):
    with pytest.raises(ValueError):
        parse_field(field)


def test_build_field_report_uses_per_field_denominator():
    field_stats = {
        "parsed.dockets.assigned_judge_raw": (Counter({"a": 3, "b": 1}), 4),
        "parsed.charges.disposition_judge_raw": (Counter({"a": 5}), 5),
    }
    report = build_field_report(field_stats)
    # Both fields present with their own row totals.
    assert "parsed.dockets.assigned_judge_raw: 2 distinct (rows=4" in report
    assert "parsed.charges.disposition_judge_raw: 1 distinct (rows=5" in report
    # Values appear in the file body.
    assert "'a'" in report and "'b'" in report
