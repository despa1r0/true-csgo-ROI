"""Background loop that periodically refreshes CS.Money's price snapshot.

Runs ``marketplaces/csmoney.py`` on an interval instead of on demand, since
CS.Money has no API to call synchronously from a request. Any single run
failing (site blocks the request, browser crashes, DB hiccup) must not kill
the loop -- there is always a next attempt.
"""

from __future__ import annotations

import os
import random
import time
import traceback
from datetime import datetime, timezone

from .csmoney_data import store_snapshot
from .marketplaces.csmoney import collect_sell_orders

DEFAULT_INTERVAL_SECONDS = 600
DEFAULT_PAGES_PER_RUN = 400


def run_once() -> None:
    pages = _positive_int_env("CSMONEY_PAGES_PER_RUN", DEFAULT_PAGES_PER_RUN)
    headless = os.getenv("CSMONEY_HEADLESS", "true").strip().lower() in {"1", "true", "yes"}
    collected = collect_sell_orders(pages, headless=headless)
    if not collected:
        print("[csmoney-worker] No data collected this run, skipping store.")
        return
    stored = store_snapshot(collected)
    print(f"[csmoney-worker] Stored {stored} variants from {len(collected)} responses.")


def main() -> None:
    interval = _positive_int_env("CSMONEY_WORKER_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS)
    print(f"[csmoney-worker] Starting. Interval: {interval}s")
    while True:
        started_at = datetime.now(timezone.utc).isoformat()
        try:
            print(f"[csmoney-worker] Run started at {started_at}")
            run_once()
        except Exception:  # A blocked/broken run must not take the loop down.
            print(f"[csmoney-worker] Run failed at {started_at}:")
            traceback.print_exc()

        # Jitter avoids ever settling into a perfectly regular, easy-to-fingerprint
        # request cadence against cs.money.
        sleep_seconds = interval + random.uniform(-0.1, 0.1) * interval
        print(f"[csmoney-worker] Sleeping {sleep_seconds:.0f}s until next run.")
        time.sleep(max(sleep_seconds, 60))


def _positive_int_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


if __name__ == "__main__":
    main()
