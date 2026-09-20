"""Inspect one CS.MONEY variant through the production storefront adapter.

This diagnostic does not write to the database. A full first page with fewer
than ten exact matches does not establish that later pages contain no more.
"""

from __future__ import annotations

import argparse
import json

from camoufox.sync_api import Camoufox

from backend.app.marketplaces.csmoney import capture_variant


def inspect(
    market_hash_name: str, *, phase: str | None = None,
    limit: int = 10, headed: bool = False,
) -> dict:
    with Camoufox(headless=not headed) as browser:
        page = browser.new_page()
        return capture_variant(page, market_hash_name, phase=phase, limit=limit)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("market_hash_name")
    parser.add_argument("--phase")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")
    print(json.dumps(
        inspect(args.market_hash_name, phase=args.phase, limit=args.limit, headed=args.headed),
        ensure_ascii=False, indent=2,
    ))


if __name__ == "__main__":
    main()
