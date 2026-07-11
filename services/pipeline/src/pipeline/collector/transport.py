"""Playwright transport adapter for the collector (Task COL-1).

Ports Capstone's per-docket fetch path (``src/acquire/portal.py``:
``fetch_docket_pdf`` / ``pdf_from_href`` — the DocketNumber search variant) and
adds explicit block / bot-check detection so the engine can tell a clean miss
from a block. This is the ONLY module that touches Playwright, and it imports
it LAZILY inside methods so the package (and the whole test suite) imports
cleanly without the optional ``collector`` dependency group installed.

Configuration is headful by default (FIX 3): this is Capstone's proven,
1,600+-docket configuration and the honest posture — we do not optimize for
evading detection. ``headless=True`` is available but off by default.

Hard rules honored here:
  - A bot check / captcha is NEVER solved, bypassed, or automated; it is
    reported as a block and the engine applies the cooldown + streak.
  - NO screenshot, tracing, HAR, or video is captured in any code path,
    including error handling (FIX 4). Detection is presence/count only and
    never reads, prints, logs, or stores page text.

The CSS selectors and block signatures below were adapted from Capstone's
live-validated portal selectors; Capstone had NO block detection to port, so
the block/bot-check signatures are best-effort and MUST be confirmed by the
operator on the headful baseline run before any extended collection.
"""

from __future__ import annotations

from pipeline.collector.classification import FetchSignal

PORTAL = "https://ujsportal.pacourts.us/CaseSearch"

# Presence-only selectors for a bot-check / captcha interstitial. Count-based;
# no text is read out of these elements.
_BOT_CHECK_SELECTOR = (
    "iframe[src*='recaptcha'], iframe[src*='hcaptcha'], "
    "iframe[title*='captcha' i], #captcha, [data-captcha], .g-recaptcha"
)
# Case-insensitive phrases that mark a soft rate-limit / block page. Matched
# via a presence check (count > 0); the matched text is never captured.
_RATE_LIMIT_PATTERNS = (
    "too many requests",
    "unusual traffic",
    "please slow down",
    "rate limit",
    "access denied",
)


class PlaywrightTransport:
    """Owns a headful Chromium session; fetches one docket sheet per call.

    Use as a context manager so the browser is always closed::

        with PlaywrightTransport() as transport:
            engine.run(..., transport=transport, ...)
    """

    def __init__(self, headless: bool = False) -> None:
        self.headless = headless
        self._pw = None
        self._browser = None
        self._page = None

    def __enter__(self) -> PlaywrightTransport:
        # Lazy import: Playwright is only needed for an actual run, never for
        # import or tests. Raised clearly if the optional group is missing.
        try:
            from playwright.sync_api import sync_playwright
        except ModuleNotFoundError as exc:  # pragma: no cover - env-dependent
            raise RuntimeError(
                "Playwright is not installed. Install the optional collector "
                "group: `uv sync --group collector` and "
                "`uv run playwright install chromium`."
            ) from exc
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self.headless)
        self._page = self._browser.new_page()
        return self

    def __exit__(self, *exc: object) -> None:  # pragma: no cover - teardown
        if self._browser is not None:
            self._browser.close()
        if self._pw is not None:
            self._pw.stop()

    def _detect_block(self) -> tuple[bool, bool]:
        """Return ``(bot_check, rate_limited)`` from presence checks only.

        Never reads page text into a value that is returned, logged, or
        stored — only boolean/count observations. Best-effort; confirm on the
        baseline run.
        """
        page = self._page
        bot_check = False
        rate_limited = False
        try:
            bot_check = page.locator(_BOT_CHECK_SELECTOR).count() > 0
        except Exception:
            bot_check = False
        try:
            body = page.locator("body")
            for phrase in _RATE_LIMIT_PATTERNS:
                if body.get_by_text(phrase, exact=False).count() > 0:
                    rate_limited = True
                    break
        except Exception:
            rate_limited = False
        return bot_check, rate_limited

    def _pdf_from_href(self, href: str) -> bytes | None:
        """Fetch a docket-sheet PDF from its results-row href in-session.

        Ported from Capstone ``portal.pdf_from_href``. Returns PDF bytes, or
        ``None`` if the response is missing or is not a PDF.
        """
        page = self._page
        url = (
            href if href.startswith("http") else f"https://ujsportal.pacourts.us{href}"
        )
        resp = page.context.request.get(url)
        if not resp.ok:
            return None
        body = resp.body()
        if not body.startswith(b"%PDF"):
            return None
        return body

    def fetch(self, docket: str) -> FetchSignal:
        """Search one docket number and return a content-free FetchSignal.

        Never raises: any transport exception is returned as
        ``FetchSignal(error=True, error_type=<class name>)``.
        """
        try:
            page = self._page
            page.goto(PORTAL, wait_until="networkidle")
            bot_check, rate_limited = self._detect_block()
            if bot_check or rate_limited:
                return FetchSignal(bot_check=bot_check, rate_limited=rate_limited)

            page.locator("select[title='Search By']").select_option("DocketNumber")
            page.locator("input[name='DocketNumber']").fill(docket)
            page.locator("#btnSearch").click()
            page.wait_for_load_state("networkidle")

            bot_check, rate_limited = self._detect_block()
            if bot_check or rate_limited:
                return FetchSignal(bot_check=bot_check, rate_limited=rate_limited)

            links = page.locator("a[href*='CpDocketSheet']")
            rows = links.count()
            if rows == 0:
                # No result row for this number: a clean miss (coverage point).
                return FetchSignal(result_rows=0)

            href = links.first.get_attribute("href")
            if not href:
                # A row exists but no sheet link resolved — treat as a block
                # signal (the docket exists, so this is not a clean miss).
                return FetchSignal(result_rows=rows, rate_limited=True)

            body = self._pdf_from_href(href)
            if body is None:
                # The docket exists (row present) but the sheet fetch failed or
                # returned non-PDF: conservatively a block signal, not a miss.
                return FetchSignal(result_rows=rows, rate_limited=True)
            return FetchSignal(pdf_ok=True, result_rows=rows, pdf_bytes=body)
        except Exception as exc:
            return FetchSignal(error=True, error_type=type(exc).__name__)
