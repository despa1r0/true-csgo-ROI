"""Gradually measure seven-day sales demand for CS.MONEY scheduling."""

from __future__ import annotations

import logging
import os
import time

from .csmoney_demand import refresh_missing_demand_signals
from .database import ensure_schema, get_connection


LOG = logging.getLogger(__name__)


def run() -> None:
    with get_connection() as connection:
        ensure_schema(connection)
    while True:
        started = time.monotonic()
        try:
            result = refresh_missing_demand_signals(batch_size=20, max_requests=5)
        except Exception:
            LOG.exception("CS.MONEY demand probe failed")
        else:
            LOG.info("CS.MONEY demand probe: %s", result)
        try:
            interval = max(60, int(os.getenv("CSMONEY_SCHEDULE_INTERVAL_SECONDS", "300")))
        except ValueError:
            interval = 300
        time.sleep(max(1, interval - (time.monotonic() - started)))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
