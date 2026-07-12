"""Pure-helper tests for the judge-coverage report tool (Task 22.3, AC 8).

Covers the null/absent-as-distinct-class accounting (honest denominator), the
match-method tallies, and the console/report separation (raw values live only in
the report body, never the console headline) without a database.
"""

from __future__ import annotations

from pipeline.normalization.judge_matcher import (
    JudgeMatcher,
    RosterEntry,
    RosterSnapshot,
)
from pipeline.reports import judge_coverage
from pipeline.reports.judge_coverage import (
    _field_stats,
    _print_headline,
    build_judge_coverage_report,
    main,
)

ROSTER = RosterSnapshot(
    entries=(
        RosterEntry("j1", "coyle-anne-marie", "Anne Marie Coyle"),
        RosterEntry("j2", "lopez-maria", "Maria Lopez"),
    )
)


def test_field_stats_counts_absent_separately_from_unmatched():
    matcher = JudgeMatcher(ROSTER)
    value_freqs = [
        ("Coyle, Anne Marie", 10),  # exact
        ("Doe, Jane", 3),  # unmatched
        (None, 5),  # absent
        ("   ", 2),  # absent (blank)
    ]
    stats = _field_stats(matcher, value_freqs)
    assert stats["distinct_total"] == 4
    assert stats["absent_distinct"] == 2
    assert stats["absent_rows"] == 7
    assert stats["present_distinct"] == 2
    assert stats["present_rows"] == 13
    assert stats["matched_rows"] == 10  # unmatched excluded from matched
    assert stats["unmatched_tail_size"] == 1
    assert stats["method_distinct"]["exact"] == 1
    assert stats["method_distinct"]["unmatched"] == 1


def test_report_body_carries_values_but_console_does_not(capsys):
    field_value_freqs = {"assigned": [("Coyle, Anne Marie", 4), ("Zzyzx, Quorra", 1)]}
    report, headline = build_judge_coverage_report(ROSTER, field_value_freqs)
    # Value present in the report body (file-only surface).
    assert "Zzyzx, Quorra" in report
    assert headline["assigned"]["unmatched_tail_size"] == 1
    # Console headline is counts only — pinned decision 5: no raw value printed.
    _print_headline(headline)
    console = capsys.readouterr().out
    assert "Zzyzx" not in console
    assert "unmatched_tail_size=1" in console


def test_main_refuses_in_ci(monkeypatch):
    monkeypatch.setattr(judge_coverage, "running_in_ci", lambda: True)
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused")
    assert main([]) == 2
