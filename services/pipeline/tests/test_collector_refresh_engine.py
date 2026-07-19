"""Refresh-engine tests (Task COL-4b) — fully offline: fake transport,
recording fake sleep, fake clock. Zero network, zero Playwright, zero
database (targets are injected synthetic values; the derivation query has its
own Postgres-backed suite).

Every docket number and hash here is FABRICATED: UJS-shaped numbers over
impossible 9xxxxxx sequences, hashes computed from constant fake bytes.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from threading import Event

from pipeline.collector import refresh_engine
from pipeline.collector.classification import FetchSignal
from pipeline.collector.engine import (
    HARD_CEILING_MINUTES,
    POST_BLOCK_COOLDOWN_SECONDS,
)
from pipeline.collector.refresh_engine import RefreshParams
from pipeline.collector.refresh_targets import RefreshTarget

FIXED_NOW = datetime(2026, 7, 13, 9, 30, 0, tzinfo=UTC)

# The UJS docket-number shape, as a SUBSTRING probe for the hygiene assertion.
_DOCKET_RE = re.compile(r"(CP|MC)-\d{2}-[A-Z]{2}-\d{7}-\d{4}")

OLD_BYTES = b"%PDF-1.7 fabricated old sheet"
NEW_BYTES = b"%PDF-1.7 fabricated new sheet"
OLD_HASH = hashlib.sha256(OLD_BYTES).hexdigest()


class FakeClock:
    """Monotonic clock advanced by the recording sleep (sleeps move time)."""

    def __init__(self) -> None:
        self.t = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.t += seconds


class FakeTransport:
    """Returns a scripted FetchSignal per docket; records every fetched number."""

    def __init__(self, signal_for) -> None:
        self._signal_for = signal_for
        self.calls: list[str] = []

    def fetch(self, docket: str) -> FetchSignal:
        self.calls.append(docket)
        if callable(self._signal_for):
            return self._signal_for(docket)
        return self._signal_for


def make_target(seq: int, court: str = "MC", source_hash: str = OLD_HASH):
    return RefreshTarget(
        docket_number=f"{court}-51-CR-{9000000 + seq:07d}-2025",
        source_hash=source_hash,
    )


def make_targets(count: int, court: str = "MC") -> list[RefreshTarget]:
    return [make_target(i + 1, court) for i in range(count)]


def make_params(tmp_path: Path, **overrides) -> RefreshParams:
    defaults = dict(
        court="both",
        max_minutes=240,
        refresh_dir=tmp_path / "refresh",
        report_dir=tmp_path / "runs",
        headless=False,
    )
    defaults.update(overrides)
    return RefreshParams(**defaults)


def run_engine(params, targets, transport, clock, *, jitter=3.0, abort_event=None):
    return refresh_engine.run(
        params,
        targets,
        transport,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        now=lambda: FIXED_NOW,
        jitter=lambda: jitter,
        abort_event=abort_event or Event(),
    )


def hit(pdf_bytes: bytes = OLD_BYTES) -> FetchSignal:
    return FetchSignal(pdf_ok=True, pdf_bytes=pdf_bytes)


def read_attempts(report: dict) -> list[dict]:
    path = Path(report["output_dir"]) / "attempts.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()]


# --- AC-1 / AC-2: the fetch universe IS the target list --------------------


def test_attempted_equals_target_list_exactly(tmp_path):
    clock = FakeClock()
    targets = make_targets(4)
    transport = FakeTransport(hit())
    report = run_engine(make_params(tmp_path), targets, transport, clock)
    # Every target attempted, in derivation order; nothing outside the list.
    assert transport.calls == [t.docket_number for t in targets]
    assert report["counts"]["attempted"] == len(targets)
    assert report["targets"]["derived_total"] == len(targets)
    assert report["stop_reason"] == "targets_exhausted"


def test_targets_by_court_counts_in_report(tmp_path):
    clock = FakeClock()
    targets = make_targets(2, "MC") + make_targets(3, "CP")
    transport = FakeTransport(hit())
    report = run_engine(make_params(tmp_path), targets, transport, clock)
    assert report["targets"]["by_court"] == {"MC": 2, "CP": 3}


# --- Pinned decision 8: unchanged / changed / new hash classes -------------


def test_unchanged_and_changed_hash_classification(tmp_path):
    clock = FakeClock()
    targets = make_targets(2)
    # Target 1 re-fetches identical bytes; target 2 fetches a changed sheet.
    transport = FakeTransport(
        lambda d: hit(OLD_BYTES if d == targets[0].docket_number else NEW_BYTES)
    )
    params = make_params(tmp_path)
    report = run_engine(params, targets, transport, clock)
    counts = report["counts"]
    assert counts["fetched"] == 2
    assert counts["unchanged_hash"] == 1
    assert counts["changed_hash"] == 1
    assert counts["new_hash"] == 0
    # The PDF is written in BOTH cases (unchanged dies later, at import).
    for target in targets:
        assert (params.refresh_dir / f"{target.docket_number}.pdf").exists()
    by_docket = {a["docket_number"]: a for a in read_attempts(report)}
    assert by_docket[targets[0].docket_number]["hash_class"] == "unchanged"
    assert by_docket[targets[1].docket_number]["hash_class"] == "changed"
    assert report["reconciles"] == {
        "attempted_eq_attempt_log_entries": True,
        "fetched_eq_unchanged_changed_new": True,
    }


def test_new_hash_bucket_is_defensive_only(tmp_path):
    # The derivation JOIN guarantees a prior hash; an empty one still cannot
    # crash or misclassify — it lands in the defensive `new` bucket.
    clock = FakeClock()
    targets = [make_target(1, source_hash="")]
    report = run_engine(make_params(tmp_path), targets, FakeTransport(hit()), clock)
    assert report["counts"]["new_hash"] == 1
    assert report["counts"]["fetched"] == 1
    assert report["reconciles"]["fetched_eq_unchanged_changed_new"] is True


def test_hit_without_pdf_bytes_is_a_failed_fetch(tmp_path):
    clock = FakeClock()
    targets = make_targets(1)
    transport = FakeTransport(FetchSignal(pdf_ok=True, pdf_bytes=None))
    params = make_params(tmp_path)
    report = run_engine(params, targets, transport, clock)
    assert report["counts"]["fetched"] == 0
    assert report["counts"]["failed"] == 1
    attempt = read_attempts(report)[0]
    assert attempt["outcome"] == "fetch_failed"
    assert attempt["detail"] == "no_pdf_bytes"
    assert not (params.refresh_dir / f"{targets[0].docket_number}.pdf").exists()


# --- Cycle-local resume skip ------------------------------------------------


def test_already_fetched_skip_no_portal_request_no_delay(tmp_path):
    clock = FakeClock()
    targets = make_targets(3)
    params = make_params(tmp_path)
    params.refresh_dir.mkdir(parents=True)
    pre = params.refresh_dir / f"{targets[1].docket_number}.pdf"
    pre.write_bytes(OLD_BYTES)
    transport = FakeTransport(hit())
    report = run_engine(params, targets, transport, clock, jitter=3.3)
    assert targets[1].docket_number not in transport.calls
    assert len(transport.calls) == 2
    assert report["counts"]["already_fetched"] == 1
    assert report["counts"]["fetched"] == 2
    # One jittered delay per REAL request only; the skip sleeps nothing.
    assert clock.sleeps.count(3.3) == 2
    assert report["per_request_delays_taken"] == 2
    # The pre-existing file is untouched (no re-fetch, no overwrite).
    assert pre.read_bytes() == OLD_BYTES


def test_already_fetched_skip_is_streak_neutral(tmp_path):
    # blocked, blocked, skip, blocked, blocked, blocked -> the skip must not
    # reset the block streak, so the run stops at block_streak (5).
    clock = FakeClock()
    targets = make_targets(6)
    params = make_params(tmp_path)
    params.refresh_dir.mkdir(parents=True)
    (params.refresh_dir / f"{targets[2].docket_number}.pdf").write_bytes(OLD_BYTES)
    transport = FakeTransport(FetchSignal(rate_limited=True))
    report = run_engine(params, targets, transport, clock)
    assert report["stop_reason"] == "block_streak"
    assert report["counts"]["blocked"] == 5
    assert report["counts"]["already_fetched"] == 1
    assert report["max_block_streak"] == 5


# --- No-results on a loaded docket: anomaly, never a coverage miss ----------


def test_no_results_counts_as_anomaly_and_writes_no_miss_ledger(tmp_path):
    clock = FakeClock()
    targets = make_targets(6)
    transport = FakeTransport(FetchSignal(no_results=True))
    report = run_engine(make_params(tmp_path), targets, transport, clock)
    counts = report["counts"]
    assert counts["failed"] == 6
    assert counts["no_results_anomalies"] == 6
    # A no-results page is a live portal response: streaks reset, so the run
    # walks the whole list rather than tripping a streak stop.
    assert report["stop_reason"] == "targets_exhausted"
    assert all(a["detail"] == "no_results" for a in read_attempts(report))
    # No miss-ledger (or any other ledger) file exists anywhere we wrote.
    ledger_files = [p for p in tmp_path.rglob("*") if "ledger" in p.name.lower()]
    assert ledger_files == []


# --- AC-3: a refresh writes ONLY refresh PDFs + its report artifacts --------


def test_file_universe_is_exactly_pdfs_and_report_artifacts(tmp_path):
    clock = FakeClock()
    targets = make_targets(3)

    def script(docket: str) -> FetchSignal:
        if docket == targets[1].docket_number:
            return FetchSignal(rate_limited=True)
        return hit(NEW_BYTES)

    params = make_params(tmp_path)
    report = run_engine(params, targets, FakeTransport(script), clock)
    run_dir = Path(report["output_dir"])
    created = {p for p in tmp_path.rglob("*") if p.is_file()}
    expected = {
        params.refresh_dir / f"{targets[0].docket_number}.pdf",
        params.refresh_dir / f"{targets[2].docket_number}.pdf",
        run_dir / "attempts.jsonl",
        run_dir / "run-report.json",
    }
    assert created == expected


# --- AC-4: locked collection conditions, reused not re-derived ---------------


def test_time_budget_clamped_to_locked_ceiling(tmp_path):
    # --max-minutes can never exceed the 240-minute ceiling: with each request
    # consuming ~an hour of fake clock, the run caps after 4 requests even
    # though the flag asked for far more time.
    clock = FakeClock()
    targets = make_targets(10)
    params = make_params(tmp_path, max_minutes=100_000)
    report = run_engine(params, targets, FakeTransport(hit()), clock, jitter=3600)
    assert report["stop_reason"] == "time_cap"
    assert report["counts"]["fetched"] == 4
    assert report["parameters"]["hard_ceiling_minutes"] == HARD_CEILING_MINUTES


def test_max_minutes_shortens_the_run(tmp_path):
    clock = FakeClock()
    targets = make_targets(5)
    params = make_params(tmp_path, max_minutes=1)
    report = run_engine(params, targets, FakeTransport(hit()), clock, jitter=61)
    assert report["stop_reason"] == "time_cap"
    assert report["counts"]["fetched"] == 1


def test_inter_batch_cooldown_counts_real_requests_only(tmp_path):
    clock = FakeClock()
    targets = make_targets(5)
    params = make_params(tmp_path, batch_size=2)
    params.refresh_dir.mkdir(parents=True)
    # A resume skip between real requests must not advance the batch count.
    (params.refresh_dir / f"{targets[2].docket_number}.pdf").write_bytes(OLD_BYTES)
    report = run_engine(params, targets, FakeTransport(hit()), clock)
    # 4 real requests at batch_size=2 -> exactly one boundary cooldown.
    assert report["cooldowns_taken"]["inter_batch"] == 1
    assert clock.sleeps.count(params.batch_cooldown_seconds) == 1


def test_post_block_cooldown_and_block_streak_stop(tmp_path):
    clock = FakeClock()
    targets = make_targets(20)
    transport = FakeTransport(FetchSignal(rate_limited=True))
    report = run_engine(make_params(tmp_path), targets, transport, clock)
    assert report["stop_reason"] == "block_streak"
    assert report["counts"]["blocked"] == 5
    assert report["cooldowns_taken"]["post_block"] == 5
    assert clock.sleeps.count(POST_BLOCK_COOLDOWN_SECONDS) == 5


def test_error_streak_stop(tmp_path):
    clock = FakeClock()
    targets = make_targets(20)
    transport = FakeTransport(FetchSignal(error=True, error_type="TimeoutError"))
    report = run_engine(make_params(tmp_path), targets, transport, clock)
    assert report["stop_reason"] == "error_streak"
    assert report["counts"]["failed"] == 5
    assert report["max_error_streak"] == 5


def test_unrecognized_page_fails_closed_to_blocked(tmp_path):
    clock = FakeClock()
    targets = make_targets(1)
    report = run_engine(
        make_params(tmp_path), targets, FakeTransport(FetchSignal()), clock
    )
    assert report["counts"]["blocked"] == 1
    attempt = read_attempts(report)[0]
    assert attempt["outcome"] == "blocked"
    assert attempt["detail"] == "unrecognized_page"


def test_abort_event_stops_before_any_fetch(tmp_path):
    clock = FakeClock()
    abort = Event()
    abort.set()
    transport = FakeTransport(hit())
    report = run_engine(
        make_params(tmp_path), make_targets(3), transport, clock, abort_event=abort
    )
    assert report["stop_reason"] == "operator_abort"
    assert transport.calls == []
    assert Path(report["output_dir"], "run-report.json").exists()


def test_max_fetches_cap_stops_run(tmp_path):
    clock = FakeClock()
    targets = make_targets(5)
    params = make_params(tmp_path, max_fetches=2)
    transport = FakeTransport(hit())
    report = run_engine(params, targets, transport, clock)
    assert report["stop_reason"] == "fetch_cap"
    assert len(transport.calls) == 2
    assert report["counts"]["fetched"] == 2


# --- AC-5: report shape + hygiene -------------------------------------------


def test_report_parameters_echo_policy_locked_values(tmp_path):
    clock = FakeClock()
    report = run_engine(
        make_params(tmp_path, court="CP"),
        make_targets(1, "CP"),
        FakeTransport(hit()),
        clock,
    )
    params = report["parameters"]
    assert report["mode"] == "refresh"
    assert params["court"] == "CP"
    assert params["post_block_cooldown_seconds"] == 300
    assert params["hard_ceiling_minutes"] == 240
    assert params["block_streak_stop"] == 5
    assert params["error_streak_stop"] == 5
    assert params["per_request_delay_seconds"] == [2.0, 5.0]


def test_report_and_coverage_statement_carry_no_docket_numbers(tmp_path):
    clock = FakeClock()
    report = run_engine(
        make_params(tmp_path), make_targets(3), FakeTransport(hit(NEW_BYTES)), clock
    )
    # Docket numbers belong ONLY in the attempt log (good-faith record); the
    # run report is counts/statuses/paths and must never carry one.
    assert _DOCKET_RE.search(json.dumps(report)) is None
    assert "3 fetched of 3 targets" in report["coverage_statement"]
    assert "(0 unchanged, 3 changed, 0 new)" in report["coverage_statement"]


def test_zero_targets_run_writes_report_and_touches_nothing(tmp_path):
    clock = FakeClock()
    transport = FakeTransport(hit())
    report = run_engine(make_params(tmp_path), [], transport, clock)
    assert report["stop_reason"] == "targets_exhausted"
    assert report["counts"]["attempted"] == 0
    assert transport.calls == []
    assert Path(report["output_dir"], "run-report.json").exists()
