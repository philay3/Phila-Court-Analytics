import pytest

from pipeline.helpers import parse_date, to_days
from pipeline.identity import assert_no_leak, hash_defendant, normalize_name

TEST_SALT = "test-salt"


def test_parse_date():
    assert parse_date("03/14/2024") == "2024-03-14"
    assert parse_date("") is None
    assert parse_date("garbage") is None


def test_to_days_simple():
    assert to_days("23 Months") == 690


def test_to_days_compound():
    assert to_days("1 Year 6 Months") == 540


def test_to_days_half():
    assert to_days("11 1/2 Months") == 345


def test_to_days_unicode_half():
    assert to_days("11½ Months") == 345


def test_to_days_days_only():
    assert to_days("90 Days") == 90


def test_to_days_unparseable():
    assert to_days("Life") is None


def test_normalize_name():
    assert normalize_name("  O'Brien,  Patrick J. ") == "o brien patrick j"


def test_hash_deterministic():
    assert hash_defendant("Smith, John", 1990, salt=TEST_SALT) == hash_defendant(
        "smith  john", 1990, salt=TEST_SALT
    )


def test_leak_assertion_trips():
    # A name fragment planted in a VALUE must still fail, and the scan is
    # recursive across nested dicts and lists (name buried in a list of dicts).
    with pytest.raises(RuntimeError):
        assert_no_leak(["Smith"], {"charges": [{"offense": "smith, anne"}]})


def test_leak_ignores_key_name_collision():
    # A fragment that coincides with a structural KEY substring but appears in
    # no value must NOT trip (the Phase 7 stage 3 fix). "ross" is inside the
    # key "cross_court_dockets"; the value holds only docket numbers.
    record = {"cross_court_dockets": "CP-51-CR-0000000-2025", "otn": None}
    assert assert_no_leak(["ross"], record) is None


def test_to_days_decimals():
    assert to_days("6.00 Years") == 2160


def test_to_days_flat_year():
    assert to_days("1 Year") == 360
    assert to_days("12 Months") == 360
