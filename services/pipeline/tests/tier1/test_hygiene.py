"""Tier-1 docket-number hygiene (Task 19.1, pinned decision 1).

Machine-enforced guarantee that no realistic docket number ever lands in the
repo. Scans the ENTIRE ``tests/tier1/`` tree — fixtures, goldens,
``fixture-index.yaml``, ``support.py``, ``generate_goldens.py``, and the test
modules themselves — for any token matching the CPCMS docket shape, and fails on
any whose 7-digit sequence is not the allowed all-zeros(+trailing-digit)
placeholder. The whole-tree scan means the cross-court/related-case reference
inside ``held_cross_court_mc`` (a second docket) is checked automatically too.

Placeholder rule (decision 1): the sequence segment must match ``000000\\d`` —
six zeros plus one trailing digit (``0000000`` .. ``0000009``). Anything else in
docket shape (a realistic sequence such as ``1234567``) fails.

Fictional-name spot rule (documented, not machine-scanned here): every name in
every fixture is invented (surnames Sample / Placeholder / Codefend, given names
Dana / Chris / Lee / Alex, judge surnames Reyes / Torres / Nguyen / Okonkwo). No
real person's name appears. Names are not pattern-detectable the way docket
numbers are, so this rule is enforced by authorship + review, and the golden
hashing uses only the public TIER1_TEST_SALT so committed hashes leak nothing.

On failure this reports the file and offset only — never the matched token — so a
realistic docket that somehow slipped in is not echoed into test output.
"""

from __future__ import annotations

import re
from pathlib import Path

# CPCMS docket shape with the 7-digit sequence captured.
_DOCKET_RE = re.compile(r"(?:CP|MC)-\d{2}-[A-Z]{2}-(\d{7})-\d{4}")
# Allowed placeholder sequence: six zeros plus one trailing digit.
_PLACEHOLDER_SEQ = re.compile(r"^000000\d$")

_TIER1_DIR = Path(__file__).resolve().parent
_TEXT_SUFFIXES = {".py", ".yaml", ".txt", ".json"}


def _scan_files():
    for path in sorted(_TIER1_DIR.rglob("*")):
        if path.is_file() and path.suffix in _TEXT_SUFFIXES:
            yield path


def test_only_placeholder_docket_numbers_in_tier1_tree():
    offenders: list[str] = []
    total_docket_tokens = 0
    for path in _scan_files():
        text = path.read_text()
        for m in _DOCKET_RE.finditer(text):
            total_docket_tokens += 1
            if not _PLACEHOLDER_SEQ.match(m.group(1)):
                rel = path.relative_to(_TIER1_DIR)
                # Report location only; never echo the matched (possibly real) token.
                offenders.append(f"{rel} @ offset {m.start()}")

    assert not offenders, (
        "realistic docket-number pattern found in tier-1 tree:\n" + "\n".join(offenders)
    )
    # Sanity: the scan actually inspected docket tokens (guards against a
    # vacuous pass if the corpus or regex ever silently stops matching).
    assert total_docket_tokens > 0, "hygiene scan found no docket tokens at all"
