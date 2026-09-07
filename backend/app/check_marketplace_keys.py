"""Perform one small, read-only authenticated request per marketplace."""

from __future__ import annotations

from collections.abc import Callable

from dotenv import load_dotenv

from .csgomarket import get_active_listings as get_csgomarket_listings
from .marketplaces.csfloat import get_active_listings as get_csfloat_listings
from .marketplaces.whitemarket import get_active_listings as get_whitemarket_listings


TEST_ITEM = "AK-47 | Redline (Field-Tested)"


def main() -> int:
    load_dotenv()
    checks: list[tuple[str, Callable[[], object]]] = [
        ("CSFloat", lambda: get_csfloat_listings(TEST_ITEM, limit=1)),
        ("CSGO Market", lambda: get_csgomarket_listings(TEST_ITEM, limit=1)),
        ("White.Market", lambda: get_whitemarket_listings(TEST_ITEM, limit=1)),
    ]
    failed = False
    for name, check in checks:
        try:
            result = check()
        except Exception as error:  # Diagnostic command: report each provider.
            failed = True
            # Keep output ASCII-safe on Windows consoles and never echo a token.
            print(f"{name}: ERROR ({type(error).__name__})", flush=True)
        else:
            count = len(result) if isinstance(result, list) else 1
            print(f"{name}: OK ({count} listing responses)", flush=True)
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
