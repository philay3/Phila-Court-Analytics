"""Tests for the ``run-fixtures`` command (Task 19.2).

Synthetic/temp only — NOTHING here reads or writes ``~/court-data/`` or opens a
real PDF. Tier-2 extraction and parsing are monkeypatched (the 17.3 precedent),
so corpus ``*.pdf`` files hold placeholder bytes purely to give the run
something to hash and iterate. Tier-1 assertions run against the committed
corpus through the public CLI, plus isolated orchestration tests over a
monkeypatched index/golden dir.

Privacy: the tier-2 console assertions prove field values never reach stdout.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from pipeline import cli
from pipeline import run_fixtures as rf
from pipeline.extraction import STATUS_FAILED, STATUS_SUCCESS, ExtractionResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _record(docket_number: str = "MC-51-CR-0000000-2025") -> dict:
    return {
        "docket_number": docket_number,
        "parser_version": 2,
        "parsed_at": "2026-01-01T00:00:00",  # dropped by the projection
        "case": {"defendant_hash": "deadbeef", "court_type": "Municipal Court"},
        "charges": [{"sequence": 1, "offense": "Placeholder Offense", "sentences": []}],
        "notes": [],
        "related_cases": [],
    }


_DEFAULT_RECORD = object()  # sentinel: distinguish "omitted" from explicit None


def _envelope(
    *,
    status: str = "parsed",
    record=_DEFAULT_RECORD,
    warnings: list | None = None,
    review_needed: bool = False,
    error: dict | None = None,
) -> dict:
    """A full ``parse_document``-shaped envelope, including the fields the golden
    projection is supposed to drop."""
    return {
        "source_sha256": "placeholder",
        "parser_version": 7,  # envelope wrapper version — dropped
        "extraction_artifact": {"artifact_id": "x", "text_hash": None},  # dropped
        "record": _record() if record is _DEFAULT_RECORD else record,
        "warnings": warnings or [],
        "review_needed": review_needed,
        "status": status,
        "created_at": "2026-01-01T00:00:00+00:00",  # dropped
        "error": error,
    }


class _Tier2Harness:
    """Fake corpus + monkeypatched extract/parse_document under tmp_path."""

    def __init__(self, tmp_path, monkeypatch):
        self.corpus = tmp_path / "corpus"
        self.corpus.mkdir()
        self.output = tmp_path / "out"
        self._extract_results: dict[str, ExtractionResult] = {}
        self._envelopes: dict[str, dict] = {}
        self._raises: set[str] = set()
        monkeypatch.setattr(rf, "extract", self._extract)
        monkeypatch.setattr(rf, "parse_document", self._parse)

    def add_pdf(self, stem, *, envelope=None, extract_result=None, raises=False):
        (self.corpus / f"{stem}.pdf").write_bytes(
            b"%PDF-1.4 synthetic " + stem.encode()
        )
        if extract_result is not None:
            self._extract_results[stem] = extract_result
        if envelope is not None:
            self._envelopes[stem] = envelope
        if raises:
            self._raises.add(stem)

    def sha(self, stem) -> str:
        return rf._source_hash(self.corpus / f"{stem}.pdf")

    def golden_path(self, stem):
        return self.output / f"{self.sha(stem)}.json"

    def write_golden(self, stem, projection: dict) -> None:
        self.output.mkdir(parents=True, exist_ok=True)
        self.golden_path(stem).write_text(rf.golden_bytes(projection))

    def projection_for(self, stem) -> dict:
        return rf.project_envelope(self._envelopes.get(stem, _envelope()))

    def _extract(self, pdf_path):
        if pdf_path.stem in self._extract_results:
            return self._extract_results[pdf_path.stem]
        return ExtractionResult(
            status=STATUS_SUCCESS, page_texts=["page text"], text_hash="th"
        )

    def _parse(
        self,
        docket_number,
        pages_text,
        *,
        source_sha256,
        text_hash,
        provenance_path,
        extraction_status,
        salt,
    ):
        if docket_number in self._raises:
            raise RuntimeError("synthetic parse crash")
        return dict(self._envelopes.get(docket_number, _envelope()))

    def run(self, update_goldens=False, init_goldens=False) -> int:
        return rf.run_tier2(
            self.corpus,
            self.output,
            salt="realsalt",
            init_goldens=init_goldens,
            update_goldens=update_goldens,
        )

    def reports(self) -> list:
        return sorted((self.output / "reports").glob("tier2-report-*.json"))

    def report(self) -> dict:
        return json.loads(self.reports()[-1].read_text())


# ---------------------------------------------------------------------------
# project_envelope — the shared projection
# ---------------------------------------------------------------------------


def test_projection_drops_wrapper_fields_keeps_record_parser_version():
    projected = rf.project_envelope(_envelope())
    assert set(projected) == {"status", "record", "warnings", "review_needed", "error"}
    # Record's own parser_version stays visible; parsed_at is dropped.
    assert projected["record"]["parser_version"] == 2
    assert "parsed_at" not in projected["record"]


def test_projection_failed_arm_has_null_record():
    env = _envelope(
        status="failed",
        record=None,
        error={"code": "unsupported_format", "exception_class": "KeyError"},
    )
    projected = rf.project_envelope(env)
    assert projected["record"] is None
    assert projected["status"] == "failed"


# ---------------------------------------------------------------------------
# Tier 1 — always runs, every write gated by --update-goldens
# ---------------------------------------------------------------------------


def test_tier1_no_args_matches_committed_goldens():
    # Full end-to-end through the real parser + committed corpus.
    assert cli.main(["run-fixtures"]) == 0


def _stub_tier1(monkeypatch, tmp_path, *, golden: dict, existing: dict | None):
    """Point tier-1 at a one-entry temp corpus with a canned build_golden."""
    goldens = tmp_path / "goldens"
    goldens.mkdir()
    monkeypatch.setattr(rf, "GOLDENS_DIR", goldens)
    monkeypatch.setattr(
        rf,
        "_load_index",
        lambda: {
            "fixtures": [{"filename": "f_mc.txt", "court_type": "Municipal Court"}]
        },
    )
    monkeypatch.setattr(rf, "load_fixture_pages", lambda _f: ["page"])
    monkeypatch.setattr(rf, "build_golden", lambda _d, _p: golden)
    path = goldens / "f_mc.json"
    if existing is not None:
        path.write_text(rf.golden_bytes(existing))
    return path


def test_tier1_missing_golden_without_flag_refuses(monkeypatch, tmp_path):
    golden = {
        "status": "parsed",
        "record": None,
        "warnings": [],
        "review_needed": False,
        "error": None,
    }
    path = _stub_tier1(monkeypatch, tmp_path, golden=golden, existing=None)

    result = rf.run_tier1(update_goldens=False)

    assert [e.status for e in result.entries] == [rf.T1_MISSING]
    assert result.failed_run is True
    assert not path.exists()  # never written without the flag


def test_tier1_missing_golden_with_flag_creates(monkeypatch, tmp_path):
    golden = {
        "status": "parsed",
        "record": None,
        "warnings": [],
        "review_needed": False,
        "error": None,
    }
    path = _stub_tier1(monkeypatch, tmp_path, golden=golden, existing=None)

    result = rf.run_tier1(update_goldens=True)

    assert [e.status for e in result.entries] == [rf.T1_NEW]
    assert result.failed_run is False
    assert json.loads(path.read_text()) == golden


def test_tier1_diverged_without_flag_reports_and_does_not_write(monkeypatch, tmp_path):
    fresh = {
        "status": "parsed",
        "record": {"a": 1},
        "warnings": [],
        "review_needed": False,
        "error": None,
    }
    stale = {
        "status": "parsed",
        "record": {"a": 2},
        "warnings": [],
        "review_needed": False,
        "error": None,
    }
    path = _stub_tier1(monkeypatch, tmp_path, golden=fresh, existing=stale)

    result = rf.run_tier1(update_goldens=False)

    assert [e.status for e in result.entries] == [rf.T1_DIVERGED]
    assert result.failed_run is True
    assert json.loads(path.read_text()) == stale  # untouched


def test_tier1_diverged_with_flag_updates(monkeypatch, tmp_path):
    fresh = {
        "status": "parsed",
        "record": {"a": 1},
        "warnings": [],
        "review_needed": False,
        "error": None,
    }
    stale = {
        "status": "parsed",
        "record": {"a": 2},
        "warnings": [],
        "review_needed": False,
        "error": None,
    }
    path = _stub_tier1(monkeypatch, tmp_path, golden=fresh, existing=stale)

    result = rf.run_tier1(update_goldens=True)

    assert [e.status for e in result.entries] == [rf.T1_UPDATED]
    assert result.failed_run is False
    assert json.loads(path.read_text()) == fresh


# ---------------------------------------------------------------------------
# Tier 2 — real-corpus drift, goldens outside the repo
# ---------------------------------------------------------------------------


def test_tier2_missing_without_flag_reports_not_writes(tmp_path, monkeypatch):
    # 19.3 contract: no golden-writing flag NEVER writes a golden, even for a
    # first-seen docket. Present-golden dockets are still compared in the same
    # run (per-docket isolation — one missing golden never aborts the corpus).
    h = _Tier2Harness(tmp_path, monkeypatch)
    h.add_pdf("mc_present")
    h.write_golden("mc_present", h.projection_for("mc_present"))
    h.add_pdf("mc_absent")

    rc = h.run(update_goldens=False)  # no golden-writing flag

    assert rc == 1  # a missing golden fails the run
    totals = h.report()["totals"]
    assert totals[rf.T2_MISSING] == 1
    assert totals[rf.T2_MATCH] == 1  # present-golden docket still compared
    # Zero golden files written for the absent docket — filesystem assertion.
    assert not h.golden_path("mc_absent").exists()


def test_tier2_init_writes_only_absent(tmp_path, monkeypatch):
    # --init-goldens establishes ONLY absent goldens; existing ones are untouched.
    h = _Tier2Harness(tmp_path, monkeypatch)
    h.add_pdf("mc_present")
    h.write_golden("mc_present", h.projection_for("mc_present"))
    present_before = h.golden_path("mc_present").read_text()
    h.add_pdf("mc_absent")

    rc = h.run(init_goldens=True)

    assert rc == 0  # establishment is a clean run
    totals = h.report()["totals"]
    assert totals[rf.T2_NEW] == 1
    assert totals[rf.T2_MATCH] == 1
    # The absent golden is now written with the expected projection...
    assert json.loads(h.golden_path("mc_absent").read_text()) == h.projection_for(
        "mc_absent"
    )
    # ...and the pre-existing golden is left byte-identical.
    assert h.golden_path("mc_present").read_text() == present_before


def test_tier2_init_does_not_overwrite_existing_divergent(tmp_path, monkeypatch):
    # Least privilege: --init-goldens covers absent only; a divergent existing
    # golden is reported, never silently clobbered.
    h = _Tier2Harness(tmp_path, monkeypatch)
    h.add_pdf("mc1", envelope=_envelope(record=_record("MC-51-CR-0000000-2025")))
    h.write_golden(
        "mc1", rf.project_envelope(_envelope(record=_record("MC-51-CR-0000001-2025")))
    )
    before = h.golden_path("mc1").read_text()

    rc = h.run(init_goldens=True)

    assert rc == 1
    assert h.report()["totals"][rf.T2_DIVERGED] == 1
    assert h.golden_path("mc1").read_text() == before  # not overwritten


def test_tier2_update_does_not_create_absent(tmp_path, monkeypatch):
    # Least privilege: --update-goldens covers existing only; an absent golden is
    # golden_missing (nonzero), never created.
    h = _Tier2Harness(tmp_path, monkeypatch)
    h.add_pdf("mc_absent")

    rc = h.run(update_goldens=True)

    assert rc == 1
    assert h.report()["totals"][rf.T2_MISSING] == 1
    assert not h.golden_path("mc_absent").exists()


def test_tier2_both_flags_write_absent_and_divergent(tmp_path, monkeypatch):
    # Combined flags = explicit full-write mode: absent created, divergent
    # refreshed, matching left alone.
    h = _Tier2Harness(tmp_path, monkeypatch)
    h.add_pdf("mc_absent")
    h.add_pdf("mc_div", envelope=_envelope(record=_record("MC-51-CR-0000000-2025")))
    fresh_div = h.projection_for("mc_div")
    h.write_golden(
        "mc_div",
        rf.project_envelope(_envelope(record=_record("MC-51-CR-0000001-2025"))),
    )
    h.add_pdf("mc_match")
    h.write_golden("mc_match", h.projection_for("mc_match"))

    rc = h.run(init_goldens=True, update_goldens=True)

    assert rc == 0
    totals = h.report()["totals"]
    assert totals[rf.T2_NEW] == 1
    assert totals[rf.T2_UPDATED] == 1
    assert totals[rf.T2_MATCH] == 1
    assert json.loads(h.golden_path("mc_absent").read_text()) == h.projection_for(
        "mc_absent"
    )
    assert json.loads(h.golden_path("mc_div").read_text()) == fresh_div


def test_tier2_report_is_run_unique_and_non_clobbering(tmp_path, monkeypatch):
    # Two consecutive runs → two distinct report files, and run one's report is
    # byte-identical afterward (names distinct + first content untouched).
    h = _Tier2Harness(tmp_path, monkeypatch)
    h.add_pdf("mc1")
    h.write_golden("mc1", h.projection_for("mc1"))
    stamps = iter(
        [
            datetime(2026, 7, 11, 16, 34, 12, 100000, tzinfo=UTC),
            datetime(2026, 7, 11, 16, 34, 12, 200000, tzinfo=UTC),
        ]
    )
    monkeypatch.setattr(rf, "_now_utc", lambda: next(stamps))

    assert h.run(update_goldens=False) == 0
    after_one = h.reports()
    assert len(after_one) == 1
    first = after_one[0]
    first_content = first.read_text()

    assert h.run(update_goldens=False) == 0
    after_two = h.reports()
    assert len(after_two) == 2  # distinct artifacts
    assert first.exists()
    assert first.read_text() == first_content  # run one's report untouched


def test_tier2_report_refuses_overwrite_on_timestamp_collision(tmp_path, monkeypatch):
    # Belt-and-suspenders: if the run-unique path somehow already exists, the run
    # refuses (rc 2) rather than clobbering the prior report.
    h = _Tier2Harness(tmp_path, monkeypatch)
    h.add_pdf("mc1")
    h.write_golden("mc1", h.projection_for("mc1"))
    fixed = datetime(2026, 7, 11, 16, 34, 12, 123456, tzinfo=UTC)
    monkeypatch.setattr(rf, "_now_utc", lambda: fixed)

    assert h.run(update_goldens=False) == 0
    assert h.run(update_goldens=False) == 2  # same timestamp → refuse
    assert len(h.reports()) == 1  # only the first survives


def test_tier2_match_is_clean(tmp_path, monkeypatch):
    h = _Tier2Harness(tmp_path, monkeypatch)
    h.add_pdf("mc1")
    h.write_golden("mc1", h.projection_for("mc1"))

    rc = h.run(update_goldens=False)

    assert rc == 0
    assert h.report()["totals"][rf.T2_MATCH] == 1


def test_tier2_diverged_without_flag_reports_not_writes(tmp_path, monkeypatch, capsys):
    h = _Tier2Harness(tmp_path, monkeypatch)
    secret_docket = "MC-51-CR-9999999-2025"
    h.add_pdf("mc1", envelope=_envelope(record=_record(secret_docket)))
    stale = h.projection_for("mc1")
    stored = rf.project_envelope(_envelope(record=_record("MC-51-CR-0000000-2025")))
    h.write_golden("mc1", stored)
    before = h.golden_path("mc1").read_text()

    rc = h.run(update_goldens=False)

    assert rc == 1
    assert h.report()["totals"][rf.T2_DIVERGED] == 1
    assert h.golden_path("mc1").read_text() == before  # not overwritten
    # The value-bearing diff is in the report file; assert it carries values.
    report_text = json.dumps(h.report())
    assert secret_docket in report_text
    # Console shows the field PATH but never the diverging value.
    out = capsys.readouterr().out
    assert "record.docket_number" in out
    assert secret_docket not in out
    assert stale["record"]["docket_number"] not in out


def test_tier2_diverged_with_flag_reports_updated_status(tmp_path, monkeypatch):
    h = _Tier2Harness(tmp_path, monkeypatch)
    h.add_pdf("mc1", envelope=_envelope(record=_record("MC-51-CR-0000000-2025")))
    fresh = h.projection_for("mc1")
    h.write_golden(
        "mc1", rf.project_envelope(_envelope(record=_record("MC-51-CR-0000001-2025")))
    )

    rc = h.run(update_goldens=True)

    assert rc == 0  # updated is not a failure
    totals = h.report()["totals"]
    assert totals[rf.T2_UPDATED] == 1  # distinct status, not folded into match
    assert totals[rf.T2_MATCH] == 0
    assert json.loads(h.golden_path("mc1").read_text()) == fresh  # overwritten


def test_tier2_extraction_failure_is_failed_nonzero_even_with_flag(
    tmp_path, monkeypatch
):
    h = _Tier2Harness(tmp_path, monkeypatch)
    h.add_pdf("mc1", extract_result=ExtractionResult(status=STATUS_FAILED))

    rc = h.run(update_goldens=True)

    assert rc == 1  # a refresh cannot absolve a failure
    assert h.report()["totals"][rf.T2_FAILED] == 1
    assert not h.golden_path("mc1").exists()


def test_tier2_parse_failed_envelope_is_failed(tmp_path, monkeypatch):
    h = _Tier2Harness(tmp_path, monkeypatch)
    h.add_pdf(
        "mc1",
        envelope=_envelope(
            status="failed",
            record=None,
            error={"code": "unsupported_format", "exception_class": "KeyError"},
        ),
    )

    rc = h.run(update_goldens=True)

    assert rc == 1
    entry = h.report()["dockets"][0]
    assert entry["status"] == rf.T2_FAILED
    assert entry["reason"] == rf.REASON_PARSE_FAILED
    assert not h.golden_path("mc1").exists()


def test_tier2_unexpected_exception_does_not_abort_run(tmp_path, monkeypatch):
    h = _Tier2Harness(tmp_path, monkeypatch)
    h.add_pdf("mc_bad", raises=True)
    h.add_pdf("mc_ok")
    h.write_golden("mc_ok", h.projection_for("mc_ok"))  # healthy docket has a golden

    rc = h.run(update_goldens=False)

    assert rc == 1
    totals = h.report()["totals"]
    assert totals[rf.T2_FAILED] == 1  # the crash was captured
    assert totals[rf.T2_MATCH] == 1  # the healthy docket still ran


def test_tier2_empty_corpus_refuses(tmp_path, monkeypatch):
    h = _Tier2Harness(tmp_path, monkeypatch)  # corpus dir exists, no PDFs
    assert h.run(update_goldens=False) == 2


def test_tier2_output_inside_git_worktree_refused(tmp_path, monkeypatch):
    h = _Tier2Harness(tmp_path, monkeypatch)
    h.add_pdf("mc1")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").write_text("gitdir: elsewhere\n")  # marks a worktree
    h.output = repo / "goldens"
    assert h.run(update_goldens=False) == 2


# ---------------------------------------------------------------------------
# CLI guards for tier 2 (CI refusal + required salt)
# ---------------------------------------------------------------------------


def _clear_ci(monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)


def test_corpus_dir_in_ci_refuses(tmp_path, monkeypatch):
    monkeypatch.setenv("CI", "1")
    monkeypatch.setenv("DEFENDANT_HASH_SALT", "realsalt")
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    assert cli.main(["run-fixtures", "--corpus-dir", str(corpus)]) == 2


def test_corpus_dir_missing_salt_refuses(tmp_path, monkeypatch):
    _clear_ci(monkeypatch)
    monkeypatch.delenv("DEFENDANT_HASH_SALT", raising=False)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    assert cli.main(["run-fixtures", "--corpus-dir", str(corpus)]) == 2


def test_corpus_dir_blank_salt_refuses(tmp_path, monkeypatch):
    _clear_ci(monkeypatch)
    monkeypatch.setenv("DEFENDANT_HASH_SALT", "   ")
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    assert cli.main(["run-fixtures", "--corpus-dir", str(corpus)]) == 2
