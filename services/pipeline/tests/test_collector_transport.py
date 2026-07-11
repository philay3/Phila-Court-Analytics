"""Transport tests — offline: a fake page/browser is injected into a
non-entered PlaywrightTransport, so Playwright is never imported."""

import sys

from pipeline.collector.classification import (
    OUTCOME_BLOCKED,
    OUTCOME_HIT,
    OUTCOME_MISS,
    classify,
)
from pipeline.collector.transport import (
    _SEARCH_UI_SELECTOR,
    PlaywrightTransport,
)


class FakeTextLocator:
    def __init__(self, count: int) -> None:
        self._count = count

    def count(self) -> int:
        return self._count


class FakeBody:
    def __init__(self, phrases: set[str]) -> None:
        self._phrases = phrases

    def get_by_text(self, phrase: str, exact: bool = False) -> FakeTextLocator:
        return FakeTextLocator(1 if phrase in self._phrases else 0)


class FakeLocator:
    def __init__(self, count: int = 0, href: str | None = None) -> None:
        self._count = count
        self._href = href

    def count(self) -> int:
        return self._count

    @property
    def first(self) -> "FakeLocator":
        return self

    def get_attribute(self, name: str) -> str | None:
        return self._href

    def select_option(self, *a, **k) -> None:
        pass

    def fill(self, *a, **k) -> None:
        pass

    def click(self, *a, **k) -> None:
        pass


class FakeResponse:
    def __init__(self, body: bytes, ok: bool = True) -> None:
        self._body = body
        self.ok = ok

    def body(self) -> bytes:
        return self._body


class FakeRequest:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def get(self, url: str) -> FakeResponse:
        return FakeResponse(self._body)


class FakeContext:
    def __init__(self, body: bytes) -> None:
        self.request = FakeRequest(body)


class FakePage:
    """Minimal portal stand-in driven by a page-state description."""

    def __init__(
        self,
        *,
        selectors: dict[str, int] | None = None,
        body_phrases: set[str] | None = None,
        href: str | None = None,
        pdf_bytes: bytes = b"%PDF-1.7 sheet",
    ) -> None:
        self._selectors = selectors or {}
        self._body_phrases = body_phrases or set()
        self._href = href
        self.context = FakeContext(pdf_bytes)

    def goto(self, *a, **k) -> None:
        pass

    def wait_for_load_state(self, *a, **k) -> None:
        pass

    def locator(self, selector: str):
        if selector == "body":
            return FakeBody(self._body_phrases)
        if "CpDocketSheet" in selector:
            return FakeLocator(count=1 if self._href else 0, href=self._href)
        return FakeLocator(count=self._selectors.get(selector, 0))


def _transport_with(page: FakePage) -> PlaywrightTransport:
    t = PlaywrightTransport()
    t._page = page
    return t


def test_playwright_not_imported_by_these_tests():
    assert "playwright" not in sys.modules


def test_positive_no_results_requires_search_ui():
    page = FakePage(selectors={_SEARCH_UI_SELECTOR: 1})
    signal = _transport_with(page).fetch("MC-51-CR-0000001-2025")
    assert signal.no_results is True
    assert classify(signal) == OUTCOME_MISS


def test_block_interstitial_without_search_ui_fails_closed():
    # No docket-sheet link, no search UI, no known block text: every positive
    # marker stays False, so the classifier blocks it (FIX 1).
    page = FakePage(selectors={})
    signal = _transport_with(page).fetch("MC-51-CR-0000001-2025")
    assert signal.no_results is False
    assert signal.pdf_ok is False
    assert classify(signal) == OUTCOME_BLOCKED


def test_unauthorized_signature_recognized():
    for phrase in ("unauthorized", "not authorized"):
        page = FakePage(body_phrases={phrase})
        signal = _transport_with(page).fetch("MC-51-CR-0000001-2025")
        assert signal.unauthorized is True
        assert classify(signal) == OUTCOME_BLOCKED


def test_hit_returns_pdf_bytes():
    page = FakePage(href="/Report/CpDocketSheet?id=abc", pdf_bytes=b"%PDF-1.7 x")
    signal = _transport_with(page).fetch("MC-51-CR-0000001-2025")
    assert signal.pdf_ok is True
    assert signal.pdf_bytes == b"%PDF-1.7 x"
    assert classify(signal) == OUTCOME_HIT


def test_detect_block_reads_only_presence():
    page = FakePage(body_phrases={"too many requests"})
    bot, rate, unauth = _transport_with(page)._detect_block()
    assert (bot, rate, unauth) == (False, True, False)


# --- FIX 3: graceful teardown ---------------------------------------------


class BoomBrowser:
    def close(self) -> None:
        raise RuntimeError("Connection closed while reading from the driver")


class OkPw:
    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


class BoomPw:
    def stop(self) -> None:
        raise RuntimeError("driver already gone")


def test_exit_tolerates_dead_browser_close():
    t = PlaywrightTransport()
    t._browser = BoomBrowser()
    t._pw = OkPw()
    t.__exit__(None, None, None)  # must not raise
    assert t._pw.stopped is True


def test_exit_tolerates_failing_stop():
    t = PlaywrightTransport()
    t._browser = None
    t._pw = BoomPw()
    t.__exit__(None, None, None)  # must not raise
