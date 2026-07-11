import pytest

from pipeline.collector.enumeration import COURT_PREFIXES, docket_range, format_docket


def test_format_docket_zero_pads_to_seven_digits():
    assert format_docket("MC", 2025, 1) == "MC-51-CR-0000001-2025"
    assert format_docket("MC", 2025, 451) == "MC-51-CR-0000451-2025"
    assert format_docket("MC", 2025, 9_999_999) == "MC-51-CR-9999999-2025"


def test_format_docket_rejects_unsupported_court():
    with pytest.raises(ValueError, match="unsupported court"):
        format_docket("CP", 2025, 1)


def test_format_docket_rejects_out_of_range_sequence():
    with pytest.raises(ValueError, match="out of range"):
        format_docket("MC", 2025, 0)
    with pytest.raises(ValueError, match="out of range"):
        format_docket("MC", 2025, 10_000_000)


def test_docket_range_is_consecutive_and_padded():
    got = docket_range("MC", 2025, 1, 3)
    assert got == [
        "MC-51-CR-0000001-2025",
        "MC-51-CR-0000002-2025",
        "MC-51-CR-0000003-2025",
    ]


def test_docket_range_from_offset_start():
    got = docket_range("MC", 2025, 449, 3)
    assert got == [
        "MC-51-CR-0000449-2025",
        "MC-51-CR-0000450-2025",
        "MC-51-CR-0000451-2025",
    ]


def test_docket_range_length_matches_count():
    assert len(docket_range("MC", 2025, 1, 600)) == 600


def test_docket_range_rejects_bad_args():
    with pytest.raises(ValueError):
        docket_range("MC", 2025, 0, 5)
    with pytest.raises(ValueError):
        docket_range("MC", 2025, 1, 0)
    with pytest.raises(ValueError, match="overflow"):
        docket_range("MC", 2025, 9_999_999, 5)


def test_only_mc_is_supported():
    assert set(COURT_PREFIXES) == {"MC"}
