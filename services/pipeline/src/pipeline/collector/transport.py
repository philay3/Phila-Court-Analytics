"""Playwright transport adapter for the collector (Task COL-1 / COL-1a).

Ports Capstone's per-docket fetch path (``src/acquire/portal.py``:
``fetch_docket_pdf`` / ``pdf_from_href`` — the DocketNumber search variant) and
adds POSITIVE identification of the two non-block states so the classifier can
fail closed. This is the ONLY module that touches Playwright, and it imports it
LAZILY inside methods so the package (and the whole test suite) imports cleanly
without the optional ``collector`` dependency group installed.

Configuration is headful by default (FIX 3, COL-1): Capstone's proven,
1,600+-docket configuration and the honest posture — we do not optimize for
evading detection. ``headless=True`` is available but off by default.

Hard rules honored here:
  - A bot check / captcha is NEVER solved, bypassed, or automated; it is
    reported as a block and the engine applies the cooldown + streak.
  - NO screenshot, tracing, HAR, or video is captured in any code path,
    including error handling. Detection is presence/count only and never
    reads, prints, logs, or stores page text.

Fail-closed observation (COL-1a). ``fetch`` emits ``no_results=True`` ONLY when
the portal's genuine no-results state is positively identified: the search UI is
still rendered (``select[title='Search By']`` / ``#btnSearch``) with zero
docket-sheet links and no recognized block signature. A block interstitial lacks
that UI, so it yields no positive marker and the classifier blocks it. On top of
that structural default, an ``unauthorized``/``not authorized`` page signature is
recognized explicitly (COL-1a, FIX 2).
"""

from __future__ import annotations

import logging

from pipeline.collector.classification import FetchSignal

logger = logging.getLogger("pipeline.collector")

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
# The block page observed on run-20260711-034851 around sequence 0000122.
# Two case-insensitive substrings; either match ⇒ blocked (COL-1a, FIX 2).
# Substring (not exact-phrase) matching: operator recall is "unauthorized
# request" but is not screenshot-verified, and a false positive costs only a
# conservative cooldown.
_UNAUTHORIZED_PATTERNS = (
    "unauthorized",
    "not authorized",
)
# Positive marker that the DocketNumber search actually rendered its results UI
# (present on both hit and genuine no-results pages; absent on a block
# interstitial). Basis for the fail-closed no-results identification.
_SEARCH_UI_SELECTOR = "select[title='Search By'], #btnSearch"
_DOCKET_SHEET_SELECTOR = "a[href*='CpDocketSheet']"


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

    def __exit__(self, *exc: object) -> None:
        # Graceful teardown (COL-1a, FIX 3): a SIGINT abort can reach the driver
        # subprocess before we close, so close()/stop() may throw
        # "Connection closed while reading from the driver". The run report is
        # already written by the time we get here, so swallow teardown failures
        # rather than let them mask a clean operator_abort exit.
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

    def _detect_block(self) -> tuple[bool, bool, bool]:
        """Return ``(bot_check, rate_limited, unauthorized)`` from presence
        checks only.

        Never reads page text into a value that is returned, logged, or
        stored — only boolean/count observations. Best-effort; confirm on the
        baseline run.
        """
        bot_check = self._any_selector(_BOT_CHECK_SELECTOR)
        rate_limited = self._any_text(_RATE_LIMIT_PATTERNS)
        unauthorized = self._any_text(_UNAUTHORIZED_PATTERNS)
        return bot_check, rate_limited, unauthorized

    def _search_ui_present(self) -> bool:
        """True if the search UI rendered (the positive no-results basis)."""
        return self._any_selector(_SEARCH_UI_SELECTOR)

    def _any_selector(self, selector: str) -> bool:
        try:
            return self._page.locator(selector).count() > 0
        except Exception:
            return False

    def _any_text(self, patterns: tuple[str, ...]) -> bool:
        try:
            body = self._page.locator("body")
            for phrase in patterns:
                if body.get_by_text(phrase, exact=False).count() > 0:
                    return True
        except Exception:
            return False
        return False

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
            bot_check, rate_limited, unauthorized = self._detect_block()
            if bot_check or rate_limited or unauthorized:
                return FetchSignal(
                    bot_check=bot_check,
                    rate_limited=rate_limited,
                    unauthorized=unauthorized,
                )

            page.locator("select[title='Search By']").select_option("DocketNumber")
            page.locator("input[name='DocketNumber']").fill(docket)
            page.locator("#btnSearch").click()
            page.wait_for_load_state("networkidle")

            # Block detection runs BEFORE the no-results check so a block page
            # that superficially keeps the search UI is still caught.
            bot_check, rate_limited, unauthorized = self._detect_block()
            if bot_check or rate_limited or unauthorized:
                return FetchSignal(
                    bot_check=bot_check,
                    rate_limited=rate_limited,
                    unauthorized=unauthorized,
                )

            links = page.locator(_DOCKET_SHEET_SELECTOR)
            if links.count() > 0:
                href = links.first.get_attribute("href")
                if not href:
                    # A row exists but no sheet link resolved: the docket
                    # exists, so this is not a clean miss — fail closed.
                    return FetchSignal(rate_limited=True)
                body = self._pdf_from_href(href)
                if body is None:
                    # Docket exists but the sheet fetch failed / returned
                    # non-PDF: conservatively a block, not a miss.
                    return FetchSignal(rate_limited=True)
                return FetchSignal(pdf_ok=True, pdf_bytes=body)

            # No docket-sheet link. Only positively call this a miss when the
            # search UI is still present (COL-1a, FIX 1). Otherwise leave every
            # positive marker False so the classifier fails closed to blocked.
            if self._search_ui_present():
                return FetchSignal(no_results=True)
            return FetchSignal()
        except Exception as exc:
            return FetchSignal(error=True, error_type=type(exc).__name__)
