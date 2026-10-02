"""Background CS.MONEY collector. Run with ``python -m backend.app.csmoney_worker``."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
import time
from urllib.error import HTTPError, URLError

from .csmoney_data import (
    cache_ttl_seconds,
    claim_refresh_job,
    complete_refresh_job,
    defer_refresh_job,
    enqueue_variants,
    load_variant_context,
    record_refresh_error,
    release_refresh_job,
    store_variant_capture,
    store_wiki_market_summary,
)
from .csmoney_demand import get_observed_sales_priorities
from .csmoney_wiki import WikiPriceError, fetch_market_summary
from .csmoney_search import claim_search, defer_search, finish_search
from .database import ensure_schema, get_connection
from .marketplaces.csmoney import (CsMoneyBlockedError, CsMoneyBrowserError, CsMoneyRequestError,
                                  capture_search, capture_variant, is_browser_failure, storefront_url)


LOG = logging.getLogger(__name__)


def _positive_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


def _browser_retry_delay() -> int:
    return _positive_env("CSMONEY_BROWSER_RESTART_DELAY_SECONDS", 10)


def container_memory_bytes() -> int | None:
    """Read total worker/container usage, including Firefox, on cgroup v2 or v1."""
    for filename in ("/sys/fs/cgroup/memory.current",
                     "/sys/fs/cgroup/memory/memory.usage_in_bytes"):
        try:
            value = int(Path(filename).read_text().strip())
        except (OSError, ValueError):
            continue
        if value >= 0:
            return value
    return None


def _new_browser():
    from camoufox.sync_api import Camoufox

    return Camoufox(headless=True)


def schedule_candidates(*, batch_size: int = 30) -> int:
    """Mix observed demand with a oldest-first sweep of the whole catalogue."""
    ttl = cache_ttl_seconds()
    crawl_ttl = _positive_env("CSMONEY_CRAWL_TTL_SECONDS", 86400)
    hot_ids: list[str] = []
    observed = get_observed_sales_priorities(limit=200)
    if observed:
        candidate_ids = [entry["variant_id"] for entry in observed]
        with get_connection() as connection:
            due_hot_ids = {
                row["id"] for row in connection.execute(
                    """
                    SELECT v.id FROM skin_variants v
                    LEFT JOIN csmoney_variant_state st ON st.variant_id = v.id
                    WHERE v.id = ANY(%s)
                      AND (st.fetched_at IS NULL
                           OR st.fetched_at < NOW() - (%s * INTERVAL '1 second'))
                      AND (st.last_error IS NULL OR st.last_attempt_at IS NULL
                           OR st.last_attempt_at < NOW() - INTERVAL '15 minutes')
                    """,
                    (candidate_ids, ttl),
                ).fetchall()
            }
        hot_ids = [variant_id for variant_id in candidate_ids if variant_id in due_hot_ids][:10]
    added = enqueue_variants(hot_ids, priority=50)
    with get_connection() as connection:
        due = [
            row["id"]
            for row in connection.execute(
                """
                SELECT v.id FROM skin_variants v
                LEFT JOIN csmoney_variant_state st ON st.variant_id = v.id
                WHERE v.market_hash_name IS NOT NULL
                  AND NOT (v.id = ANY(%s))
                  AND (st.fetched_at IS NULL
                       OR st.fetched_at < NOW() - (%s * INTERVAL '1 second'))
                  AND (st.last_error IS NULL OR st.last_attempt_at IS NULL
                       OR st.last_attempt_at < NOW() - INTERVAL '15 minutes')
                  AND (st.exact_matches <> 0 OR st.is_partial IS NOT TRUE
                       OR st.last_attempt_at IS NULL
                       OR st.last_attempt_at < NOW() - (%s * INTERVAL '1 second'))
                ORDER BY st.fetched_at NULLS FIRST, v.id
                LIMIT %s
                """,
                (hot_ids, crawl_ttl, crawl_ttl, max(0, batch_size - len(hot_ids))),
            ).fetchall()
        ]
    added += enqueue_variants(due, priority=1)
    return added


def _wiki_summary(variant_id: str, context: dict) -> None:
    summary = fetch_market_summary(context["item_name"], context["market_hash_name"])
    store_wiki_market_summary(
        variant_id, summary, item_url=storefront_url(context["market_hash_name"]),
    )
    complete_refresh_job(variant_id)
    LOG.info("CS.MONEY %s: source=wiki_market_summary result=ok price_cents=%d count=%d partial=true",
             variant_id, summary["price_cents"], summary["quantity"])


def _wiki_failure(variant_id: str, error: Exception, *, storefront_403: bool = False,
                  attempts: int = 1) -> None:
    """Log/persist an allowlisted outcome, never provider exception contents."""
    if isinstance(error, HTTPError):
        result = "http_403_challenge" if error.code == 403 else "http_error"
    elif isinstance(error, TimeoutError) or (
        isinstance(error, URLError) and isinstance(error.reason, TimeoutError)
    ):
        result = "timeout"
    elif isinstance(error, WikiPriceError):
        result = error.result if error.result in {"empty", "network_error"} else "malformed"
    elif isinstance(error, ValueError):
        result = "malformed"
    else:
        result = "network_error"
    prefix = "Storefront 403; " if storefront_403 else ""
    record_refresh_error(variant_id, f"{prefix}Wiki Market summary unavailable: {result}")
    defer_refresh_job(variant_id, seconds=min(900, 60 * attempts))
    LOG.warning("CS.MONEY %s: source=wiki_market_summary result=%s", variant_id, result)


def process_search(page, *, circuit_open: bool = False) -> bool:
    """Process the priority text queue on a fresh tab in the current context."""
    job = claim_search()
    if job is None:
        return False
    request_id = job["request_id"]
    if circuit_open:
        finish_search(request_id, "blocked", error="CS.MONEY storefront is temporarily blocked")
        return True
    tab = None
    try:
        tab = page.context.new_page()
        capture = capture_search(tab, job["query"])
        finish_search(request_id, "complete" if capture["listings"] else "empty",
                      result=capture)
    except CsMoneyBrowserError:
        defer_search(request_id, seconds=_browser_retry_delay())
        raise
    except CsMoneyBlockedError as error:
        finish_search(request_id, "blocked", error=str(error))
        raise
    except CsMoneyRequestError as error:
        finish_search(request_id, "error", error=str(error))
    except Exception as error:
        # new_page() can fail before the adapter gets a chance to classify it.
        if is_browser_failure(error):
            defer_search(request_id, seconds=_browser_retry_delay())
            raise CsMoneyBrowserError("CS.MONEY search browser unavailable") from error
        finish_search(request_id, "error", error="Search failed; inspect worker logs")
        LOG.exception("Unexpected CS.MONEY search failure for %s", request_id)
    finally:
        if tab is not None:
            try:
                tab.close()
            except Exception as error:
                if is_browser_failure(error):
                    # Preserve the request's outcome (especially a 403). The outer
                    # loop checks the shared browser before claiming another job.
                    LOG.debug("CS.MONEY search tab already unavailable for %s", request_id)
                else:
                    LOG.exception("Could not close CS.MONEY search tab for %s", request_id)
    return True


def process_one(page) -> bool:
    """Process one leased job; return false when there was no ready job."""
    job = claim_refresh_job()
    if job is None:
        return False
    variant_id = job["variant_id"]
    context = load_variant_context(variant_id)
    if context is None:
        complete_refresh_job(variant_id)
        return True
    if page is None:
        try:
            _wiki_summary(variant_id, context)
        except (WikiPriceError, OSError, TimeoutError, ValueError) as error:
            _wiki_failure(variant_id, error, attempts=job["attempts"])
        return True
    try:
        capture = capture_variant(
            page,
            context["market_hash_name"],
            phase=context.get("phase"),
        )
        stored = store_variant_capture(variant_id, capture)
    except CsMoneyBrowserError:
        record_refresh_error(variant_id, "Browser session unavailable; restarting collector browser")
        release_refresh_job(variant_id, seconds=_browser_retry_delay())
        raise
    except CsMoneyRequestError as error:
        message = str(error)
        if isinstance(error, CsMoneyBlockedError) or "403" in message or "429" in message:
            # Stop storefront requests globally while using the separate
            # public Wiki Market summary. One 403 is enough to trip the gate.
            try:
                _wiki_summary(variant_id, context)
            except (WikiPriceError, OSError, TimeoutError, ValueError) as wiki_error:
                _wiki_failure(variant_id, wiki_error, storefront_403=True,
                              attempts=job["attempts"])
            raise
        record_refresh_error(variant_id, message)
        retry_seconds = min(900, 60 * job["attempts"])
        defer_refresh_job(variant_id, seconds=retry_seconds)
        LOG.warning("CS.MONEY %s: %s; retry in %ds", variant_id, message, retry_seconds)
    except Exception:
        record_refresh_error(variant_id, "Collector failed; inspect worker logs")
        defer_refresh_job(variant_id, seconds=min(900, 60 * job["attempts"]))
        LOG.exception("Unexpected CS.MONEY collector failure for %s", variant_id)
    else:
        complete_refresh_job(variant_id)
        LOG.info(
            "CS.MONEY %s: %d listings from %d page items, partial=%s",
            variant_id, stored, capture["page_items"], capture["is_partial"],
        )
    return True


def run(*, once: bool = False) -> None:
    """Reuse bounded browser sessions; recover infrastructure failures separately from 403s."""
    with get_connection() as connection:
        ensure_schema(connection)
    request_interval = _positive_env("CSMONEY_MIN_REQUEST_INTERVAL_SECONDS", 10)
    schedule_interval = _positive_env("CSMONEY_SCHEDULE_INTERVAL_SECONDS", 300)
    storefront_retry = _positive_env("CSMONEY_STOREFRONT_RETRY_SECONDS", 21600)
    max_session_seconds = _positive_env("CSMONEY_BROWSER_MAX_SESSION_SECONDS", 1800)
    max_session_jobs = _positive_env("CSMONEY_BROWSER_MAX_SESSION_JOBS", 100)
    memory_limit = _positive_env("CSMONEY_BROWSER_MEMORY_LIMIT_MB", 1536) * 1024 * 1024
    max_restarts = _positive_env("CSMONEY_BROWSER_MAX_RESTARTS", 3)
    restart_failures = 0
    next_schedule = 0.0
    last_request = 0.0
    blocked_until = 0.0
    while True:
        if time.monotonic() < blocked_until:
            now = time.monotonic()
            if now >= next_schedule:
                scheduled = schedule_candidates()
                LOG.info("CS.MONEY scheduled %d candidate jobs", scheduled)
                next_schedule = now + schedule_interval
            remaining = request_interval - (time.monotonic() - last_request)
            if last_request and remaining > 0:
                time.sleep(remaining)
            processed = process_search(None, circuit_open=True) or process_one(None)
            if processed:
                last_request = time.monotonic()
            if once:
                return
            if not processed:
                time.sleep(5)
            continue
        restart_reason = None
        session_jobs = 0
        session_started = time.monotonic()
        try:
            with _new_browser() as browser:
                try:
                    page = browser.new_page()
                except Exception as error:
                    if not is_browser_failure(error):
                        raise
                    raise CsMoneyBrowserError("CS.MONEY browser closed during page creation") from error
                session_started = time.monotonic()
                next_metrics = session_started
                LOG.info("CS.MONEY browser session started")
                while True:
                    now = time.monotonic()
                    if now >= next_schedule:
                        scheduled = schedule_candidates()
                        LOG.info("CS.MONEY scheduled %d candidate jobs", scheduled)
                        next_schedule = now + schedule_interval
                    remaining = request_interval - (time.monotonic() - last_request)
                    if last_request and remaining > 0:
                        time.sleep(remaining)
                    # Check before claiming a job: a disconnected browser must not drain the queue.
                    if page.is_closed() or not browser.is_connected():
                        raise CsMoneyBrowserError("CS.MONEY browser disconnected before request")
                    memory = container_memory_bytes()
                    age = time.monotonic() - session_started
                    if time.monotonic() >= next_metrics:
                        LOG.info("CS.MONEY browser session jobs=%d age_seconds=%d memory_mb=%s",
                                 session_jobs, int(age),
                                 memory // (1024 * 1024) if memory is not None else "unavailable")
                        next_metrics = time.monotonic() + schedule_interval
                    if memory is not None and memory >= memory_limit:
                        restart_reason = "memory"
                    elif age >= max_session_seconds:
                        restart_reason = "age"
                    elif session_jobs >= max_session_jobs:
                        restart_reason = "job_limit"
                    if restart_reason:
                        LOG.info("CS.MONEY browser rotation reason=%s jobs=%d age_seconds=%d memory_mb=%s",
                                 restart_reason, session_jobs, int(age),
                                 memory // (1024 * 1024) if memory is not None else "unavailable")
                        break
                    try:
                        processed = process_search(page) or process_one(page)
                    except CsMoneyRequestError as error:
                        # Failed navigations still count towards the global request pace.
                        last_request = time.monotonic()
                        if isinstance(error, CsMoneyBrowserError):
                            raise
                        restart_reason = "blocked"
                        break
                    if processed:
                        last_request = time.monotonic()
                        session_jobs += 1
                        restart_failures = 0
                    if once:
                        return
                    if not processed:
                        time.sleep(5)
        except CsMoneyBrowserError:
            restart_reason = "browser_unavailable"
        if restart_reason == "blocked":
            blocked_until = time.monotonic() + storefront_retry
            LOG.warning("CS.MONEY storefront blocked; using Wiki Market summaries for %ds",
                        storefront_retry)
            if once:
                return
        elif restart_reason in {"browser_unavailable", "memory"}:
            restart_failures += 1
            LOG.warning("CS.MONEY browser restart reason=%s consecutive_failures=%d",
                        restart_reason, restart_failures)
            if restart_failures >= max_restarts:
                # Exit so Docker can also reclaim leaked/orphaned browser processes.
                raise RuntimeError("CS.MONEY browser recovery exhausted; worker restart required")
            time.sleep(_browser_retry_delay())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(once=args.once)


if __name__ == "__main__":
    main()
