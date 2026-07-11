from pipeline.collector.guard import (
    STOP_BLOCK_STREAK,
    STOP_ERROR_STREAK,
    RunGuard,
)


def test_five_consecutive_blocks_trip_block_streak():
    guard = RunGuard()
    reasons = [guard.record("blocked") for _ in range(5)]
    assert reasons[:4] == [None, None, None, None]
    assert reasons[4] == STOP_BLOCK_STREAK
    assert guard.block_streak == 5


def test_hit_resets_block_streak():
    guard = RunGuard()
    guard.record("blocked")
    guard.record("blocked")
    assert guard.block_streak == 2
    guard.record("hit")
    assert guard.block_streak == 0


def test_clean_miss_resets_block_streak():
    guard = RunGuard()
    guard.record("blocked")
    guard.record("blocked")
    assert guard.record("miss") is None
    assert guard.block_streak == 0


def test_error_is_neutral_to_block_streak():
    guard = RunGuard()
    guard.record("blocked")
    guard.record("blocked")
    guard.record("error")  # neither resets nor increments the block streak
    assert guard.block_streak == 2
    # three more blocks then reach five total
    guard.record("blocked")
    guard.record("blocked")
    assert guard.record("blocked") == STOP_BLOCK_STREAK


def test_five_consecutive_errors_trip_error_streak():
    guard = RunGuard()
    reasons = [guard.record("error") for _ in range(5)]
    assert reasons[:4] == [None, None, None, None]
    assert reasons[4] == STOP_ERROR_STREAK
    assert guard.error_streak == 5


def test_error_streak_resets_on_hit_miss_and_block():
    for resetter in ("hit", "miss", "blocked"):
        guard = RunGuard()
        guard.record("error")
        guard.record("error")
        assert guard.error_streak == 2
        guard.record(resetter)
        assert guard.error_streak == 0


def test_already_present_is_neutral_to_both_streaks():
    guard = RunGuard()
    guard.record("blocked")
    guard.record("error")
    guard.record("already_present")
    assert guard.block_streak == 1
    assert guard.error_streak == 1


def test_streaks_are_consecutive_not_cumulative():
    guard = RunGuard()
    for _ in range(4):
        guard.record("blocked")
    guard.record("hit")  # resets
    reasons = [guard.record("blocked") for _ in range(5)]
    assert reasons[4] == STOP_BLOCK_STREAK
    assert reasons[3] is None
