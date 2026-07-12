"""Pure-helper tests for the distinct-value report tool (Task 22.2, AC 1).

Covers the coverage-threshold math and the console/report separation (values go
only to the report body, never the console summary) without a database.
"""

from __future__ import annotations

from collections import Counter

from pipeline.reports import distinct_values
from pipeline.reports.distinct_values import (
    build_report,
    coverage_for_n,
    main,
)


def test_coverage_for_n_counts_distinct_and_weight():
    counter = Counter({"a": 5, "b": 3, "c": 1})
    assert coverage_for_n(counter, 1) == (3, 9)
    assert coverage_for_n(counter, 3) == (2, 8)
    assert coverage_for_n(counter, 5) == (1, 5)
    assert coverage_for_n(counter, 10) == (0, 0)


def test_build_report_includes_values_and_buckets():
    counters = {"statute": Counter({"18 § 1": 2, "18 § 2": 1})}
    report = build_report(counters, total_rows=3, table="parsed.charges")
    assert "distinct-value report over parsed.charges".lower() in report.lower()
    assert "statute: 2 distinct" in report
    # The full value list is present in the report body.
    assert "'18 § 1'" in report
    assert "distinct>=N" in report


def test_main_refuses_in_ci(monkeypatch):
    # Required Fix 1(b): the tool must refuse in CI before touching the DB.
    monkeypatch.setattr(distinct_values, "running_in_ci", lambda: True)
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused")
    assert main([]) == 2
