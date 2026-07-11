"""Engine tests — fully offline: fake transport, recording fake sleep, fake
clock. Zero network, zero Playwright."""

import json
from datetime import UTC, datetime
from threading import Event

import pytest

from pipeline.collector import engine
from pipeline.collector.classification import FetchSignal
from pipeline.collector.engine import (
    BATCH_COOLDOWN_DEFAULT_SECONDS,
    BATCH_SIZE_DEFAULT,
    HARD_CEILING_MINUTES,
    POST_BLOCK_COOLDOWN_SECONDS,
    CollectParams,
)

FIXED_NOW = datetime(2026, 7, 11, 9, 30, 0, tzinfo=UTC)


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

    def __init__(self, signal_for, on_fetch=None) -> None:
        self._signal_for = signal_for
        self._on_fetch = on_fetch
        self.calls: list[str] = []

    def fetch(self, docket: str) -> FetchSignal:
        self.calls.append(docket)
        if self._on_fetch is not None:
            self._on_fetch(docket)
        if callable(self._signal_for):
            return self._signal_for(docket)
        return self._signal_for


def make_params(tmp_path, **overrides) -> CollectParams:
    defaults = dict(
        court="MC",
        year=2025,
        start_seq=1,
        count=5,
        max_minutes=240,
        intake_dir=tmp_path / "intake",
        report_dir=tmp_path / "runs",
        ledger_dir=tmp_path / "coverage",
        headless=False,
    )
    defaults.update(overrides)
    return CollectParams(**defaults)


def run_engine(params, transport, clock, *, jitter=3.0, abort_event=None):
    return engine.run(
        params,
        transport,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        now=lambda: FIXED_NOW,
        jitter=lambda: jitter,
        abort_event=abort_event or Event(),
    )


# --- per-request delay (FIX 1) --------------------------------------------


def test_jittered_delay_after_every_real_request(tmp_path):
    clock = FakeClock()
    transport = FakeTransport(lambda d: FetchSignal(no_results=True))
    params = make_params(tmp_path, count=3)
    report = run_engine(params, transport, clock, jitter=3.7)
    # One 2.0–5.0s delay per fetched attempt; none skipped.
    delays = [s for s in clock.sleeps if s == 3.7]
    assert len(delays) == 3
    assert report["per_request_delays_taken"] == 3


def test_production_jitter_is_within_band():
    from pipeline.collector.run import _jitter

    for _ in range(200):
        assert 2.0 <= _jitter() <= 5.0


# --- block streak + post-block cooldown -----------------------------------


def test_five_blocks_stop_with_block_streak_and_cooldowns(tmp_path):
    clock = FakeClock()
    transport = FakeTransport(lambda d: FetchSignal(rate_limited=True))
    params = make_params(tmp_path, count=20)
    report = run_engine(params, transport, clock)
    assert report["stop_reason"] == "block_streak"
    assert report["counts"]["blocks"] == 5
    assert report["max_block_streak"] == 5
    assert report["cooldowns_taken"]["post_block"] == 5
    # A 2-minute cooldown followed each block.
    assert clock.sleeps.count(POST_BLOCK_COOLDOWN_SECONDS) == 5


def test_post_block_cooldown_is_two_minutes():
    assert POST_BLOCK_COOLDOWN_SECONDS == 120


# --- error streak (FIX 2) --------------------------------------------------


def test_five_errors_stop_with_error_streak(tmp_path):
    clock = FakeClock()
    transport = FakeTransport(
        lambda d: FetchSignal(error=True, error_type="TimeoutError")
    )
    params = make_params(tmp_path, count=20)
    report = run_engine(params, transport, clock)
    assert report["stop_reason"] == "error_streak"
    assert report["counts"]["errors"] == 5
    assert report["max_error_streak"] == 5
    # Errors never trigger the post-block cooldown.
    assert report["cooldowns_taken"]["post_block"] == 0


# --- inter-batch cooldown --------------------------------------------------


def test_inter_batch_cooldown_after_full_batch(tmp_path):
    clock = FakeClock()
    transport = FakeTransport(lambda d: FetchSignal(no_results=True))
    params = make_params(tmp_path, count=BATCH_SIZE_DEFAULT + 1)
    report = run_engine(params, transport, clock)
    assert report["stop_reason"] == "range_exhausted"
    assert report["cooldowns_taken"]["inter_batch"] == 1
    assert clock.sleeps.count(BATCH_COOLDOWN_DEFAULT_SECONDS) == 1
    # The 41st attempt is in batch 2.
    lines = _read_attempts(params, report)
    assert lines[-1]["batch"] == 2
    assert lines[0]["batch"] == 1


def test_batch_boundary_counts_real_requests_not_skips(tmp_path):
    # A run of already_present skips must not advance the batch counter.
    clock = FakeClock()
    params = make_params(tmp_path, count=BATCH_SIZE_DEFAULT + 1)
    params.intake_dir.mkdir(parents=True, exist_ok=True)
    # Pre-place PDFs for the first 10 dockets so they skip.
    from pipeline.collector.enumeration import docket_range

    dockets = docket_range("MC", 2025, 1, BATCH_SIZE_DEFAULT + 1)
    for d in dockets[:10]:
        (params.intake_dir / f"{d}.pdf").write_bytes(b"%PDF-1.4 x")
    transport = FakeTransport(lambda d: FetchSignal(no_results=True))
    report = run_engine(params, transport, clock)
    # 41 dockets, 10 skipped -> only 31 real requests -> no inter-batch cooldown.
    assert report["counts"]["already_present"] == 10
    assert report["cooldowns_taken"]["inter_batch"] == 0
    assert len(transport.calls) == BATCH_SIZE_DEFAULT + 1 - 10


def test_batch_size_and_cooldown_come_from_params(tmp_path):
    # FIX 4: --batch-size / --batch-cooldown-seconds are honored per run.
    clock = FakeClock()
    transport = FakeTransport(lambda d: FetchSignal(no_results=True))
    params = make_params(tmp_path, count=3, batch_size=2, batch_cooldown_seconds=90)
    report = run_engine(params, transport, clock)
    assert report["cooldowns_taken"]["inter_batch"] == 1
    assert clock.sleeps.count(90) == 1
    assert report["parameters"]["batch_size"] == 2
    assert report["parameters"]["inter_batch_cooldown_seconds"] == 90
    lines = _read_attempts(params, report)
    assert lines[-1]["batch"] == 2


# --- time cap + hard ceiling ----------------------------------------------


def test_time_cap_stops_run(tmp_path):
    clock = FakeClock()
    transport = FakeTransport(lambda d: FetchSignal(no_results=True))
    params = make_params(tmp_path, count=100, max_minutes=1)  # 60s budget
    report = run_engine(params, transport, clock, jitter=20.0)
    # elapsed 0,20,40 -> fetch; at 60 the 4th iteration stops.
    assert report["stop_reason"] == "time_cap"
    assert report["counts"]["attempted"] == 3


def test_hard_ceiling_clamps_even_with_huge_max_minutes(tmp_path):
    clock = FakeClock()
    transport = FakeTransport(lambda d: FetchSignal(no_results=True))
    # max_minutes 9999 must be clamped to 240 (14400s). With a 3600s delay per
    # request, the run stops after 4 requests (elapsed reaches 14400), proving
    # the clamp: without it the budget would be ~600k seconds.
    params = make_params(tmp_path, count=100, max_minutes=9999)
    report = run_engine(params, transport, clock, jitter=3600.0)
    assert report["stop_reason"] == "time_cap"
    assert report["counts"]["attempted"] == 4
    assert report["parameters"]["hard_ceiling_minutes"] == HARD_CEILING_MINUTES
    assert report["parameters"]["max_minutes"] == 9999


# --- already_present skip --------------------------------------------------


def test_already_present_skip_does_not_fetch(tmp_path):
    clock = FakeClock()
    params = make_params(tmp_path, count=3)
    params.intake_dir.mkdir(parents=True, exist_ok=True)
    present = "MC-51-CR-0000002-2025"
    (params.intake_dir / f"{present}.pdf").write_bytes(b"%PDF-1.4 already")
    transport = FakeTransport(lambda d: FetchSignal(no_results=True))
    report = run_engine(params, transport, clock)
    assert present not in transport.calls
    assert report["counts"]["already_present"] == 1
    assert report["counts"]["attempted"] == 3
    # No per-request delay was spent on the skip (2 real requests).
    assert report["per_request_delays_taken"] == 2


def test_hit_writes_pdf_to_intake(tmp_path):
    clock = FakeClock()
    params = make_params(tmp_path, count=1)
    body = b"%PDF-1.7 hit-body"
    transport = FakeTransport(lambda d: FetchSignal(pdf_ok=True, pdf_bytes=body))
    run_engine(params, transport, clock)
    out = params.intake_dir / "MC-51-CR-0000001-2025.pdf"
    assert out.read_bytes() == body


# --- operator abort (graceful Ctrl-C) -------------------------------------


def test_operator_abort_finishes_in_flight_then_stops(tmp_path):
    clock = FakeClock()
    event = Event()
    params = make_params(tmp_path, count=10)

    def on_fetch(docket):
        event.set()  # SIGINT arrives during the first in-flight request

    transport = FakeTransport(lambda d: FetchSignal(no_results=True), on_fetch=on_fetch)
    report = run_engine(params, transport, clock, abort_event=event)
    assert report["stop_reason"] == "operator_abort"
    # The in-flight (first) request completed; the next iteration aborted.
    assert report["counts"]["attempted"] == 1


# --- report + attempt-log shape -------------------------------------------


def _read_report(params, report):
    path = params.report_dir / report["run_id"] / engine.RUN_REPORT_FILENAME
    return json.loads(path.read_text())


def _read_attempts(params, report):
    path = params.report_dir / report["run_id"] / engine.ATTEMPT_LOG_FILENAME
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_report_and_attempt_log_shapes(tmp_path):
    clock = FakeClock()

    def signal_for(d):
        if d.endswith("0000001-2025"):
            return FetchSignal(pdf_ok=True, pdf_bytes=b"%PDF-1.7 a")
        return FetchSignal(no_results=True)

    transport = FakeTransport(signal_for)
    params = make_params(tmp_path, count=3)
    report = run_engine(params, transport, clock)

    on_disk = _read_report(params, report)
    assert on_disk == report
    for key in (
        "run_id",
        "output_dir",
        "started_at",
        "ended_at",
        "duration_seconds",
        "duration_hms",
        "parameters",
        "counts",
        "max_block_streak",
        "max_error_streak",
        "stop_reason",
        "cooldowns_taken",
        "per_request_delays_taken",
        "coverage_statement",
    ):
        assert key in report
    counts = report["counts"]
    assert counts["attempted"] == 3
    assert counts == {
        "attempted": 3,
        "hits": 1,
        "misses": 2,
        "already_present": 0,
        "known_miss": 0,
        "blocks": 0,
        "errors": 0,
    }
    params_block = report["parameters"]
    for key in (
        "court",
        "year",
        "start_seq",
        "count",
        "range_first",
        "range_last",
        "batch_size",
        "inter_batch_cooldown_seconds",
        "post_block_cooldown_seconds",
        "per_request_delay_seconds",
        "block_streak_stop",
        "error_streak_stop",
        "max_minutes",
        "hard_ceiling_minutes",
        "headful",
    ):
        assert key in params_block
    assert report["coverage_statement"] == (
        "1 hits of 3 attempted in range MC-51-CR-0000001-2025–MC-51-CR-0000003-2025"
    )

    attempts = _read_attempts(params, report)
    assert len(attempts) == 3
    for entry in attempts:
        assert set(entry) == {
            "docket_number",
            "outcome",
            "detail",
            "batch",
            "timestamp",
        }
    assert attempts[0]["outcome"] == "hit"
    assert attempts[1]["outcome"] == "miss"


def test_range_exhausted_stop_reason(tmp_path):
    clock = FakeClock()
    transport = FakeTransport(lambda d: FetchSignal(no_results=True))
    params = make_params(tmp_path, count=3)
    report = run_engine(params, transport, clock)
    assert report["stop_reason"] == "range_exhausted"


def test_blocked_attempt_detail_names_the_signal(tmp_path):
    clock = FakeClock()
    signals = {
        1: FetchSignal(bot_check=True),
        2: FetchSignal(unauthorized=True),
        3: FetchSignal(rate_limited=True),
        4: FetchSignal(),  # unrecognized -> fail-closed block
    }

    def signal_for(d):
        seq = int(d.split("-")[3])
        return signals[seq]

    transport = FakeTransport(signal_for)
    params = make_params(tmp_path, count=4)
    report = run_engine(params, transport, clock)
    attempts = _read_attempts(params, report)
    assert [a["detail"] for a in attempts] == [
        "bot_check",
        "unauthorized",
        "rate_limited",
        "unrecognized_page",
    ]
    # All four were classified blocked; the streak stopped the run at N=5? No —
    # only four, so range_exhausted, but every outcome is blocked.
    assert all(a["outcome"] == "blocked" for a in attempts)
    assert report["counts"]["blocks"] == 4


# --- privacy: no page content anywhere; no capture APIs (FIX 4) -----------


def test_no_page_content_in_any_output(tmp_path, caplog):
    import logging

    clock = FakeClock()
    secret = b"%PDF-1.7 CAPTION Jane Q Defendant SSN 000-00-0000"
    transport = FakeTransport(lambda d: FetchSignal(pdf_ok=True, pdf_bytes=secret))
    params = make_params(tmp_path, count=2)
    with caplog.at_level(logging.INFO, logger="pipeline.collector"):
        report = run_engine(params, transport, clock)

    secret_text = secret.decode("latin-1")
    report_text = (
        params.report_dir / report["run_id"] / engine.RUN_REPORT_FILENAME
    ).read_text()
    attempts_text = (
        params.report_dir / report["run_id"] / engine.ATTEMPT_LOG_FILENAME
    ).read_text()
    log_text = "\n".join(r.getMessage() + str(r.__dict__) for r in caplog.records)

    for haystack in (report_text, attempts_text, log_text):
        assert "Jane" not in haystack
        assert "Defendant" not in haystack
        assert secret_text not in haystack
    # The bytes exist ONLY in the intake PDF.
    assert (params.intake_dir / "MC-51-CR-0000001-2025.pdf").read_bytes() == secret


def test_collector_source_invokes_no_capture_apis():
    # FIX 4: grep-level proof that no screenshot/tracing/HAR/video capture API
    # is invoked in any collector code path. Scans for call patterns, so the
    # prose in docstrings ("no screenshot, tracing, ...") does not trip it.
    import pathlib

    import pipeline.collector as pkg

    forbidden = (
        ".screenshot(",
        "record_video",
        "record_har",
        ".start_tracing",
        "context.tracing",
        ".tracing.start",
        "video_dir",
    )
    root = pathlib.Path(pkg.__file__).parent
    for source in root.glob("*.py"):
        text = source.read_text()
        for pattern in forbidden:
            assert pattern not in text, f"{pattern} found in {source.name}"


# --- output-dir guard ------------------------------------------------------


def test_validate_output_dirs_refuses_git_worktree(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    inside = repo / "intake"
    safe = tmp_path / "safe"
    assert engine.validate_output_dirs(inside, safe) is not None
    assert engine.validate_output_dirs(safe, inside) is not None
    assert engine.validate_output_dirs(safe, tmp_path / "runs") is None
    # A ledger dir inside a worktree is refused too (COL-1b).
    err = engine.validate_output_dirs(safe, tmp_path / "runs", inside)
    assert err is not None and "ledger-dir" in err
    assert engine.validate_output_dirs(safe, tmp_path / "runs", safe) is None


def test_empty_range_would_never_happen_but_coverage_is_safe(tmp_path):
    # docket_range enforces count>=1, but the coverage helper must not crash on
    # an empty attempt list defensively.
    assert "0 hits of 0 attempted" in engine._coverage_statement(
        dict.fromkeys(engine._COUNT_KEYS, 0),
        [],
    )


@pytest.mark.parametrize(
    "seconds,expected",
    [(0, "0:00:00"), (61, "0:01:01"), (3661, "1:01:01"), (14400, "4:00:00")],
)
def test_format_hms(seconds, expected):
    assert engine._format_hms(seconds) == expected


# --- persistent miss ledger (COL-1b) --------------------------------------


def _read_ledger(params) -> list[dict]:
    path = engine.ledger_path_for(params)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines()]


def _seed_ledger(params, dockets, *, run_id="run-seed"):
    path = engine.ledger_path_for(params)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(
            {
                "docket_number": d,
                "run_id": run_id,
                "timestamp": "2026-07-11T04:52:30+00:00",
                "classifier_note": "no_results",
            }
        )
        for d in dockets
    ]
    path.write_text("".join(f"{line}\n" for line in lines))


def test_ledger_appends_only_on_fail_closed_miss(tmp_path):
    clock = FakeClock()

    def signal_for(d):
        seq = int(d.split("-")[3])
        if seq == 1:
            return FetchSignal(pdf_ok=True, pdf_bytes=b"%PDF-1.7 x")
        if seq == 2:
            return FetchSignal(no_results=True)  # miss -> ledger
        if seq == 3:
            return FetchSignal(rate_limited=True)  # blocked -> no ledger
        return FetchSignal(no_results=True)  # miss -> ledger

    transport = FakeTransport(signal_for)
    params = make_params(tmp_path, count=4)
    run_engine(params, transport, clock)
    ledger = _read_ledger(params)
    dockets = sorted(e["docket_number"] for e in ledger)
    assert dockets == ["MC-51-CR-0000002-2025", "MC-51-CR-0000004-2025"]
    for entry in ledger:
        assert entry["classifier_note"] == "no_results"
        assert set(entry) == {
            "docket_number",
            "run_id",
            "timestamp",
            "classifier_note",
        }


def test_loader_dedupes_duplicate_lines(tmp_path):
    params = make_params(tmp_path, count=3)
    doc = "MC-51-CR-0000002-2025"
    _seed_ledger(params, [doc, doc, doc])
    known = engine.load_miss_ledger(
        engine.ledger_path_for(params), params.court, params.year
    )
    assert known == {doc}


def test_known_miss_skips_without_fetch_or_delay(tmp_path):
    clock = FakeClock()
    params = make_params(tmp_path, count=3)
    known = "MC-51-CR-0000002-2025"
    _seed_ledger(params, [known])
    transport = FakeTransport(lambda d: FetchSignal(no_results=True))
    report = run_engine(params, transport, clock)
    assert known not in transport.calls  # no portal request
    assert report["counts"]["known_miss"] == 1
    # 2 real requests -> 2 per-request delays; the skip spent none.
    assert report["per_request_delays_taken"] == 2
    # streak-neutral: the run finished cleanly.
    assert report["stop_reason"] == "range_exhausted"


def test_known_miss_excluded_from_batch_boundary(tmp_path):
    clock = FakeClock()
    params = make_params(tmp_path, count=BATCH_SIZE_DEFAULT + 1)
    from pipeline.collector.enumeration import docket_range

    dockets = docket_range("MC", 2025, 1, BATCH_SIZE_DEFAULT + 1)
    _seed_ledger(params, dockets[:10])  # 10 known misses
    transport = FakeTransport(lambda d: FetchSignal(no_results=True))
    report = run_engine(params, transport, clock)
    # 41 dockets, 10 known-miss skips -> 31 real requests -> no inter-batch.
    assert report["counts"]["known_miss"] == 10
    assert report["cooldowns_taken"]["inter_batch"] == 0
    assert len(transport.calls) == BATCH_SIZE_DEFAULT + 1 - 10


def test_recheck_misses_bypasses_ledger_and_reappends(tmp_path):
    clock = FakeClock()
    params = make_params(tmp_path, count=2, recheck_misses=True)
    doc = "MC-51-CR-0000001-2025"
    _seed_ledger(params, [doc])
    transport = FakeTransport(lambda d: FetchSignal(no_results=True))
    report = run_engine(params, transport, clock)
    # Ledger ignored: the seeded docket is re-attempted, not skipped.
    assert doc in transport.calls
    assert report["counts"]["known_miss"] == 0
    assert report["counts"]["misses"] == 2
    # And confirmed misses re-append (duplicate lines are fine).
    ledger = _read_ledger(params)
    assert sum(1 for e in ledger if e["docket_number"] == doc) == 2


def test_report_and_coverage_include_known_miss(tmp_path):
    clock = FakeClock()
    params = make_params(tmp_path, count=3)
    _seed_ledger(params, ["MC-51-CR-0000002-2025"])
    transport = FakeTransport(lambda d: FetchSignal(no_results=True))
    report = run_engine(params, transport, clock)
    counts = report["counts"]
    assert "known_miss" in counts
    # attempted denominator includes the known_miss.
    assert counts["attempted"] == 3
    assert counts["known_miss"] == 1
    assert counts["misses"] == 2
    assert "of 3 attempted" in report["coverage_statement"]
    assert report["parameters"]["recheck_misses"] is False
    assert report["parameters"]["ledger_path"].endswith("miss-ledger-MC-2025.jsonl")


def test_load_miss_ledger_skips_malformed_line_loudly(tmp_path, caplog):
    import logging

    params = make_params(tmp_path)
    path = engine.ledger_path_for(params)
    path.parent.mkdir(parents=True, exist_ok=True)
    good = json.dumps({"docket_number": "MC-51-CR-0000002-2025"})
    path.write_text(good + "\n" + "{not valid json\n")
    with caplog.at_level(logging.WARNING, logger="pipeline.collector"):
        known = engine.load_miss_ledger(path, "MC", 2025)
    assert known == {"MC-51-CR-0000002-2025"}
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert warnings[0].skipped == 1
    assert warnings[0].ledger_path == str(path)


def test_load_miss_ledger_filters_to_court_year(tmp_path, caplog):
    import logging

    params = make_params(tmp_path)
    path = engine.ledger_path_for(params)
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = [
        {"docket_number": "MC-51-CR-0000002-2025"},  # in scope
        {"docket_number": "CP-51-CR-0000002-2025"},  # wrong court
        {"docket_number": "MC-51-CR-0000002-2024"},  # wrong year
    ]
    path.write_text("".join(json.dumps(e) + "\n" for e in entries))
    with caplog.at_level(logging.WARNING, logger="pipeline.collector"):
        known = engine.load_miss_ledger(path, "MC", 2025)
    assert known == {"MC-51-CR-0000002-2025"}
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert warnings[0].skipped == 2


def test_load_miss_ledger_missing_file_is_empty(tmp_path):
    params = make_params(tmp_path)
    assert engine.load_miss_ledger(engine.ledger_path_for(params), "MC", 2025) == set()
