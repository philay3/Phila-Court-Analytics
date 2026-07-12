"""Search-engine tests — fully offline: fake search transport, recording fake
sleep, fake clock. Zero network, zero Playwright. Covers AC-1/4/6/7/8 and the
required fixes F2 (combined batch accounting), F3 (blocked writes a ledger entry,
error writes none), F6 (grid_complete/grid_empty reset streaks)."""

import json
import logging
from datetime import UTC, date, datetime
from threading import Event

from pipeline.collector import search_engine
from pipeline.collector.classification import FetchSignal
from pipeline.collector.harvest import HarvestedRow, HarvestResult
from pipeline.collector.search_classification import SearchSignal
from pipeline.collector.search_engine import SearchParams
from pipeline.collector.window import window_ledger_path

FIXED_NOW = datetime(2026, 7, 11, 9, 30, 0, tzinfo=UTC)


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.t += seconds


class FakeSearchTransport:
    def __init__(self, signal_for, harvest_for=None, fetch_for=None) -> None:
        self._signal_for = signal_for
        self._harvest_for = harvest_for or (lambda d: HarvestResult([], 0))
        self._fetch_for = fetch_for or (
            lambda h: FetchSignal(pdf_ok=True, pdf_bytes=b"%PDF-1.7 x")
        )
        self.searches: list[date] = []
        self.fetches: list[str] = []
        self._current: date | None = None

    def search(self, window: date) -> SearchSignal:
        self.searches.append(window)
        self._current = window
        return self._signal_for(window)

    def harvest(self) -> HarvestResult:
        return self._harvest_for(self._current)

    def fetch(self, href: str) -> FetchSignal:
        self.fetches.append(href)
        return self._fetch_for(href)


def make_params(tmp_path, **overrides) -> SearchParams:
    defaults = dict(
        court="MC",
        start_date=date(2025, 6, 3),
        end_date=date(2025, 6, 3),
        max_minutes=240,
        intake_dir=tmp_path / "intake",
        report_dir=tmp_path / "runs",
        ledger_dir=tmp_path / "coverage",
        headless=False,
    )
    defaults.update(overrides)
    return SearchParams(**defaults)


def run_engine(params, transport, clock, *, jitter=3.0, abort_event=None):
    return search_engine.run(
        params,
        transport,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        now=lambda: FIXED_NOW,
        jitter=lambda: jitter,
        abort_event=abort_event or Event(),
    )


def _complete(row_count=10):
    return SearchSignal(
        search_ui_present=True, results_table_present=True, row_count=row_count
    )


_EMPTY = SearchSignal(search_ui_present=True, results_table_present=False, row_count=0)
_TRUNCATED = SearchSignal(
    search_ui_present=True,
    results_table_present=True,
    row_count=800,
    banner_present=True,
)
_BLOCKED = SearchSignal(rate_limited=True)
_ERROR = SearchSignal(error=True, error_type="TimeoutError")


def _rows(*specs):
    """specs: (court, seq, href) tuples -> HarvestResult with 0 skipped."""
    return HarvestResult(
        [HarvestedRow(c, f"{c}-51-CR-{s:07d}-2025", h) for c, s, h in specs], 0
    )


def _read_report(params, report):
    path = params.report_dir / report["run_id"] / search_engine.RUN_REPORT_FILENAME
    return json.loads(path.read_text())


def _read_attempts(params, report):
    path = params.report_dir / report["run_id"] / search_engine.ATTEMPT_LOG_FILENAME
    text = path.read_text()
    return [json.loads(x) for x in text.splitlines()] if text.strip() else []


def _read_ledger(params):
    path = window_ledger_path(params.ledger_dir)
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text().splitlines()]


# --- AC-1: daily iteration + per-window pipeline ---------------------------


def test_iterates_daily_windows_and_records_each(tmp_path):
    clock = FakeClock()
    params = make_params(
        tmp_path, start_date=date(2025, 6, 1), end_date=date(2025, 6, 3)
    )

    def signal_for(d):
        return {
            date(2025, 6, 1): _EMPTY,
            date(2025, 6, 2): _complete(),
            date(2025, 6, 3): _EMPTY,
        }[d]

    def harvest_for(d):
        return _rows(("MC", 1, "/x/CpDocketSheet?h=1"))

    transport = FakeSearchTransport(signal_for, harvest_for)
    report = run_engine(params, transport, clock)
    assert [d for d in transport.searches] == [
        date(2025, 6, 1),
        date(2025, 6, 2),
        date(2025, 6, 3),
    ]
    ledger = _read_ledger(params)
    assert [(e["date"], e["outcome"]) for e in ledger] == [
        ("2025-06-01", "empty"),
        ("2025-06-02", "complete"),
        ("2025-06-03", "empty"),
    ]
    assert report["stop_reason"] == "windows_exhausted"


def test_skips_windows_the_ledger_marks_complete(tmp_path):
    clock = FakeClock()
    params = make_params(
        tmp_path, start_date=date(2025, 6, 1), end_date=date(2025, 6, 2)
    )
    # Seed the ledger: 2025-06-01 already complete.
    path = window_ledger_path(params.ledger_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"date": "2025-06-01", "outcome": "complete"}) + "\n")
    transport = FakeSearchTransport(lambda d: _EMPTY)
    report = run_engine(params, transport, clock)
    # Only 2025-06-02 was searched.
    assert transport.searches == [date(2025, 6, 2)]
    assert report["date_range"]["skipped_complete"] == 1


def test_recheck_windows_ignores_the_ledger(tmp_path):
    clock = FakeClock()
    params = make_params(
        tmp_path,
        start_date=date(2025, 6, 1),
        end_date=date(2025, 6, 1),
        recheck_windows=True,
    )
    path = window_ledger_path(params.ledger_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"date": "2025-06-01", "outcome": "complete"}) + "\n")
    transport = FakeSearchTransport(lambda d: _EMPTY)
    report = run_engine(params, transport, clock)
    assert transport.searches == [date(2025, 6, 1)]  # re-searched despite ledger
    assert report["date_range"]["skipped_complete"] == 0


# --- AC-4: both courts recorded; --court gates fetching --------------------


def test_both_courts_recorded_but_only_mc_fetched(tmp_path):
    clock = FakeClock()
    params = make_params(tmp_path, court="MC")
    harvest = _rows(
        ("MC", 1, "/x/CpDocketSheet?h=1"),
        ("CP", 2, "/x/CpDocketSheet?h=2"),
        ("MC", 3, "/x/CpDocketSheet?h=3"),
    )
    transport = FakeSearchTransport(lambda d: _complete(), lambda d: harvest)
    report = run_engine(params, transport, clock)
    by_court = report["totals"]["by_court"]
    # Both courts harvested; only MC fetched.
    assert by_court["MC"]["harvested"] == 2
    assert by_court["CP"]["harvested"] == 1
    assert by_court["MC"]["fetched"] == 2
    assert by_court["CP"]["fetched"] == 0
    assert len(transport.fetches) == 2  # only the two MC hrefs


def test_court_both_fetches_cp_and_mc(tmp_path):
    clock = FakeClock()
    params = make_params(tmp_path, court="both")
    harvest = _rows(
        ("MC", 1, "/x/CpDocketSheet?h=1"),
        ("CP", 2, "/x/CpDocketSheet?h=2"),
    )
    transport = FakeSearchTransport(lambda d: _complete(), lambda d: harvest)
    report = run_engine(params, transport, clock)
    by_court = report["totals"]["by_court"]
    assert by_court["MC"]["fetched"] == 1
    assert by_court["CP"]["fetched"] == 1
    assert len(transport.fetches) == 2


def test_court_cp_fetches_only_cp(tmp_path):
    clock = FakeClock()
    params = make_params(tmp_path, court="CP")
    harvest = _rows(
        ("MC", 1, "/x/CpDocketSheet?h=1"),
        ("CP", 2, "/x/CpDocketSheet?h=2"),
    )
    transport = FakeSearchTransport(lambda d: _complete(), lambda d: harvest)
    report = run_engine(params, transport, clock)
    by_court = report["totals"]["by_court"]
    assert by_court["CP"]["fetched"] == 1
    assert by_court["MC"]["fetched"] == 0
    assert transport.fetches == ["/x/CpDocketSheet?h=2"]


# --- AC-6: already_present precedes fetch; reconciliation -------------------


def test_reconciliation_and_already_present_precedes_fetch(tmp_path):
    clock = FakeClock()
    params = make_params(tmp_path, court="MC")
    params.intake_dir.mkdir(parents=True, exist_ok=True)
    # MC-2 already on disk -> already_present, never fetched.
    (params.intake_dir / "MC-51-CR-0000002-2025.pdf").write_bytes(b"%PDF-1.4 present")
    harvest = _rows(
        ("MC", 1, "/x/CpDocketSheet?h=1"),  # fetch hit
        ("MC", 2, "/x/CpDocketSheet?h=2"),  # already_present
        ("MC", 3, None),  # no anchor -> fetch_failure
    )

    def fetch_for(href):
        return FetchSignal(pdf_ok=True, pdf_bytes=b"%PDF-1.7 hit")

    transport = FakeSearchTransport(lambda d: _complete(), lambda d: harvest, fetch_for)
    report = run_engine(params, transport, clock)
    mc = report["totals"]["by_court"]["MC"]
    assert mc == {
        "harvested": 3,
        "fetched": 1,
        "already_present": 1,
        "fetch_failures": 1,
    }
    # harvested == fetched + already_present + fetch_failures
    assert (
        mc["harvested"] == mc["fetched"] + mc["already_present"] + mc["fetch_failures"]
    )
    assert report["totals"]["reconciles"] is True
    # The already_present docket was never sent to the portal.
    assert "/x/CpDocketSheet?h=2" not in transport.fetches
    # Per-window reconciliation too.
    win = report["windows"][0]["by_court"]["MC"]
    assert (
        win["harvested"]
        == win["fetched"] + win["already_present"] + win["fetch_failures"]
    )


def test_fetch_failure_on_none_pdf_counts_as_failure(tmp_path):
    clock = FakeClock()
    params = make_params(tmp_path, court="MC")
    harvest = _rows(("MC", 1, "/x/CpDocketSheet?h=1"))
    transport = FakeSearchTransport(
        lambda d: _complete(),
        lambda d: harvest,
        lambda h: FetchSignal(rate_limited=True),
    )
    report = run_engine(params, transport, clock)
    mc = report["totals"]["by_court"]["MC"]
    assert mc["fetched"] == 0
    assert mc["fetch_failures"] == 1


# --- AC-7a: truncation banner stops the run --------------------------------


def test_truncated_window_stops_run(tmp_path):
    clock = FakeClock()
    params = make_params(
        tmp_path, start_date=date(2025, 6, 1), end_date=date(2025, 6, 5)
    )

    def signal_for(d):
        return _TRUNCATED if d == date(2025, 6, 2) else _complete()

    transport = FakeSearchTransport(signal_for, lambda d: _rows())
    report = run_engine(params, transport, clock)
    assert report["stop_reason"] == "window_truncated"
    # Stopped at 2025-06-02; 06-03..06-05 never searched.
    assert transport.searches == [date(2025, 6, 1), date(2025, 6, 2)]
    ledger = _read_ledger(params)
    assert ledger[-1]["outcome"] == "truncated"
    assert ledger[-1]["date"] == "2025-06-02"


# --- AC-7b: block/error streaks via the shared guard -----------------------


def test_five_blocked_searches_stop_with_block_streak(tmp_path):
    clock = FakeClock()
    params = make_params(
        tmp_path, start_date=date(2025, 6, 1), end_date=date(2025, 6, 10)
    )
    transport = FakeSearchTransport(lambda d: _BLOCKED)
    report = run_engine(params, transport, clock)
    assert report["stop_reason"] == "block_streak"
    assert report["max_block_streak"] == 5
    # Post-block cooldown fired after each blocked search.
    assert clock.sleeps.count(search_engine.POST_BLOCK_COOLDOWN_SECONDS) == 5
    # F3: each blocked search wrote a ledger entry.
    ledger = _read_ledger(params)
    assert len(ledger) == 5
    assert all(e["outcome"] == "blocked" for e in ledger)


def test_five_error_searches_stop_with_error_streak_and_no_ledger(tmp_path):
    clock = FakeClock()
    params = make_params(
        tmp_path, start_date=date(2025, 6, 1), end_date=date(2025, 6, 10)
    )
    transport = FakeSearchTransport(lambda d: _ERROR)
    report = run_engine(params, transport, clock)
    assert report["stop_reason"] == "error_streak"
    assert report["max_error_streak"] == 5
    # F3: a transport error writes NO ledger entry.
    assert _read_ledger(params) == []
    # Errors never trigger the post-block cooldown.
    assert report["cooldowns_taken"]["post_block"] == 0


# --- F6: grid_complete and grid_empty reset both streaks --------------------


def test_complete_and_empty_reset_streaks(tmp_path):
    clock = FakeClock()
    params = make_params(
        tmp_path, start_date=date(2025, 6, 1), end_date=date(2025, 6, 10)
    )
    # 4 blocked, complete (reset), 4 blocked, empty (reset): never 5 in a row.
    plan = {
        date(2025, 6, 1): _BLOCKED,
        date(2025, 6, 2): _BLOCKED,
        date(2025, 6, 3): _BLOCKED,
        date(2025, 6, 4): _BLOCKED,
        date(2025, 6, 5): _complete(),
        date(2025, 6, 6): _BLOCKED,
        date(2025, 6, 7): _BLOCKED,
        date(2025, 6, 8): _BLOCKED,
        date(2025, 6, 9): _BLOCKED,
        date(2025, 6, 10): _EMPTY,
    }
    transport = FakeSearchTransport(lambda d: plan[d], lambda d: _rows())
    report = run_engine(params, transport, clock)
    assert report["stop_reason"] == "windows_exhausted"
    assert report["max_block_streak"] == 4  # reset before ever reaching 5


# --- F2: batch accounting counts searches AND fetches ----------------------


def test_inter_batch_cooldown_fires_on_combined_search_and_fetch_count(tmp_path):
    clock = FakeClock()
    # batch_size 3: search(1) + 2 fetches = 3 requests -> cooldown before the
    # 3rd fetchable request (which is the next real request).
    params = make_params(tmp_path, court="MC", batch_size=3, batch_cooldown_seconds=90)
    harvest = _rows(
        ("MC", 1, "/x/CpDocketSheet?h=1"),
        ("MC", 2, "/x/CpDocketSheet?h=2"),
        ("MC", 3, "/x/CpDocketSheet?h=3"),
    )
    transport = FakeSearchTransport(lambda d: _complete(), lambda d: harvest)
    report = run_engine(params, transport, clock)
    # 1 search + 3 fetches = 4 requests; batch of 3 -> exactly one inter-batch
    # cooldown fired (before the 4th request).
    assert report["cooldowns_taken"]["inter_batch"] == 1
    assert clock.sleeps.count(90) == 1
    assert report["parameters"]["batch_request_counting"] == "searches_and_fetches"


# --- AC-8: report schema + attempts.jsonl window_date ----------------------


def test_report_schema_and_coverage_and_attempts(tmp_path):
    clock = FakeClock()
    params = make_params(
        tmp_path, court="MC", start_date=date(2025, 6, 1), end_date=date(2025, 6, 2)
    )

    def signal_for(d):
        return _complete() if d == date(2025, 6, 1) else _EMPTY

    harvest = _rows(("MC", 1, "/x/CpDocketSheet?h=1"))
    transport = FakeSearchTransport(signal_for, lambda d: harvest)
    report = run_engine(params, transport, clock)

    on_disk = _read_report(params, report)
    assert on_disk == report
    assert report["mode"] == "search"
    for key in (
        "run_id",
        "output_dir",
        "mode",
        "started_at",
        "ended_at",
        "duration_seconds",
        "duration_hms",
        "parameters",
        "date_range",
        "windows",
        "totals",
        "max_block_streak",
        "max_error_streak",
        "stop_reason",
        "cooldowns_taken",
        "per_request_delays_taken",
        "coverage_statement",
    ):
        assert key in report
    assert report["date_range"] == {
        "start": "2025-06-01",
        "end": "2025-06-02",
        "total_windows": 2,
        "searched": 2,
        "skipped_complete": 0,
    }
    # coverage stated in date terms.
    assert (
        report["coverage_statement"]
        == "2 of 2 windows complete in [2025-06-01..2025-06-02]"
    )
    # per-window summaries present.
    assert [w["date"] for w in report["windows"]] == ["2025-06-01", "2025-06-02"]
    assert report["windows"][0]["outcome"] == "complete"
    assert report["windows"][1]["outcome"] == "empty"
    # attempts.jsonl carries window_date + court on each entry.
    attempts = _read_attempts(params, report)
    assert len(attempts) == 1
    assert set(attempts[0]) == {
        "docket_number",
        "outcome",
        "detail",
        "window_date",
        "court",
    }
    assert attempts[0]["window_date"] == "2025-06-01"
    assert attempts[0]["court"] == "MC"
    assert attempts[0]["outcome"] == "hit"


# --- max-fetches (smoke) caps fetches but still writes the window entry -----


def test_max_fetches_caps_and_stops_but_writes_window_entry(tmp_path):
    clock = FakeClock()
    params = make_params(tmp_path, court="MC", max_fetches=2)
    harvest = _rows(
        ("MC", 1, "/x/CpDocketSheet?h=1"),
        ("MC", 2, "/x/CpDocketSheet?h=2"),
        ("MC", 3, "/x/CpDocketSheet?h=3"),
        ("MC", 4, "/x/CpDocketSheet?h=4"),
    )
    transport = FakeSearchTransport(lambda d: _complete(), lambda d: harvest)
    report = run_engine(params, transport, clock)
    assert report["stop_reason"] == "fetch_cap"
    assert len(transport.fetches) == 2  # only 2 live fetches
    assert report["totals"]["fetches"] == 2
    # The window's ledger entry is still written (single-window run yields one).
    ledger = _read_ledger(params)
    assert len(ledger) == 1
    assert ledger[0]["outcome"] == "complete"
    assert ledger[0]["fetched"]["MC"] == 2


# --- hit writes PDF; jitter after every portal request ---------------------


def test_hit_writes_pdf_to_intake(tmp_path):
    clock = FakeClock()
    params = make_params(tmp_path, court="MC")
    body = b"%PDF-1.7 sheet-body"
    harvest = _rows(("MC", 7, "/x/CpDocketSheet?h=7"))
    transport = FakeSearchTransport(
        lambda d: _complete(),
        lambda d: harvest,
        lambda h: FetchSignal(pdf_ok=True, pdf_bytes=body),
    )
    run_engine(params, transport, clock)
    out = params.intake_dir / "MC-51-CR-0000007-2025.pdf"
    assert out.read_bytes() == body


def test_jitter_after_every_search_and_fetch(tmp_path):
    clock = FakeClock()
    params = make_params(
        tmp_path, court="MC", start_date=date(2025, 6, 1), end_date=date(2025, 6, 2)
    )

    def signal_for(d):
        return _complete() if d == date(2025, 6, 1) else _EMPTY

    harvest = _rows(
        ("MC", 1, "/x/CpDocketSheet?h=1"), ("MC", 2, "/x/CpDocketSheet?h=2")
    )
    transport = FakeSearchTransport(signal_for, lambda d: harvest)
    report = run_engine(params, transport, clock, jitter=3.7)
    # 2 searches + 2 fetches (only window 1 harvests) = 4 portal requests.
    assert report["per_request_delays_taken"] == 4
    assert clock.sleeps.count(3.7) == 4


# --- operator abort at window boundary -------------------------------------


def test_operator_abort_between_windows(tmp_path):
    clock = FakeClock()
    event = Event()
    params = make_params(
        tmp_path, start_date=date(2025, 6, 1), end_date=date(2025, 6, 5)
    )

    def signal_for(d):
        event.set()  # abort requested during the first search
        return _EMPTY

    transport = FakeSearchTransport(signal_for)
    report = run_engine(params, transport, clock, abort_event=event)
    assert report["stop_reason"] == "operator_abort"
    # First window finished; the next iteration honored the abort.
    assert transport.searches == [date(2025, 6, 1)]


# --- privacy: no page content anywhere -------------------------------------


def test_no_page_content_in_outputs(tmp_path):
    clock = FakeClock()
    params = make_params(tmp_path, court="MC")
    secret = b"%PDF-1.7 CAPTION Jane Q Defendant DOB 1990"
    harvest = _rows(("MC", 1, "/x/CpDocketSheet?h=1"))
    transport = FakeSearchTransport(
        lambda d: _complete(),
        lambda d: harvest,
        lambda h: FetchSignal(pdf_ok=True, pdf_bytes=secret),
    )
    report = run_engine(params, transport, clock)
    report_text = (
        params.report_dir / report["run_id"] / search_engine.RUN_REPORT_FILENAME
    ).read_text()
    attempts_text = (
        params.report_dir / report["run_id"] / search_engine.ATTEMPT_LOG_FILENAME
    ).read_text()
    ledger_text = window_ledger_path(params.ledger_dir).read_text()
    for haystack in (report_text, attempts_text, ledger_text):
        assert "Jane" not in haystack
        assert "Defendant" not in haystack
        assert "CAPTION" not in haystack
    # The bytes exist ONLY in the intake PDF.
    assert (params.intake_dir / "MC-51-CR-0000001-2025.pdf").read_bytes() == secret


def test_empty_window_marks_complete_for_rerun_skip(tmp_path):
    # Run once: an empty window is recorded complete. Rerun with the SAME ledger
    # dir skips it (grid_empty marks a window complete, PD-2).
    clock = FakeClock()
    params = make_params(
        tmp_path, start_date=date(2025, 6, 1), end_date=date(2025, 6, 1)
    )
    transport = FakeSearchTransport(lambda d: _EMPTY)
    run_engine(params, transport, clock)

    clock2 = FakeClock()
    transport2 = FakeSearchTransport(lambda d: _EMPTY)
    report2 = run_engine(
        make_params(tmp_path, start_date=date(2025, 6, 1), end_date=date(2025, 6, 1)),
        transport2,
        clock2,
    )
    assert transport2.searches == []  # skipped as already-complete
    assert report2["date_range"]["skipped_complete"] == 1


# --- COL-2a: observability log lines (window / cooldown / progress) ---------


def _log_records(caplog, message):
    return [r for r in caplog.records if r.getMessage() == message]


def test_window_log_line_carries_fetch_accounting(tmp_path, caplog):
    # AC-1: the complete-window line gains flat fetched/already_present/
    # fetch_failures over the run's fetched courts; harvested stays per-court.
    clock = FakeClock()
    params = make_params(tmp_path, court="MC")
    params.intake_dir.mkdir(parents=True, exist_ok=True)
    # Pre-place seq 2's intake PDF so it resolves as already_present.
    (params.intake_dir / "MC-51-CR-0000002-2025.pdf").write_bytes(b"%PDF x")
    transport = FakeSearchTransport(
        lambda d: _complete(row_count=3),
        lambda d: _rows(
            ("MC", 1, "/x/CpDocketSheet?h=1"),  # fetch OK
            ("MC", 2, "/x/CpDocketSheet?h=2"),  # already present
            ("MC", 3, None),  # no sheet link -> fetch failure
        ),
    )
    with caplog.at_level(logging.INFO, logger="pipeline.collector"):
        run_engine(params, transport, clock)

    win = [
        r
        for r in _log_records(caplog, "window")
        if getattr(r, "outcome", None) == "complete"
    ]
    assert len(win) == 1
    rec = win[0]
    assert rec.fetched == 1
    assert rec.already_present == 1
    assert rec.fetch_failures == 1
    # Existing fields unchanged.
    assert rec.mc_harvested == 3
    assert rec.cp_harvested == 0
    assert rec.skipped_rows == 0


def test_post_block_cooldown_log_carries_context_and_detail(tmp_path, caplog):
    # AC-2: a post_block line carries batch context plus the triggering
    # outcome and a content-free detail string.
    clock = FakeClock()
    params = make_params(
        tmp_path, start_date=date(2025, 6, 1), end_date=date(2025, 6, 1)
    )
    transport = FakeSearchTransport(lambda d: SearchSignal(bot_check=True))
    with caplog.at_level(logging.INFO, logger="pipeline.collector"):
        run_engine(params, transport, clock)

    cds = _log_records(caplog, "cooldown")
    assert len(cds) == 1
    rec = cds[0]
    assert rec.kind == "post_block"
    assert rec.outcome == "blocked"
    assert rec.detail == "bot_check"
    assert rec.batch == 1
    assert rec.requests_in_batch == 1  # the blocked search itself
    assert rec.seconds == 300


def test_inter_batch_cooldown_log_carries_batch_context(tmp_path, caplog):
    # AC-2: the inter_batch line carries batch number + requests_in_batch at
    # the trigger, and no outcome/detail (those are post_block-only).
    clock = FakeClock()
    params = make_params(
        tmp_path,
        court="MC",
        batch_size=2,
        batch_cooldown_seconds=90,
        start_date=date(2025, 6, 1),
        end_date=date(2025, 6, 3),
    )
    transport = FakeSearchTransport(lambda d: _EMPTY)
    with caplog.at_level(logging.INFO, logger="pipeline.collector"):
        run_engine(params, transport, clock)

    ib = [r for r in _log_records(caplog, "cooldown") if r.kind == "inter_batch"]
    assert len(ib) == 1
    rec = ib[0]
    assert rec.batch == 1  # fires before the batch counter increments
    assert rec.requests_in_batch == 2  # == batch_size at the trigger
    assert rec.seconds == 90
    assert not hasattr(rec, "outcome")
    assert not hasattr(rec, "detail")


def test_progress_line_every_five_windows_projects_windows_exhausted(tmp_path, caplog):
    # AC-3: a progress line every 5 windows with complete/remaining, total
    # requests, elapsed vs. the effective cap, and a linear projection.
    clock = FakeClock()
    params = make_params(
        tmp_path, start_date=date(2025, 6, 1), end_date=date(2025, 6, 10)
    )  # 10 windows
    transport = FakeSearchTransport(lambda d: _EMPTY)
    with caplog.at_level(logging.INFO, logger="pipeline.collector"):
        run_engine(params, transport, clock)

    progs = _log_records(caplog, "progress")
    assert len(progs) == 2  # at window 5 and window 10
    first = progs[0]
    assert first.windows_complete == 5
    assert first.windows_remaining == 5
    assert first.total_requests == 5  # 5 searches, 0 fetches
    assert first.projected_stop == "windows_exhausted"
    assert "elapsed_minutes" in first.__dict__
    assert "cap_minutes" in first.__dict__


def test_progress_line_projects_time_cap_when_pace_exceeds_budget(tmp_path, caplog):
    # AC-3: the projection is against the EFFECTIVE budget (min(max_minutes,
    # 240)); a slow pace over many remaining windows projects time_cap.
    clock = FakeClock()
    params = make_params(
        tmp_path,
        max_minutes=2,  # 120s effective budget
        start_date=date(2025, 6, 1),
        end_date=date(2025, 6, 20),
    )  # 20 windows
    transport = FakeSearchTransport(lambda d: _EMPTY)
    with caplog.at_level(logging.INFO, logger="pipeline.collector"):
        run_engine(params, transport, clock, jitter=10.0)

    progs = _log_records(caplog, "progress")
    assert progs
    assert progs[0].projected_stop == "time_cap"
