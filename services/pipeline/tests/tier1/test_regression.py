"""Tier-1 regression: parse every fixture, compare to its committed golden.

Re-parses each fixture with the fixed public ``TIER1_TEST_SALT`` and asserts the
deterministic projection (record minus ``parsed_at``, warnings, ``review_needed``,
error arm) equals the committed golden BYTE-FOR-BYTE at the value level, with a
readable field-level diff on failure. This is the day-to-day regression reference:
a parser change that alters any parsed value, warning, or review flag on any
covered scenario fails here.

Fully offline and repo-local — no PDF, no network, no ``~/court-data/`` reference.
19.2 builds the run-fixtures CLI on top of this same loader/projection.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from pipeline.run_fixtures import (
    INDEX_PATH,
    build_golden,
    diff_fields,
    docket_for_court,
    load_fixture_pages,
    load_golden,
)

_INDEX = yaml.safe_load(INDEX_PATH.read_text())
_FIXTURES = [entry["filename"] for entry in _INDEX["fixtures"]]


@pytest.mark.parametrize("fixture_filename", _FIXTURES)
def test_fixture_matches_golden(fixture_filename):
    entry = next(e for e in _INDEX["fixtures"] if e["filename"] == fixture_filename)
    docket = docket_for_court(entry["court_type"])
    pages = load_fixture_pages(fixture_filename)

    got = build_golden(docket, pages)
    want = load_golden(fixture_filename)

    diffs = diff_fields(want, got)
    assert not diffs, "golden mismatch for {}:\n{}".format(
        fixture_filename, "\n".join(diffs)
    )


def test_no_local_corpus_reference_in_tier1_tree():
    """Belt-and-suspenders: no tier-1 file may reference the local-only real
    corpus root. The corpus is committed and offline. This module is skipped from
    its own scan (it necessarily contains the search token below)."""
    self_path = Path(__file__).resolve()
    token = (
        "court" + "-data"
    )  # the local-only corpus dir name, split to avoid self-match
    tier1 = self_path.parent
    offenders = []
    for path in tier1.rglob("*"):
        if path.resolve() == self_path:
            continue
        if path.is_file() and path.suffix in {".py", ".yaml", ".txt", ".json"}:
            if token in path.read_text():
                offenders.append(path.name)
    assert not offenders, f"local-corpus reference found in: {offenders}"
