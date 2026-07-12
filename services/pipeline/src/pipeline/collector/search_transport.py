"""Playwright transport adapter for search mode (Task COL-2).

Drives the Date-Filed advanced search (ported from Capstone ``collect.py`` /
``fetch_mc_fixtures.py``), observes the results page into a content-free
:class:`SearchSignal`, harvests rows via :func:`harvest.harvest_rows`, and
fetches docket-sheet PDFs from harvested hrefs in-session. This is the ONLY
search-mode module that touches Playwright; it imports it LAZILY inside methods
so the package (and the whole test suite) imports cleanly without the optional
``collector`` dependency group.

Headful by default (the proven posture, honest about not evading detection).
Browser is restarted every ``BROWSER_RESTART_EVERY`` fetches (Capstone
convention, ported) — the restart is performed at a WINDOW boundary inside
:meth:`search`, never mid-fetch, so a window's one-time sheet hrefs stay valid
for its whole fetch loop.

Hard rules honored here (same as ``transport.py``):
  - a bot check / captcha is NEVER solved, bypassed, or automated — reported as
    a block; the engine applies the cooldown + streak;
  - NO screenshot, tracing, HAR, or video is captured in any code path;
    detection is presence/count only and never reads, prints, logs, or stores
    page text;
  - the harvester reads only the docket-number cell and the sheet anchor —
    caption/participant/DOB cells are never touched.

F4 (collector transport consolidation, future landing candidate): the block
presence-checks and ``_pdf_from_href`` below are intentionally duplicated from
``transport.py`` rather than refactored into a shared base, to keep this task
within scope. Each duplicate names its ``transport.py`` source inline.
"""

from __future__ import annotations

import logging
from datetime import date

from pipeline.collector.classification import FetchSignal
from pipeline.collector.harvest import ROW_SELECTOR, HarvestResult, harvest_rows
from pipeline.collector.search_classification import SearchSignal

logger = logging.getLogger("pipeline.collector")

PORTAL = "https://ujsportal.pacourts.us/CaseSearch"
BROWSER_RESTART_EVERY = 150  # fetches per browser session, guards memory (ported)

# --- Pinned selectors (COL-2 Step 0 recon, F5 sign-off) --------------------
# Truncation banner: presence-check for this substring (count > 0); the matched
# text is never captured. Absent on single/2-day windows, present at ~3 days.
_BANNER_SUBSTR = "Not all results are shown for Common Pleas and Magisterial"
# The results grid element; absent entirely on the genuine empty state.
_RESULTS_TABLE_SELECTOR = "table"

# --- Duplicated from transport.py (F4) -------------------------------------
# Source: transport.py ``_BOT_CHECK_SELECTOR``.
_BOT_CHECK_SELECTOR = (
    "iframe[src*='recaptcha'], iframe[src*='hcaptcha'], "
    "iframe[title*='captcha' i], #captcha, [data-captcha], .g-recaptcha"
)
# Source: transport.py ``_RATE_LIMIT_PATTERNS``.
_RATE_LIMIT_PATTERNS = (
    "too many requests",
    "unusual traffic",
    "please slow down",
    "rate limit",
    "access denied",
)
# Source: transport.py ``_UNAUTHORIZED_PATTERNS``.
_UNAUTHORIZED_PATTERNS = (
    "unauthorized",
    "not authorized",
)
# Source: transport.py ``_SEARCH_UI_SELECTOR`` — the positive "portal served
# the search page" marker (Blocker-2 / Option A basis for grid_empty).
_SEARCH_UI_SELECTOR = "select[title='Search By'], #btnSearch"


class PlaywrightSearchTransport:
    """Owns a headful Chromium session; searches one window / fetches one sheet.

    Use as a context manager so the browser is always closed::

        with PlaywrightSearchTransport() as transport:
            search_engine.run(..., transport=transport, ...)
    """

    def __init__(self, headless: bool = False) -> None:
        self.headless = headless
        self._pw = None
        self._browser = None
        self._page = None
        self._fetches_since_restart = 0

    def __enter__(self) -> PlaywrightSearchTransport:
        try:
            from playwright.sync_api import sync_playwright
        except ModuleNotFoundError as exc:  # pragma: no cover - env-dependent
            raise RuntimeError(
                "Playwright is not installed. Install the optional collector "
                "group: `uv sync --group collector` and "
                "`uv run playwright install chromium`."
            ) from exc
        self._pw = sync_playwright().start()
        self._launch_browser()
        return self

    def __exit__(self, *exc: object) -> None:
        # Swallow teardown failures (same rationale as transport.py __exit__):
        # a SIGINT abort can close the driver before us; the report is already
        # written by the time we get here.
        if self._browser is not None:
            try:
                self._browser.close()
            except Exception as close_exc:
                logger.info(
                    "browser close failed during teardown (ignored)",
                    extra={"error_type": type(close_exc).__name__},
                )
        if self._pw is not None:
            try:
                self._pw.stop()
            except Exception as stop_exc:
                logger.info(
                    "playwright stop failed during teardown (ignored)",
                    extra={"error_type": type(stop_exc).__name__},
                )

    def _launch_browser(self) -> None:
        self._browser = self._pw.chromium.launch(headless=self.headless)
        self._page = self._browser.new_page()
        self._fetches_since_restart = 0

    def _restart_browser(self) -> None:
        if self._browser is not None:
            try:
                self._browser.close()
            except Exception as close_exc:  # pragma: no cover - best-effort
                logger.info(
                    "browser close failed during restart (ignored)",
                    extra={"error_type": type(close_exc).__name__},
                )
        self._launch_browser()

    # --- observation helpers (duplicated from transport.py, F4) -------------
    def _any_selector(self, selector: str) -> bool:  # source: transport.py
        try:
            return self._page.locator(selector).count() > 0
        except Exception:
            return False

    def _any_text(self, patterns: tuple[str, ...]) -> bool:  # source: transport.py
        try:
            body = self._page.locator("body")
            for phrase in patterns:
                if body.get_by_text(phrase, exact=False).count() > 0:
                    return True
        except Exception:
            return False
        return False

    def _detect_block(self) -> tuple[bool, bool, bool]:  # source: transport.py
        """Return ``(bot_check, rate_limited, unauthorized)`` from presence
        checks only; never reads page text into a returned/stored value."""
        bot_check = self._any_selector(_BOT_CHECK_SELECTOR)
        rate_limited = self._any_text(_RATE_LIMIT_PATTERNS)
        unauthorized = self._any_text(_UNAUTHORIZED_PATTERNS)
        return bot_check, rate_limited, unauthorized

    def _pdf_from_href(self, href: str) -> bytes | None:  # source: transport.py
        """Fetch a docket-sheet PDF from its results-row href in-session.
        Returns PDF bytes, or ``None`` if the response is missing / not a PDF."""
        url = (
            href if href.startswith("http") else f"https://ujsportal.pacourts.us{href}"
        )
        resp = self._page.context.request.get(url)
        if not resp.ok:
            return None
        body = resp.body()
        if not body.startswith(b"%PDF"):
            return None
        return body

    # --- SearchTransport contract -------------------------------------------
    def search(self, window: date) -> SearchSignal:
        """Run one single-day advanced search; return a content-free signal.

        Never raises: any transport exception is returned as
        ``SearchSignal(error=True, error_type=<class name>)``.
        """
        # Browser restart lands here, at a window boundary — never mid-fetch —
        # so this window's fresh one-time sheet hrefs stay valid for its loop.
        if self._fetches_since_restart >= BROWSER_RESTART_EVERY:
            self._restart_browser()
        try:
            page = self._page
            day = window.strftime("%Y-%m-%d")
            page.goto(PORTAL, wait_until="networkidle")
            page.locator("select[title='Search By']").select_option("DateFiled")
            page.wait_for_timeout(800)
            page.locator("input[name='AdvanceSearch']").check()
            page.wait_for_timeout(800)
            page.locator("select[title='County']").select_option(label="Philadelphia")
            page.locator("input[name='FiledStartDate']").fill(day)
            page.locator("input[name='FiledEndDate']").fill(day)
            page.locator("#btnSearch").click()
            page.wait_for_load_state("networkidle")

            bot_check, rate_limited, unauthorized = self._detect_block()
            if bot_check or rate_limited or unauthorized:
                return SearchSignal(
                    bot_check=bot_check,
                    rate_limited=rate_limited,
                    unauthorized=unauthorized,
                )
            return SearchSignal(
                search_ui_present=self._any_selector(_SEARCH_UI_SELECTOR),
                results_table_present=self._any_selector(_RESULTS_TABLE_SELECTOR),
                row_count=self._page.locator(ROW_SELECTOR).count(),
                banner_present=self._any_text((_BANNER_SUBSTR,)),
            )
        except Exception as exc:
            return SearchSignal(error=True, error_type=type(exc).__name__)

    def harvest(self) -> HarvestResult:
        """Harvest CP/MC-51-CR (docket, href) pairs from the current results
        page (reads only the docket cell + sheet anchor; PD-3)."""
        return harvest_rows(self._page)

    def fetch(self, href: str) -> FetchSignal:
        """Fetch one docket-sheet PDF from a harvested href. Never raises."""
        self._fetches_since_restart += 1
        try:
            body = self._pdf_from_href(href)
            if body is None:
                # Sheet fetch failed / non-PDF: conservatively a block, not a
                # success (same polarity as transport.py's per-docket path).
                return FetchSignal(rate_limited=True)
            return FetchSignal(pdf_ok=True, pdf_bytes=body)
        except Exception as exc:
            return FetchSignal(error=True, error_type=type(exc).__name__)
