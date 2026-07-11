from pipeline.collector.classification import (
    OUTCOME_BLOCKED,
    OUTCOME_ERROR,
    OUTCOME_HIT,
    OUTCOME_MISS,
    FetchSignal,
    classify,
)


def test_pdf_ok_is_hit():
    assert classify(FetchSignal(pdf_ok=True, result_rows=1)) == OUTCOME_HIT


def test_empty_results_is_miss():
    assert classify(FetchSignal(result_rows=0)) == OUTCOME_MISS


def test_bot_check_is_blocked_never_solved():
    assert classify(FetchSignal(bot_check=True)) == OUTCOME_BLOCKED


def test_rate_limited_is_blocked():
    assert classify(FetchSignal(rate_limited=True)) == OUTCOME_BLOCKED


def test_error_is_error():
    assert classify(FetchSignal(error=True, error_type="TimeoutError")) == OUTCOME_ERROR


def test_block_precedence_over_empty_results_miss():
    # FIX 5: a page with block indicators AND zero rows is blocked, never miss.
    signal = FetchSignal(bot_check=True, rate_limited=True, result_rows=0, pdf_ok=False)
    assert classify(signal) == OUTCOME_BLOCKED


def test_block_precedence_over_pdf_hit():
    # A block indicator wins even if a stray PDF flag is set.
    assert classify(FetchSignal(bot_check=True, pdf_ok=True)) == OUTCOME_BLOCKED


def test_error_precedence_over_block():
    # A hard transport failure has no page to inspect and wins first.
    assert classify(FetchSignal(error=True, bot_check=True)) == OUTCOME_ERROR
