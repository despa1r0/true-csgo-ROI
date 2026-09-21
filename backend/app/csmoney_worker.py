"""Background CS.MONEY collector. Run with ``python -m backend.app.csmoney_worker``."""

from __future__ import annotations

import argparse
import logging
import os
import time

from .csmoney_data import (
    cache_ttl_seconds,
    claim_refresh_job,
    complete_refresh_job,
    defer_refresh_job,
    enqueue_variants,
    load_variant_context,
    record_refresh_error,
    store_variant_capture,
    store_wiki_market_summary,
)
from .csmoney_demand import get_observed_sales_priorities
from .csmoney_wiki import WikiPriceError, fetch_market_summary
from .database import ensure_schema, get_connection
from .marketplaces.csmoney import CsMoneyRequestError, capture_variant, storefront_url


LOG = logging.getLogger(__name__)


def _positive_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


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
    LOG.debug("CS.MONEY %s: Wiki Market minimum $%.2f, count=%d, partial=true",
              variant_id, summary["price_cents"] / 100, summary["quantity"])


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
            record_refresh_error(variant_id, f"Wiki Market summary unavailable: {error}")
            defer_refresh_job(variant_id, seconds=21600)
            LOG.debug("CS.MONEY %s: Wiki Market summary unavailable: %s", variant_id, error)
        return True
    try:
        capture = capture_variant(
            page,
            context["market_hash_name"],
            phase=context.get("phase"),
        )
        stored = store_variant_capture(variant_id, capture)
    except CsMoneyRequestError as error:
        message = str(error)
        if "403" in message:
            # Stop storefront requests globally while using the separate
            # public Wiki Market summary. One 403 is enough to trip the gate.
            try:
                _wiki_summary(variant_id, context)
            except (WikiPriceError, OSError, TimeoutError, ValueError) as wiki_error:
                record_refresh_error(variant_id, f"Storefront 403; Wiki unavailable: {wiki_error}")
                defer_refresh_job(variant_id, seconds=21600)
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
    """Reuse one browser across jobs and keep requests at a bounded pace."""
    from camoufox.sync_api import Camoufox

    with get_connection() as connection:
        ensure_schema(connection)
    request_interval = _positive_env("CSMONEY_MIN_REQUEST_INTERVAL_SECONDS", 10)
    schedule_interval = _positive_env("CSMONEY_SCHEDULE_INTERVAL_SECONDS", 300)
    storefront_retry = _positive_env("CSMONEY_STOREFRONT_RETRY_SECONDS", 21600)
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
            processed = process_one(None)
            if processed:
                last_request = time.monotonic()
            if once:
                return
            if not processed:
                time.sleep(5)
            continue
        challenged = False
        with Camoufox(headless=True) as browser:
            page = browser.new_page()
            while True:
                now = time.monotonic()
                if now >= next_schedule:
                    scheduled = schedule_candidates()
                    LOG.info("CS.MONEY scheduled %d candidate jobs", scheduled)
                    next_schedule = now + schedule_interval
                remaining = request_interval - (time.monotonic() - last_request)
                if last_request and remaining > 0:
                    time.sleep(remaining)
                try:
                    processed = process_one(page)
                except CsMoneyRequestError:
                    challenged = True
                    break
                if processed:
                    last_request = time.monotonic()
                if once:
                    return
                if not processed:
                    time.sleep(5)
        if once:
            return
        if challenged:
            blocked_until = time.monotonic() + storefront_retry
            LOG.warning("CS.MONEY storefront returned 403; using Wiki Market summaries for %ds",
                        storefront_retry)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(once=args.once)


if __name__ == "__main__":
    main()
