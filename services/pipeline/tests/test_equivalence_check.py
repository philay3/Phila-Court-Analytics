"""Tests for the baseline equivalence run (Task 17.3).

Synthetic data only: extraction and parse are monkeypatched, so no real PDF or
docket ever appears. Corpus ``*.pdf`` files hold placeholder bytes purely so
the run's directory scan and per-file hashing have something to read; their
parsed records are supplied by the fake parser. All output goes to pytest
``tmp_path``; nothing touches ``~/court-data/``. Docket numbers are fictional
(``CP/MC-51-CR-000000N-2024``); the sentinel value below is invented text used
to prove field values never reach the console.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline import cli, equivalence_check
from pipeline.equivalence_check import (
    DEFENDANT_HASH_PATH,
    KIND_LIST_LENGTH,
    KIND_VALUE,
    REASON_PARSE_ERROR,
    REASON_PRIVACY_ASSERTION,
    REASON_UNEXPECTED_EXCEPTION,
    SALT_MODE_COMPARED,
    SALT_MODE_EXCLUDED,
    STATUS_BASELINE_MISSING,
    STATUS_CORPUS_MISSING,
    STATUS_DIVERGENT,
    STATUS_EQUIVALENT,
    STATUS_EXTRACTION_FAILED,
    STATUS_PARSE_FAILED,
    BaselineError,
    diff_records,
    load_baseline,
    run_equivalence_check,
)
from pipeline.extraction import (
    STATUS_FAILED as EXTRACTION_STATUS_FAILED,
)
from pipeline.extraction import (
    STATUS_SUCCESS,
    ExtractionResult,
)
from pipeline.helpers import ParseError

TEST_SALT = "test-salt"
# Invented value: if it reaches stdout/stderr the privacy test fails.
SENTINEL = "SYNTHETIC-FIELD-VALUE-XYZZY"


def _record(
    docket_number: str,
    *,
    court_type: str = "Common Pleas",
    min_days: int | None = 90,
    defendant_hash: str = "hash-A",
    assigned_judge_raw: str = "Judge Example",
    parsed_at: str = "2020-01-01T00:00:00",
    parser_version: int = 1,
    n_charges: int = 1,
) -> dict:
    """A record shaped like the 17.2 contract, enough for the diff to bite."""
    charges = [
        {
            "sequence": i + 1,
            "statute": "18 § 2701",
            "sentences": [{"sentence_type": "Confinement", "min_days": min_days}],
        }
        for i in range(n_charges)
    ]
    return {
        "docket_number": docket_number,
        "parser_version": parser_version,
        "parsed_at": parsed_at,
        "case": {
            "county": "Philadelphia",
            "court_type": court_type,
            "assigned_judge_raw": assigned_judge_raw,
            "defendant_hash": defendant_hash,
        },
        "charges": charges,
        "related_cases": [],
        "notes": [],
    }


class _Harness:
    """Builds corpus/baseline/output dirs and a fake extract+parse under
    tmp_path, then runs the comparator."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        self.corpus = tmp_path / "corpus"
        self.baseline_dir = tmp_path / "baseline"
        self.output = tmp_path / "out"
        self.corpus.mkdir()
        self.baseline_dir.mkdir()
        self._parsed: dict[str, object] = {}  # docket -> record | Exception
        self._extract_fails: set[str] = set()
        self._monkeypatch = monkeypatch
        monkeypatch.setattr(equivalence_check, "extract", self._fake_extract)
        monkeypatch.setattr(equivalence_check, "parse_docket_checked", self._fake_parse)

    def add_corpus(self, docket_number: str) -> None:
        (self.corpus / f"{docket_number}.pdf").write_bytes(b"%PDF-1.4 synthetic")

    def add_baseline(self, record: dict) -> None:
        path = self.baseline_dir / f"{record['docket_number']}.json"
        path.write_text(json.dumps(record))

    def set_parsed(self, docket_number: str, record_or_exc: object) -> None:
        self._parsed[docket_number] = record_or_exc

    def set_extract_fails(self, docket_number: str) -> None:
        self._extract_fails.add(docket_number)

    def _fake_extract(self, pdf_path: Path) -> ExtractionResult:
        if pdf_path.stem in self._extract_fails:
            return ExtractionResult(
                status=EXTRACTION_STATUS_FAILED,
                error={"code": "unreadable_pdf", "message": "synthetic"},
            )
        return ExtractionResult(
            status=STATUS_SUCCESS,
            page_texts=["synthetic page"],
            page_count=1,
            per_page_chars=[14],
        )

    def _fake_parse(
        self, docket_number: str, pages_text: list[str], *, salt: str
    ) -> tuple[dict, list[str], list[dict[str, object]]]:
        assert salt == TEST_SALT
        outcome = self._parsed[docket_number]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome, [], []

    def run(self, *, salt_parity_confirmed: bool = False, extra=None) -> int:
        return run_equivalence_check(
            self.corpus,
            self.baseline_dir,
            self.output,
            salt=TEST_SALT,
            salt_parity_confirmed=salt_parity_confirmed,
            extra_exclusions=extra or [],
        )

    def json_report(self) -> dict:
        return json.loads((self.output / "equivalence-report.json").read_text())

    def txt_report(self) -> str:
        return (self.output / "equivalence-report.txt").read_text()


def _docket(report: dict, docket_number: str) -> dict:
    return next(d for d in report["dockets"] if d["docket_number"] == docket_number)


# --- diff algorithm ---------------------------------------------------------


def test_diff_detects_nested_scalar_divergence():
    base = _record("CP-51-CR-0000001-2024", min_days=90)
    corpus = _record("CP-51-CR-0000001-2024", min_days=120)
    (divergence,) = diff_records(base, corpus, exclusions=set())
    assert divergence["path"] == "charges[0].sentences[0].min_days"
    assert divergence["kind"] == KIND_VALUE
    assert divergence["baseline"] == 90
    assert divergence["corpus"] == 120


def test_diff_list_length_records_surplus_with_values():
    base = _record("CP-51-CR-0000002-2024", n_charges=1)
    corpus = _record("CP-51-CR-0000002-2024", n_charges=2)
    divergences = diff_records(base, corpus, exclusions=set())
    length = next(d for d in divergences if d["kind"] == KIND_LIST_LENGTH)
    assert length["path"] == "charges"
    assert length["baseline_len"] == 1
    assert length["corpus_len"] == 2
    # The surplus element is recoverable, values included (JSON report only).
    assert length["surplus_in_corpus"][0]["sequence"] == 2


def test_diff_list_length_records_missing_from_corpus():
    base = _record("CP-51-CR-0000003-2024", n_charges=2)
    corpus = _record("CP-51-CR-0000003-2024", n_charges=1)
    length = next(
        d
        for d in diff_records(base, corpus, exclusions=set())
        if d["kind"] == KIND_LIST_LENGTH
    )
    assert length["missing_from_corpus"][0]["sequence"] == 2


def test_diff_excludes_parsed_at_and_parser_version_by_default():
    base = _record("CP-51-CR-0000004-2024", parsed_at="2020-01-01T00:00:00")
    corpus = _record("CP-51-CR-0000004-2024", parsed_at="2025-05-05T12:00:00")
    corpus["parser_version"] = 2
    assert diff_records(base, corpus, exclusions={"parsed_at", "parser_version"}) == []


def test_diff_respects_extra_exclusion_path():
    base = _record("CP-51-CR-0000005-2024", assigned_judge_raw="A")
    corpus = _record("CP-51-CR-0000005-2024", assigned_judge_raw="B")
    assert diff_records(base, corpus, exclusions={"case.assigned_judge_raw"}) == []


def test_diff_excludes_defendant_hash_at_verified_path():
    # The exclusion constant matches the real 17.2 field path.
    base = _record("CP-51-CR-0000006-2024", defendant_hash="hash-A")
    corpus = _record("CP-51-CR-0000006-2024", defendant_hash="hash-B")
    assert diff_records(base, corpus, exclusions={DEFENDANT_HASH_PATH}) == []
    # And without the exclusion, the hash divergence is caught at that path.
    (divergence,) = diff_records(base, corpus, exclusions=set())
    assert divergence["path"] == DEFENDANT_HASH_PATH == "case.defendant_hash"


# --- 18.4 held-charge value-verification gate -------------------------------


def _held_record(docket_number: str, *, event_date: object, event_name: object) -> dict:
    """A record whose single charge is HELD (carries event keys, no disposition).

    A held charge is identified by event-key PRESENCE, so both keys are always
    present here; their VALUES are what the gate verifies.
    """
    record = _record(docket_number, n_charges=1)
    record["charges"][0].update(
        {"event_date": event_date, "event_name": event_name, "sentences": []}
    )
    return record


def test_held_value_gate_passes_when_event_date_and_name_populated(
    tmp_path, monkeypatch
):
    h = _Harness(tmp_path, monkeypatch)
    rec = _held_record(
        "CP-51-CR-0000010-2024", event_date="2024-06-15", event_name="Held for Court"
    )
    h.add_corpus(rec["docket_number"])
    h.add_baseline(rec)  # identical baseline -> equivalent, gate still evaluates
    h.set_parsed(rec["docket_number"], rec)
    code = h.run()
    gate = h.json_report()["held_value_gate"]
    assert gate["pass"] is True
    assert gate["held_charges_total"] == 1
    assert gate["held_charges_populated"] == 1
    assert gate["held_charges_violations"] == 0
    assert gate["event_name_vocab_size"] == 1
    assert code == 0  # reconciled + gate pass


def test_held_value_gate_fails_on_null_event_date(tmp_path, monkeypatch):
    h = _Harness(tmp_path, monkeypatch)
    rec = _held_record(
        "CP-51-CR-0000011-2024", event_date=None, event_name="Held for Court"
    )
    h.add_corpus(rec["docket_number"])
    h.add_baseline(rec)
    h.set_parsed(rec["docket_number"], rec)
    code = h.run()
    gate = h.json_report()["held_value_gate"]
    assert gate["pass"] is False
    assert gate["held_charges_violations"] == 1
    assert "HELD-CHARGE VALUE GATE (18.4): FAIL" in h.txt_report()
    assert code == 1  # fail-loud even though totals reconcile


def test_held_value_gate_fails_on_unparseable_event_date(tmp_path, monkeypatch):
    h = _Harness(tmp_path, monkeypatch)
    rec = _held_record(
        "CP-51-CR-0000012-2024", event_date="not-a-date", event_name="Held for Court"
    )
    h.add_corpus(rec["docket_number"])
    h.add_baseline(rec)
    h.set_parsed(rec["docket_number"], rec)
    assert h.run() == 1
    assert h.json_report()["held_value_gate"]["held_charges_violations"] == 1


def test_held_value_gate_fails_on_empty_event_name(tmp_path, monkeypatch):
    h = _Harness(tmp_path, monkeypatch)
    rec = _held_record("CP-51-CR-0000013-2024", event_date="2024-06-15", event_name="")
    h.add_corpus(rec["docket_number"])
    h.add_baseline(rec)
    h.set_parsed(rec["docket_number"], rec)
    assert h.run() == 1
    assert h.json_report()["held_value_gate"]["held_charges_violations"] == 1


# --- 18.5 UN-DISPOSAL check -------------------------------------------------


def test_undisposed_regressions_flags_only_present_and_undisposed():
    """Disposed-in-baseline / undisposed-in-corpus is flagged; a charge held in
    BOTH (not a regression) and a baseline-disposed charge ABSENT from the corpus
    (a separate charge-count divergence) are NOT counted."""
    baseline = {
        "charges": [
            {"sequence": 1, "disposition_raw": "ARD - County"},  # disposed
            {"sequence": 2, "disposition_raw": None},  # held in baseline too
            {"sequence": 3, "disposition_raw": "Guilty"},  # disposed, missing below
        ]
    }
    corpus = {
        "charges": [
            {"sequence": 1, "disposition_raw": None, "disposition_date": None},
            {"sequence": 2, "disposition_raw": None},
        ]
    }
    assert equivalence_check._undisposed_regressions(baseline, corpus) == [1]


def test_undisposed_regressions_empty_when_disposed_in_both():
    baseline = {"charges": [{"sequence": 1, "disposition_date": "2025-03-10"}]}
    corpus = {"charges": [{"sequence": 1, "disposition_raw": "ARD - County"}]}
    assert equivalence_check._undisposed_regressions(baseline, corpus) == []


def test_un_disposal_gate_fails_and_exits_nonzero(tmp_path, monkeypatch):
    """A charge disposed in the baseline but left undisposed (held) by the corpus
    parse — the 18.4 ARD regression — trips the always-fail UN-DISPOSAL category
    and returns a non-zero exit, distinct from generic field divergences."""
    h = _Harness(tmp_path, monkeypatch)
    dk = "CP-51-CR-0000020-2024"
    baseline = _record(dk)
    baseline["charges"][0].update(
        {"disposition_raw": "ARD - County", "disposition_date": "2025-03-10"}
    )
    corpus = _record(dk)
    corpus["charges"][0].update(
        {
            "disposition_raw": None,
            "disposition_date": None,
            "disposition_judge_raw": None,
            "event_date": "2025-03-10",
            "event_name": "Status",
        }
    )
    h.add_corpus(dk)
    h.add_baseline(baseline)
    h.set_parsed(dk, corpus)
    code = h.run()
    undisposal = h.json_report()["un_disposal"]
    assert undisposal["pass"] is False
    assert undisposal["charges"] == 1
    assert undisposal["dockets"] == 1
    assert "UN-DISPOSAL CHECK (18.5): FAIL" in h.txt_report()
    assert code == 1


def test_held_value_gate_reports_distinct_vocab_size_and_never_leaks_names(
    tmp_path, monkeypatch
):
    h = _Harness(tmp_path, monkeypatch)
    # Two dockets, two distinct event names (+ a case-variant that must dedupe).
    specs = [
        ("CP-51-CR-0000014-2024", "Held for Court"),
        ("CP-51-CR-0000015-2024", "Waiver of Preliminary Hearing"),
        ("CP-51-CR-0000016-2024", "held for court"),  # same as #1, normalized
    ]
    for docket, name in specs:
        rec = _held_record(docket, event_date="2024-06-15", event_name=name)
        h.add_corpus(docket)
        h.add_baseline(rec)
        h.set_parsed(docket, rec)
    code = h.run()
    gate = h.json_report()["held_value_gate"]
    assert gate["pass"] is True
    assert gate["held_charges_total"] == 3
    assert gate["event_name_vocab_size"] == 2  # case-normalized dedupe
    assert code == 0
    # Privacy: the size is reported, the event-name strings are not written.
    assert "Waiver of Preliminary Hearing" not in h.txt_report()
    assert "Waiver of Preliminary Hearing" not in json.dumps(h.json_report())


def test_held_value_gate_pass_when_no_held_charges(tmp_path, monkeypatch):
    """A corpus with only terminal charges has zero held charges — the gate
    passes vacuously (no violations) and reports a zero vocabulary."""
    h = _Harness(tmp_path, monkeypatch)
    rec = _record("CP-51-CR-0000017-2024", n_charges=1)  # no event keys
    h.add_corpus(rec["docket_number"])
    h.add_baseline(rec)
    h.set_parsed(rec["docket_number"], rec)
    code = h.run()
    gate = h.json_report()["held_value_gate"]
    assert gate["pass"] is True
    assert gate["held_charges_total"] == 0
    assert gate["event_name_vocab_size"] == 0
    assert code == 0


# --- baseline loading -------------------------------------------------------


def test_load_baseline_single_object_and_list_shapes(tmp_path):
    base_dir = tmp_path / "baseline"
    base_dir.mkdir()
    (base_dir / "a.json").write_text(json.dumps(_record("CP-51-CR-0000007-2024")))
    (base_dir / "batch.json").write_text(
        json.dumps([_record("MC-51-CR-0000008-2024"), _record("CP-51-CR-0000009-2024")])
    )
    loaded = load_baseline(base_dir)
    assert loaded.records_loaded == 3
    assert set(loaded.index) == {
        "CP-51-CR-0000007-2024",
        "MC-51-CR-0000008-2024",
        "CP-51-CR-0000009-2024",
    }


def test_load_baseline_rejects_non_record_root(tmp_path):
    base_dir = tmp_path / "baseline"
    base_dir.mkdir()
    (base_dir / "bad.json").write_text(json.dumps("not a record"))
    with pytest.raises(BaselineError):
        load_baseline(base_dir)


def test_load_baseline_flags_duplicates_and_skips_recordless(tmp_path):
    base_dir = tmp_path / "baseline"
    base_dir.mkdir()
    (base_dir / "one.json").write_text(json.dumps(_record("CP-51-CR-0000010-2024")))
    (base_dir / "dup.json").write_text(json.dumps(_record("CP-51-CR-0000010-2024")))
    (base_dir / "noise.json").write_text(json.dumps({"unrelated": True}))
    loaded = load_baseline(base_dir)
    assert loaded.duplicate_dockets == ["CP-51-CR-0000010-2024"]
    assert loaded.skipped == 1


def test_empty_baseline_refuses_to_run(tmp_path, monkeypatch):
    harness = _Harness(tmp_path, monkeypatch)
    harness.add_corpus("CP-51-CR-0000011-2024")
    # No baseline records at all.
    assert harness.run() == 2
    assert not harness.output.exists()


# --- status classification & reconciliation ---------------------------------


def test_equivalent_and_divergent_classification(tmp_path, monkeypatch):
    harness = _Harness(tmp_path, monkeypatch)
    same = "CP-51-CR-0000012-2024"
    diff = "CP-51-CR-0000013-2024"
    harness.add_corpus(same)
    harness.add_baseline(_record(same, min_days=90))
    harness.set_parsed(same, _record(same, min_days=90))
    harness.add_corpus(diff)
    harness.add_baseline(_record(diff, min_days=90))
    harness.set_parsed(diff, _record(diff, min_days=180))

    assert harness.run() == 0
    report = harness.json_report()
    assert report["totals"][STATUS_EQUIVALENT] == 1
    assert report["totals"][STATUS_DIVERGENT] == 1
    assert _docket(report, diff)["divergences"][0]["path"] == (
        "charges[0].sentences[0].min_days"
    )


def test_baseline_missing_and_corpus_missing_reconcile_both_directions(
    tmp_path, monkeypatch
):
    harness = _Harness(tmp_path, monkeypatch)
    matched_cp = "CP-51-CR-0000014-2024"
    matched_mc = "MC-51-CR-0000015-2024"
    no_baseline = "CP-51-CR-0000016-2024"  # corpus PDF, no baseline record
    no_corpus = "MC-51-CR-0000017-2024"  # baseline record, no corpus PDF

    for docket, court in (
        (matched_cp, "Common Pleas"),
        (matched_mc, "Municipal Court"),
    ):
        harness.add_corpus(docket)
        harness.add_baseline(_record(docket, court_type=court))
        harness.set_parsed(docket, _record(docket, court_type=court))
    harness.add_corpus(no_baseline)
    harness.set_parsed(no_baseline, _record(no_baseline))  # never reached
    harness.add_baseline(_record(no_corpus, court_type="Municipal Court"))

    assert harness.run() == 0
    report = harness.json_report()
    totals = report["totals"]
    assert totals[STATUS_EQUIVALENT] == 2
    assert totals[STATUS_BASELINE_MISSING] == 1
    assert totals[STATUS_CORPUS_MISSING] == 1
    # Reconciliation asserted by the comparator and recorded in the header.
    assert report["header"]["reconciled"] is True
    # corpus PDFs (3) = equivalent(2) + baseline_missing(1); baseline (3) =
    # matched(2) + corpus_missing(1).
    assert report["header"]["corpus_pdf_count"] == 3
    assert report["header"]["baseline_unique_dockets"] == 3
    # Per-court split keeps MC visible, never blended.
    assert report["by_court"]["MC"][STATUS_CORPUS_MISSING] == 1
    assert report["by_court"]["CP"][STATUS_BASELINE_MISSING] == 1


def test_extraction_failure_recorded(tmp_path, monkeypatch):
    harness = _Harness(tmp_path, monkeypatch)
    docket = "CP-51-CR-0000018-2024"
    harness.add_corpus(docket)
    harness.add_baseline(_record(docket))
    harness.set_extract_fails(docket)
    harness.set_parsed(docket, _record(docket))  # never reached

    assert harness.run() == 0
    assert harness.json_report()["totals"][STATUS_EXTRACTION_FAILED] == 1


# --- per-docket exception capture -------------------------------------------


def test_parse_exception_does_not_abort_run(tmp_path, monkeypatch):
    harness = _Harness(tmp_path, monkeypatch)
    poison = "CP-51-CR-0000019-2024"
    good = "CP-51-CR-0000020-2024"
    harness.add_corpus(poison)
    harness.add_baseline(_record(poison))
    harness.set_parsed(poison, ParseError("synthetic parse failure"))
    harness.add_corpus(good)
    harness.add_baseline(_record(good))
    harness.set_parsed(good, _record(good))

    assert harness.run() == 0
    report = harness.json_report()
    assert _docket(report, poison)["reason"] == REASON_PARSE_ERROR
    assert _docket(report, poison)["exception_type"] == "ParseError"
    # The docket after the poisoned one still processed to completion.
    assert report["totals"][STATUS_EQUIVALENT] == 1


def test_privacy_assertion_is_distinct_parse_failure(tmp_path, monkeypatch):
    harness = _Harness(tmp_path, monkeypatch)
    docket = "CP-51-CR-0000021-2024"
    harness.add_corpus(docket)
    harness.add_baseline(_record(docket))
    harness.set_parsed(docket, RuntimeError("privacy assertion failed"))

    assert harness.run() == 0
    entry = _docket(harness.json_report(), docket)
    assert entry["status"] == STATUS_PARSE_FAILED
    assert entry["reason"] == REASON_PRIVACY_ASSERTION
    assert entry["exception_type"] == "RuntimeError"


def test_unexpected_exception_recorded_as_parse_failed(tmp_path, monkeypatch):
    harness = _Harness(tmp_path, monkeypatch)
    docket = "CP-51-CR-0000022-2024"
    harness.add_corpus(docket)
    harness.add_baseline(_record(docket))
    harness.set_parsed(docket, KeyError("unsupported disposition layout"))

    assert harness.run() == 0
    entry = _docket(harness.json_report(), docket)
    assert entry["status"] == STATUS_PARSE_FAILED
    assert entry["reason"] == REASON_UNEXPECTED_EXCEPTION
    assert entry["exception_type"] == "KeyError"


# --- salt parity mode -------------------------------------------------------


def test_salt_parity_unconfirmed_excludes_hash_and_states_mode(tmp_path, monkeypatch):
    harness = _Harness(tmp_path, monkeypatch)
    docket = "CP-51-CR-0000023-2024"
    harness.add_corpus(docket)
    harness.add_baseline(_record(docket, defendant_hash="hash-A"))
    # Hash differs, but parity unconfirmed -> excluded -> still equivalent.
    harness.set_parsed(docket, _record(docket, defendant_hash="hash-B"))

    assert harness.run(salt_parity_confirmed=False) == 0
    report = harness.json_report()
    assert report["totals"][STATUS_EQUIVALENT] == 1
    header = report["header"]
    assert header["salt_parity_mode"] == SALT_MODE_EXCLUDED
    assert header["salt_parity_confirmed"] is False
    assert DEFENDANT_HASH_PATH in header["excluded_fields"]
    assert SALT_MODE_EXCLUDED in harness.txt_report()


def test_salt_parity_confirmed_compares_hash(tmp_path, monkeypatch):
    harness = _Harness(tmp_path, monkeypatch)
    docket = "CP-51-CR-0000024-2024"
    harness.add_corpus(docket)
    harness.add_baseline(_record(docket, defendant_hash="hash-A"))
    harness.set_parsed(docket, _record(docket, defendant_hash="hash-B"))

    assert harness.run(salt_parity_confirmed=True) == 0
    report = harness.json_report()
    assert report["totals"][STATUS_DIVERGENT] == 1
    header = report["header"]
    assert header["salt_parity_mode"] == SALT_MODE_COMPARED
    assert DEFENDANT_HASH_PATH not in header["excluded_fields"]


# --- privacy: no field values in console ------------------------------------


def test_no_field_values_or_salt_in_console(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setenv("DEFENDANT_HASH_SALT", TEST_SALT)
    harness = _Harness(tmp_path, monkeypatch)
    docket = "MC-51-CR-0009999-2024"
    harness.add_corpus(docket)
    harness.add_baseline(_record(docket, assigned_judge_raw="Judge Example"))
    # A divergence whose corpus value carries the sentinel.
    harness.set_parsed(docket, _record(docket, assigned_judge_raw=SENTINEL))

    assert (
        cli.main(
            [
                "equivalence-check",
                "--corpus-dir",
                str(harness.corpus),
                "--baseline-dir",
                str(harness.baseline_dir),
                "--output-dir",
                str(harness.output),
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    for stream in (captured.out, captured.err):
        assert SENTINEL not in stream  # field value never leaves the report
        assert TEST_SALT not in stream  # salt never printed
    # The value does reach the out-of-repo JSON report...
    assert SENTINEL in (harness.output / "equivalence-report.json").read_text()
    # ...but not the human-readable summary (paths only).
    assert SENTINEL not in harness.txt_report()


# --- run-boundary guards ----------------------------------------------------


def test_output_dir_inside_git_worktree_rejected(tmp_path, monkeypatch):
    harness = _Harness(tmp_path, monkeypatch)
    docket = "CP-51-CR-0000025-2024"
    harness.add_corpus(docket)
    harness.add_baseline(_record(docket))
    harness.set_parsed(docket, _record(docket))
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)

    assert (
        run_equivalence_check(
            harness.corpus,
            harness.baseline_dir,
            repo / "out",
            salt=TEST_SALT,
            salt_parity_confirmed=False,
            extra_exclusions=[],
        )
        == 2
    )
    assert not (repo / "out").exists()


def test_ci_environment_refuses_run(tmp_path, monkeypatch):
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("DEFENDANT_HASH_SALT", TEST_SALT)
    harness = _Harness(tmp_path, monkeypatch)
    harness.add_corpus("CP-51-CR-0000026-2024")

    assert (
        cli.main(
            [
                "equivalence-check",
                "--corpus-dir",
                str(harness.corpus),
                "--baseline-dir",
                str(harness.baseline_dir),
                "--output-dir",
                str(harness.output),
            ]
        )
        == 2
    )
    assert not harness.output.exists()


def test_missing_salt_refuses_run(tmp_path, monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("DEFENDANT_HASH_SALT", raising=False)
    harness = _Harness(tmp_path, monkeypatch)
    harness.add_corpus("CP-51-CR-0000027-2024")

    assert (
        cli.main(
            [
                "equivalence-check",
                "--corpus-dir",
                str(harness.corpus),
                "--baseline-dir",
                str(harness.baseline_dir),
                "--output-dir",
                str(harness.output),
            ]
        )
        == 2
    )
    assert not harness.output.exists()


def test_cli_defaults_under_court_data():
    parser = cli.build_parser()
    args = parser.parse_args(["equivalence-check"])
    home = Path.home()
    assert args.corpus_dir == home / "court-data" / "fixtures"
    assert args.baseline_dir == home / "court-data" / "capstone-baseline"
    assert args.output_dir == home / "court-data" / "equivalence"
    assert args.exclude_fields == []
    assert args.salt_parity_confirmed is False
