import pytest

from pipeline.identity import (
    assert_no_leak,
    assert_related_cases_clean,
    hash_defendant,
    hash_defendant_name_only,
)

TEST_SALT = "test-salt"


# --- assert_related_cases_clean (ported from Capstone test_mc_parser.py) ---


def test_privacy_guard_rejects_extra_field():
    bad = {
        "related_cases": [
            {
                "docket_number": "MC-51-CR-0000000-2025",
                "court": "Municipal Court",
                "association_reason": "Refiled",
                "caption": "Example, Adam",
            }
        ]
    }
    with pytest.raises(RuntimeError):
        assert_related_cases_clean(bad)


def test_privacy_guard_passes_clean_record():
    good = {
        "related_cases": [
            {
                "docket_number": "MC-51-CR-0000000-2025",
                "court": "Municipal Court",
                "association_reason": "Refiled",
            }
        ]
    }
    assert assert_related_cases_clean(good) is None


# --- Salt is a required keyword-only parameter with no default ---


@pytest.mark.parametrize("bad_salt", ["", "   ", None])
def test_hash_defendant_rejects_missing_salt(bad_salt):
    with pytest.raises(ValueError) as excinfo:
        hash_defendant("Smith, John", 1990, salt=bad_salt)
    # Error names the env var and the parameter; it must never echo the
    # defendant name, birth year, or any docket data.
    message = str(excinfo.value)
    assert "DEFENDANT_HASH_SALT" in message
    assert "salt" in message
    assert "Smith" not in message
    assert "1990" not in message


def test_hash_defendant_requires_salt_keyword():
    # Salt is keyword-only: a positional third argument is a TypeError, which
    # prevents silently passing something else as the salt.
    with pytest.raises(TypeError):
        hash_defendant("Smith, John", 1990, TEST_SALT)


def test_hash_defendant_deterministic_with_salt():
    first = hash_defendant("Smith, John", 1990, salt=TEST_SALT)
    second = hash_defendant("Smith, John", 1990, salt=TEST_SALT)
    assert first == second


def test_hash_defendant_salt_changes_output():
    assert hash_defendant("Smith, John", 1990, salt="salt-a") != hash_defendant(
        "Smith, John", 1990, salt="salt-b"
    )


# --- hash_defendant_name_only (34.4 blank-DOB caption variant basis) ---


@pytest.mark.parametrize("bad_salt", ["", "   ", None])
def test_hash_name_only_rejects_missing_salt(bad_salt):
    with pytest.raises(ValueError) as excinfo:
        hash_defendant_name_only("Smith, John", salt=bad_salt)
    message = str(excinfo.value)
    assert "DEFENDANT_HASH_SALT" in message
    assert "Smith" not in message


def test_hash_name_only_requires_salt_keyword():
    with pytest.raises(TypeError):
        hash_defendant_name_only("Smith, John", TEST_SALT)


def test_hash_name_only_deterministic_and_salt_sensitive():
    assert hash_defendant_name_only(
        "Smith, John", salt=TEST_SALT
    ) == hash_defendant_name_only("Smith, John", salt=TEST_SALT)
    assert hash_defendant_name_only(
        "Smith, John", salt="salt-a"
    ) != hash_defendant_name_only("Smith, John", salt="salt-b")


def test_hash_name_only_normalization_parity_with_full_basis():
    # Same normalization as hash_defendant: case, punctuation, and whitespace
    # variants of the same name collapse to one hash.
    assert hash_defendant_name_only(
        "SMITH,  JOHN", salt=TEST_SALT
    ) == hash_defendant_name_only("smith john", salt=TEST_SALT)


def test_hash_name_only_differs_from_full_basis_for_any_year():
    # The name-only basis is not any year's name+year basis (no sentinel year).
    name_only = hash_defendant_name_only("Smith, John", salt=TEST_SALT)
    for year in (0, 1900, 1990, 2025):
        assert name_only != hash_defendant("Smith, John", year, salt=TEST_SALT)


# --- assert_no_leak key-allowlist rule (dict keys are never scanned) ---


def test_leak_key_allowlist_exact_key_match():
    # The sentinel exactly equals a dict KEY but appears in no VALUE. Keys are
    # structural constants and must never be scanned, so this must not trip.
    record = {"defendant_name": None, "otn": "CP-51-CR-0000001-2025"}
    assert assert_no_leak(["defendant_name"], record) is None


# --- 18.3 Q1: whole-token (boundary-anchored) matching, replacing substring ---


def test_leak_whole_token_collision_still_blocks():
    # A sentinel that appears as its OWN token in a value is a real leak: the
    # judge value's surname equals a defendant name part. Boundary-anchored
    # matching still catches it, so the backstop hard-stops.
    record = {"case": {"assigned_judge_raw": "Cole, Judge A."}}
    with pytest.raises(RuntimeError):
        assert_no_leak(["Cole"], record)


def test_leak_fragment_substring_no_longer_blocks():
    # 18.3 Q1: a sentinel that appears ONLY as a proper sub-span inside a larger
    # token ("Cole" inside "Coleman") is not a whole-token match and must not
    # block — this recovers the quarantine fragment false positives. The
    # surrendered leak class (fragment embedded in a larger token) is accepted.
    record = {"case": {"assigned_judge_raw": "Coleman, Judge A."}}
    assert assert_no_leak(["Cole"], record) is None


def test_leak_full_name_and_dob_still_matched_exactly():
    # Multi-token sentinels (rendered full name, DOB string) are matched with
    # their internal punctuation intact and outer boundaries anchored.
    record = {"case": {"note": "seen with Example, Chris on 01/01/1990 here"}}
    with pytest.raises(RuntimeError):
        assert_no_leak(["Example, Chris"], record)
    with pytest.raises(RuntimeError):
        assert_no_leak(["01/01/1990"], record)
