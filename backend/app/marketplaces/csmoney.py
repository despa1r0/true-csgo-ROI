import json
import os
import random
from camoufox.sync_api import Camoufox

from ..csmoney_data import store_snapshot


# A minPrice/maxPrice range -- even one this wide, effectively "everything"
# -- makes cs.money paginate past its ~300-item (5-page) depth limit on the
# plain/unfiltered and type-filtered storefront views. Verified empirically:
# without these params offset>=300 gets a 403 (code 4030) on a *fresh*
# session too, so it's not a request-count throttle; with them, offset up to
# 50,000 kept returning real pages. Trade-off documented, not guaranteed to
# stay true forever -- if cs.money changes this, pages_to_fetch just yields
# fewer real pages sooner (handled below via the short-page break).
PRICE_RANGE_MIN = 0.01
PRICE_RANGE_MAX = 999999


def collect_sell_orders(pages_to_fetch: int = 5, *, headless: bool = False) -> list[dict]:
    collected_data: list[dict] = []

    print("Start scraping...")

    with Camoufox(headless=headless) as browser:
        page = browser.new_page()

        print("CS.MONEY...")
        page.goto(
            "https://cs.money/ru/csgo/store/",
            wait_until="domcontentloaded",
            timeout=120000
        )

        print("⏳ Wait...")
        page.wait_for_timeout(10000)

        print("(Fetch API)...")
        limit = 60

        for i in range(pages_to_fetch):
            offset = i * limit
            print(f"   Request {i + 1}/{pages_to_fetch} (offset={offset})...")

            result = page.evaluate("""
                                   async ([limit_val, offset_val, minPrice, maxPrice]) => {
                                       const url = '/2.0/market/sell-orders?' + new URLSearchParams({
                                           limit: limit_val.toString(),
                                           offset: offset_val.toString(),
                                           minPrice: minPrice.toString(),
                                           maxPrice: maxPrice.toString()
                                       });

                                       const response = await fetch(url, {
                                           headers: {
                                               'X-Client-App': 'web'
                                           }
                                       });

                                       return {
                                           status: response.status,
                                           body: await response.text()
                                       };
                                   }
                                   """, [limit, offset, PRICE_RANGE_MIN, PRICE_RANGE_MAX])

            if result["status"] == 200:
                try:
                    data = json.loads(result["body"])
                    collected_data.append(data)
                    items_count = len(data.get("items", []))
                    print(f"Got lots: {items_count}")
                    if items_count < limit:
                        print("Reached the end of the live listing set, stopping early.")
                        break
                except json.JSONDecodeError as e:
                    print(f"error parsing JSON (offset={offset}): {e}")
            else:
                print(f"error API. Status: {result['status']}")

            sleep_time = random.uniform(0.5, 1.5)
            print(f"   [Sleep: {sleep_time:.2f}s]")
            page.wait_for_timeout(int(sleep_time * 1000))

        print("Success.")

    return collected_data


def main():
    headless = os.getenv("CSMONEY_HEADLESS", "false").strip().lower() in {"1", "true", "yes"}
    # ~1s/page observed with the price-range trick -> ~400 pages fits a
    # 10-minute run and covers most of the live listing set.
    pages = int(os.getenv("CSMONEY_PAGES_PER_RUN", "400"))
    collected_data = collect_sell_orders(pages, headless=headless)

    if not collected_data:
        print("Error: Data wasn't collected.")
        return

    stored = store_snapshot(collected_data)
    print(f"Saved in PostgreSQL: {stored} variants")


if __name__ == "__main__":
    main()