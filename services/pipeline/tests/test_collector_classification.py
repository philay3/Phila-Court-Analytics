from pipeline.collector.classification import (
    OUTCOME_BLOCKED,
    OUTCOME_ERROR,
    OUTCOME_HIT,
    OUTCOME_MISS,
    FetchSignal,
    classify,
)


def test_pdf_ok_is_hit():
    assert classify(FetchSignal(pdf_ok=True)) == OUTCOME_HIT


def test_positively_identified_no_results_is_miss():
    assert classify(FetchSignal(no_results=True)) == OUTCOME_MISS


def test_miss_requires_the_positive_no_results_marker():
    # FIX 1 (fail-closed): without the positive no-results marker, an otherwise
    # empty signal is NOT a miss — it is a block.
    assert classify(FetchSignal()) == OUTCOME_BLOCKED


def test_unknown_page_shape_is_blocked_not_miss():
    # An unrecognized page (no PDF, no positive no-results marker, no known
    # block signature) fails closed to blocked.
    assert classify(FetchSignal(pdf_ok=False, no_results=False)) == OUTCOME_BLOCKED


def test_bot_check_is_blocked_never_solved():
    assert classify(FetchSignal(bot_check=True)) == OUTCOME_BLOCKED


def test_rate_limited_is_blocked():
    assert classify(FetchSignal(rate_limited=True)) == OUTCOME_BLOCKED


def test_unauthorized_signature_is_blocked():
    # FIX 2: the observed "unauthorized" / "not authorized" page is a block.
    assert classify(FetchSignal(unauthorized=True)) == OUTCOME_BLOCKED


def test_error_is_error():
    assert classify(FetchSignal(error=True, error_type="TimeoutError")) == OUTCOME_ERROR


def test_block_precedence_over_no_results_miss():
    # A page with a block indicator AND the no-results marker is blocked.
    signal = FetchSignal(unauthorized=True, no_results=True)
    assert classify(signal) == OUTCOME_BLOCKED


def test_block_precedence_over_pdf_hit():
    assert classify(FetchSignal(bot_check=True, pdf_ok=True)) == OUTCOME_BLOCKED


def test_error_precedence_over_block():
    # A hard transport failure has no page to inspect and wins first.
    assert classify(FetchSignal(error=True, bot_check=True)) == OUTCOME_ERROR
