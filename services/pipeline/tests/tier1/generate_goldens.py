"""Tier-1 golden generator (Task 19.1, decision 6).

Regenerates every committed golden JSON from its fixture by running the PARSER
(never hand-authored) with the fixed public ``TIER1_TEST_SALT``. Deterministic
and re-runnable: same fixtures + same parser => byte-identical goldens.

Discipline (decision 6): regeneration is gated behind an explicit ``--regenerate``
flag AND a ``tasks/worklog.md`` note. Run WITHOUT the flag and this exits
non-zero with a message and writes nothing — no silent no-op. The module is named
so pytest never collects it (no ``test_`` prefix) and defines no test functions.

Run from ``services/pipeline``:

    .venv/bin/python tests/tier1/generate_goldens.py --regenerate

Reads ``fixture-index.yaml`` for each fixture's court_type (which fixes the
placeholder docket the parser is handed) and writes one golden per fixture.
Offline; reaches no local-only real corpus.
"""

from __future__ import annotations

import sys

import yaml
from support import (
    GOLDENS_DIR,
    INDEX_PATH,
    build_golden,
    docket_for_court,
    golden_bytes,
    golden_filename,
    load_fixture_pages,
)


def main(argv: list[str]) -> int:
    if "--regenerate" not in argv:
        print(
            "refusing to run: golden regeneration requires the explicit "
            "--regenerate flag plus a tasks/worklog.md note (Task 19.1 "
            "decision 6). No goldens were written.",
            file=sys.stderr,
        )
        return 2

    index = yaml.safe_load(INDEX_PATH.read_text())
    GOLDENS_DIR.mkdir(exist_ok=True)
    written = 0
    for entry in index["fixtures"]:
        filename = entry["filename"]
        docket = docket_for_court(entry["court_type"])
        pages = load_fixture_pages(filename)
        golden = build_golden(docket, pages)
        (GOLDENS_DIR / golden_filename(filename)).write_text(golden_bytes(golden))
        written += 1
        print(f"wrote {golden_filename(filename)}")
    print(f"regenerated {written} golden(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
