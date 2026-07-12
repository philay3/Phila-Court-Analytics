"""Search-result classifier tests (AC-2): four positive states + fail-closed
default + error/block precedence. Pure, offline."""

from pipeline.collector.search_classification import (
    OUTCOME_GRID_COMPLETE,
    OUTCOME_GRID_EMPTY,
    OUTCOME_GRID_TRUNCATED,
    OUTCOME_SEARCH_BLOCKED,
    OUTCOME_SEARCH_ERROR,
    SearchSignal,
    classify_search,
)


def test_grid_complete_when_table_and_rows_and_no_banner():
    signal = SearchSignal(
        search_ui_present=True, results_table_present=True, row_count=241
    )
    assert classify_search(signal) == OUTCOME_GRID_COMPLETE


def test_grid_truncated_when_banner_present():
    signal = SearchSignal(
        search_ui_present=True,
        results_table_present=True,
        row_count=805,
        banner_present=True,
    )
    assert classify_search(signal) == OUTCOME_GRID_TRUNCATED


def test_grid_empty_no_results_table_form_a():
    # Blocker-2 Option A, form (a): served search UI, no results table, 0 rows.
    signal = SearchSignal(
        search_ui_present=True, results_table_present=False, row_count=0
    )
    assert classify_search(signal) == OUTCOME_GRID_EMPTY


def test_grid_empty_zero_row_table_form_b():
    # Blocker-2 Option A, form (b): served search UI, a results table that
    # rendered with zero rows.
    signal = SearchSignal(
        search_ui_present=True, results_table_present=True, row_count=0
    )
    assert classify_search(signal) == OUTCOME_GRID_EMPTY


def test_fail_closed_default_without_search_ui_is_blocked():
    # The fail-closed default: an empty signal (no served search UI) is blocked,
    # never empty — emptiness is NEVER inferred from absence.
    assert classify_search(SearchSignal()) == OUTCOME_SEARCH_BLOCKED


def test_no_search_ui_but_rows_is_blocked():
    # An unrecognized page claiming rows without the served search UI fails
    # closed to blocked.
    signal = SearchSignal(
        search_ui_present=False, results_table_present=True, row_count=10
    )
    assert classify_search(signal) == OUTCOME_SEARCH_BLOCKED


def test_bot_check_is_blocked():
    assert classify_search(SearchSignal(bot_check=True)) == OUTCOME_SEARCH_BLOCKED


def test_rate_limited_is_blocked():
    assert classify_search(SearchSignal(rate_limited=True)) == OUTCOME_SEARCH_BLOCKED


def test_unauthorized_is_blocked():
    assert classify_search(SearchSignal(unauthorized=True)) == OUTCOME_SEARCH_BLOCKED


def test_error_is_error():
    signal = SearchSignal(error=True, error_type="TimeoutError")
    assert classify_search(signal) == OUTCOME_SEARCH_ERROR


def test_error_precedence_over_block():
    # A hard transport failure has no page to inspect and wins first.
    signal = SearchSignal(error=True, bot_check=True)
    assert classify_search(signal) == OUTCOME_SEARCH_ERROR


def test_block_precedence_over_truncated():
    # A block signature outranks a banner that a soft-block page might carry.
    signal = SearchSignal(
        search_ui_present=True,
        banner_present=True,
        row_count=5,
        results_table_present=True,
        unauthorized=True,
    )
    assert classify_search(signal) == OUTCOME_SEARCH_BLOCKED


def test_banner_precedence_over_complete():
    # Banner present with rows => truncated, not complete.
    signal = SearchSignal(
        search_ui_present=True,
        results_table_present=True,
        row_count=805,
        banner_present=True,
    )
    assert classify_search(signal) == OUTCOME_GRID_TRUNCATED
