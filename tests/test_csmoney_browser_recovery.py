from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.app import csmoney_data, csmoney_search, csmoney_worker as worker
from backend.app.csmoney_worker import process_search as process_search_job
from backend.app.marketplaces.csmoney import (
    CsMoneyBlockedError, CsMoneyBrowserError, CsMoneyRequestError,
    capture_search, capture_variant,
)


CLOSED = "Page.goto: Target page, context or browser has been closed"


class Page:
    def __init__(self, *, failure=None, failure_stage="goto", closed=False):
        self.failure = failure
        self.failure_stage = failure_stage
        self.closed = closed

    def is_closed(self):
        return self.closed

    def close(self):
        self.closed = True

    def goto(self, *_args, **_kwargs):
        if self.failure is not None and self.failure_stage == "goto":
            raise self.failure
        return SimpleNamespace(status=200)

    def locator(self, _selector):
        def contents():
            if self.failure is not None and self.failure_stage == "embedded":
                raise self.failure
            return [] if self.failure_stage == "content" else ['{"inventory":{"items":[]}}']
        return SimpleNamespace(all_text_contents=contents)

    def content(self):
        if self.failure is not None:
            raise self.failure
        return ""


@pytest.mark.parametrize("capture", [capture_variant, capture_search])
@pytest.mark.parametrize("stage", ["goto", "embedded", "content"])
@pytest.mark.parametrize("message", [CLOSED, "Page crashed", "Browser closed", "Browser crashed"])
def test_adapter_classifies_browser_failures_at_every_page_operation(capture, stage, message):
    with pytest.raises(CsMoneyBrowserError, match="closed or crashed"):
        capture(Page(failure=RuntimeError(message), failure_stage=stage), "Redline")


@pytest.mark.parametrize("capture", [capture_variant, capture_search])
def test_navigation_timeout_remains_a_request_error(capture):
    with pytest.raises(CsMoneyRequestError) as raised:
        capture(Page(failure=TimeoutError("Timeout 120000ms exceeded")), "Redline")
    assert not isinstance(raised.value, CsMoneyBrowserError)


class Clock:
    now = 1000.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class Browser:
    def __init__(self, page=None, *, connected=True, new_page_error=None):
        self.page = page or Page()
        self.page.context = SimpleNamespace(
            new_page=lambda: Page(failure=self.page.failure, failure_stage=self.page.failure_stage),
            route=lambda *_args: None,
        )
        self.connected = connected
        self.new_page_error = new_page_error
        self.exited = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.exited = True

    def _context_page(self):
        if self.new_page_error:
            raise self.new_page_error
        return self.page

    def new_page(self, **_kwargs):
        raise AssertionError("Use an explicit context: browser.new_page() cannot own additional tabs")

    def is_connected(self):
        return self.connected

    def new_context(self, **_kwargs):
        return SimpleNamespace(new_page=self._context_page, route=lambda *_args: None)


@pytest.fixture
def runtime(monkeypatch):
    clock = Clock()
    connection = SimpleNamespace(__enter__=lambda _self: None)

    class Connection:
        def __enter__(self):
            return connection

        def __exit__(self, *_args):
            pass

    monkeypatch.setattr(worker, "get_connection", Connection)
    monkeypatch.setattr(worker, "ensure_schema", lambda _connection: None)
    monkeypatch.setattr(worker, "schedule_candidates", lambda: 0)
    monkeypatch.setattr(worker, "process_search", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(worker, "container_memory_bytes", lambda: None)
    monkeypatch.setattr(worker, "time", clock)
    for name, value in {
        "CSMONEY_MIN_REQUEST_INTERVAL_SECONDS": "10",
        "CSMONEY_BROWSER_MAX_SESSION_SECONDS": "1800",
        "CSMONEY_BROWSER_MAX_SESSION_JOBS": "100",
        "CSMONEY_BROWSER_MEMORY_LIMIT_MB": "1536",
        "CSMONEY_BROWSER_RESTART_DELAY_SECONDS": "10",
        "CSMONEY_BROWSER_MAX_RESTARTS": "3",
    }.items():
        monkeypatch.setenv(name, value)
    return clock


def test_closed_browser_recovers_same_catalogue_job_without_wiki_or_provider_backoff(monkeypatch, runtime):
    actions = []
    browsers = [Browser(Page(failure=RuntimeError(CLOSED))), Browser()]
    pending = iter(browsers)
    monkeypatch.setattr(worker, "_new_browser", lambda: next(pending))
    monkeypatch.setattr(worker, "claim_refresh_job", lambda: {"variant_id": "redline", "attempts": 93})
    monkeypatch.setattr(worker, "load_variant_context", lambda _id: {"market_hash_name": "Redline"})
    monkeypatch.setattr(worker, "record_refresh_error", lambda *args: actions.append(("error", args)))
    monkeypatch.setattr(worker, "release_refresh_job", lambda _id, **kwargs: actions.append(("release", kwargs)))
    monkeypatch.setattr(worker, "defer_refresh_job", lambda *_args, **_kwargs: pytest.fail("Provider backoff used"))
    monkeypatch.setattr(worker, "_wiki_summary", lambda *_args: pytest.fail("Crash opened the 403 circuit"))
    monkeypatch.setattr(worker, "store_variant_capture", lambda *_args: actions.append(("store",)) or 0)
    monkeypatch.setattr(worker, "complete_refresh_job", lambda _id: actions.append(("complete",)))

    worker.run(once=True)

    assert [action[0] for action in actions] == ["error", "release", "store", "complete"]
    assert actions[1][1] == {"seconds": 10}
    assert all(browser.exited for browser in browsers)
    assert runtime.now == 1010.0


@pytest.mark.parametrize("first", [Browser(Page(closed=True)), Browser(connected=False),
                                    Browser(new_page_error=RuntimeError(CLOSED))])
def test_dead_browser_is_replaced_before_claiming_next_job(monkeypatch, runtime, first):
    second = Browser()
    browsers = iter([first, second])
    monkeypatch.setattr(worker, "_new_browser", lambda: next(browsers))
    pages = []
    monkeypatch.setattr(worker, "process_one", lambda page: pages.append(page) or True)
    worker.run(once=True)
    assert pages == [second.page]
    assert first.exited and second.exited


def test_repeated_browser_failures_exit_worker_after_bounded_restarts(monkeypatch, runtime):
    browsers = []

    def create():
        browser = Browser(Page(closed=True))
        browsers.append(browser)
        return browser

    monkeypatch.setattr(worker, "_new_browser", create)
    monkeypatch.setattr(worker, "process_one", lambda _page: pytest.fail("Dead browser claimed a job"))
    with pytest.raises(RuntimeError, match="recovery exhausted"):
        worker.run()
    assert len(browsers) == 3
    assert all(browser.exited for browser in browsers)
    assert runtime.now == 1020.0


@pytest.mark.parametrize("rotation", ["age", "job_limit", "memory"])
def test_session_rotation_keeps_processing_on_a_new_browser(monkeypatch, runtime, rotation):
    browsers, pages = [], []

    def create():
        browser = Browser()
        browsers.append(browser)
        return browser

    class StopWorker(Exception):
        pass

    def process(page):
        pages.append(page)
        if len(pages) == 2:
            raise StopWorker()
        if rotation == "age":
            runtime.now += 1800
        return True

    monkeypatch.setattr(worker, "_new_browser", create)
    monkeypatch.setattr(worker, "process_one", process)
    if rotation == "job_limit":
        monkeypatch.setenv("CSMONEY_BROWSER_MAX_SESSION_JOBS", "1")
    if rotation == "memory":
        memory = iter([500, 1600, 500])
        monkeypatch.setattr(worker, "container_memory_bytes", lambda: next(memory) * 1024 * 1024)
    with pytest.raises(StopWorker):
        worker.run()
    assert len(browsers) == 2
    assert pages == [browser.page for browser in browsers]
    assert all(browser.exited for browser in browsers)
    if rotation == "memory":
        # Only the normal request interval applies; planned rotation adds no recovery pause.
        assert runtime.now == 1010.0


def test_memory_pressure_without_progress_exits_instead_of_launching_forever(monkeypatch, runtime):
    browsers = []
    monkeypatch.setattr(worker, "container_memory_bytes", lambda: 1600 * 1024 * 1024)
    monkeypatch.setattr(worker, "process_one", lambda _page: pytest.fail("Job claimed above memory limit"))

    def create():
        browser = Browser()
        browsers.append(browser)
        return browser

    monkeypatch.setattr(worker, "_new_browser", create)
    with pytest.raises(RuntimeError, match="recovery exhausted"):
        worker.run()
    assert len(browsers) == 3
    assert all(browser.exited for browser in browsers)


def test_403_still_closes_browser_and_uses_wiki_during_cooldown(monkeypatch, runtime):
    browser = Browser()
    monkeypatch.setattr(worker, "_new_browser", lambda: browser)
    pages = []

    class StopWorker(Exception):
        pass

    def process(page):
        pages.append(page)
        if page is not None:
            raise CsMoneyBlockedError("CS.MONEY page returned 403")
        raise StopWorker()

    monkeypatch.setattr(worker, "process_one", process)
    with pytest.raises(StopWorker):
        worker.run()
    assert pages == [browser.page, None]
    assert browser.exited
    assert runtime.now == 1010.0


@pytest.mark.parametrize("stage", ["new_page", "capture"])
def test_search_browser_failure_remains_pending_and_propagates(monkeypatch, stage):
    request_id = uuid4()
    actions = []
    tab = SimpleNamespace(close=lambda: actions.append("closed"))

    def create_tab():
        if stage == "new_page":
            raise RuntimeError(CLOSED)
        return tab

    monkeypatch.setattr(worker, "claim_search", lambda: {"request_id": request_id, "query": "Redline"})
    monkeypatch.setattr(worker, "defer_search", lambda *args, **kwargs: actions.append((args, kwargs)))
    monkeypatch.setattr(worker, "finish_search", lambda *_args, **_kwargs: pytest.fail("Search marked terminal"))
    monkeypatch.setattr(worker, "capture_search", lambda *_args: (_ for _ in ()).throw(CsMoneyBrowserError(CLOSED)))
    with pytest.raises(CsMoneyBrowserError):
        worker.process_search(SimpleNamespace(context=SimpleNamespace(new_page=create_tab)))
    assert actions[0] == ((request_id,), {"seconds": 10})
    if stage == "capture":
        assert actions[1] == "closed"


def test_search_tab_teardown_does_not_mask_storefront_403(monkeypatch):
    def close():
        raise RuntimeError(CLOSED)

    tab = SimpleNamespace(close=close)
    page = SimpleNamespace(context=SimpleNamespace(new_page=lambda: tab))
    monkeypatch.setattr(worker, "claim_search", lambda: {"request_id": uuid4(), "query": "Redline"})
    monkeypatch.setattr(worker, "finish_search", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(worker, "capture_search", lambda *_args: (_ for _ in ()).throw(CsMoneyBlockedError("403")))
    with pytest.raises(CsMoneyBlockedError):
        worker.process_search(page)


def test_search_is_retried_in_new_session_and_finishes_successfully(monkeypatch, runtime):
    # Exercise the real search handler through the worker loop, not just its raised error.
    monkeypatch.setattr(worker, "process_search", process_search_job)
    request_id = uuid4()
    actions = []
    tabs = [SimpleNamespace(failed=True, close=lambda: actions.append("close_first")),
            SimpleNamespace(failed=False, close=lambda: actions.append("close_second"))]
    browsers = [Browser(), Browser()]
    for browser, tab in zip(browsers, tabs):
        browser.page.context = SimpleNamespace(new_page=lambda tab=tab: tab, route=lambda *_args: None)
    pending = iter(browsers)
    monkeypatch.setattr(worker, "_new_browser", lambda: next(pending))
    monkeypatch.setattr(worker, "claim_search", lambda: {"request_id": request_id, "query": "Redline"})
    monkeypatch.setattr(worker, "defer_search", lambda *args, **kwargs: actions.append("deferred"))
    monkeypatch.setattr(worker, "finish_search", lambda _id, status, **kwargs: actions.append(status))
    monkeypatch.setattr(worker, "process_one", lambda _page: pytest.fail("Catalogue claimed during search"))

    def capture(tab, _query):
        if tab.failed:
            raise CsMoneyBrowserError(CLOSED)
        return {"listings": [{"listing_id": "1"}]}

    monkeypatch.setattr(worker, "capture_search", capture)
    worker.run(once=True)
    assert actions == ["deferred", "close_first", "complete", "close_second"]
    assert all(browser.exited for browser in browsers)


@pytest.mark.parametrize("values,expected", [
    ({"memory.current": "1234"}, 1234),
    ({"memory.usage_in_bytes": "2345"}, 2345),
    ({"memory.current": "invalid", "memory.usage_in_bytes": "3456"}, 3456),
    ({"memory.current": "2000", "memory.stat": "inactive_file 1200\nanon 700\n"}, 800),
    ({"memory.usage_in_bytes": "2000", "memory.stat": "total_inactive_file 1100\n"}, 900),
    ({"memory.current": "2000", "memory.stat": "invalid stat line"}, 2000),
    ({"memory.current": "2000", "memory.stat": "inactive_file 3000\n"}, 0),
    ({"memory.current": "-1"}, None),
    ({}, None),
])
def test_container_memory_handles_cgroup_versions_and_unavailable_metrics(monkeypatch, values, expected):
    def read(path):
        if path.name not in values:
            raise FileNotFoundError()
        return values[path.name]

    monkeypatch.setattr(worker.Path, "read_text", read)
    assert worker.container_memory_bytes() == expected


def test_browser_retry_preserves_priority_attempt_budget_and_search_expiry(monkeypatch):
    statements = []

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def execute(self, sql, params):
            statements.append((sql, params))

    monkeypatch.setattr(csmoney_data, "get_connection", Connection)
    monkeypatch.setattr(csmoney_search, "get_connection", Connection)
    csmoney_data.release_refresh_job("redline", seconds=10)
    request_id = uuid4()
    csmoney_search.defer_search(request_id, seconds=10)
    variant_sql, variant_params = statements[0]
    assert "attempts = GREATEST(attempts - 1, 0)" in variant_sql
    assert "priority =" not in variant_sql
    assert variant_params == (10, "redline")
    search_sql, search_params = statements[1]
    assert "expires_at =" not in search_sql
    assert "status = 'running'" in search_sql
    assert search_params == (10, request_id)


@pytest.mark.parametrize("error", [None, CsMoneyBlockedError("403"), CsMoneyBrowserError(CLOSED)])
def test_catalogue_capture_uses_new_tab_and_always_closes_it(monkeypatch, error):
    actions = []
    tab = SimpleNamespace(close=lambda: actions.append("close"))
    anchor = SimpleNamespace(context=SimpleNamespace(new_page=lambda: actions.append("new_page") or tab))

    def capture(page, name, *, phase):
        assert page is tab
        assert name == "Redline" and phase is None
        actions.append("capture")
        if error:
            raise error
        return {"listings": []}

    monkeypatch.setattr(worker, "capture_variant", capture)
    if error:
        with pytest.raises(type(error)):
            worker._capture_variant_in_tab(anchor, "Redline", phase=None)
    else:
        assert worker._capture_variant_in_tab(anchor, "Redline", phase=None) == {"listings": []}
    assert actions == ["new_page", "capture", "close"]


@pytest.mark.parametrize("resource,blocked", [
    ("image", True), ("media", True), ("font", True),
    ("document", False), ("script", False), ("stylesheet", False), ("xhr", False), ("fetch", False),
])
def test_collection_routing_blocks_only_decorative_resources(resource, blocked):
    handlers = []
    context = SimpleNamespace(route=lambda pattern, handler: handlers.append(handler))
    worker._configure_collection_context(context)
    actions = []
    route = SimpleNamespace(request=SimpleNamespace(resource_type=resource),
                            abort=lambda: actions.append("abort"), continue_=lambda: actions.append("continue"))
    handlers[0](route)
    assert actions == ["abort" if blocked else "continue"]
