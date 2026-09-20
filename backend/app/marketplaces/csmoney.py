import json
import random
from camoufox.sync_api import Camoufox

from ..csmoney_data import store_snapshot


def collect_sell_orders(pages_to_fetch: int = 5) -> list[dict]:
    collected_data: list[dict] = []

    print("Start scraping...")

    with Camoufox(headless=False) as browser:
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
                                   async ([limit_val, offset_val]) => {
                                       const url = '/2.0/market/sell-orders?' + new URLSearchParams({
                                           limit: limit_val.toString(),
                                           offset: offset_val.toString()
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
                                   """, [limit, offset])

            if result["status"] == 200:
                try:
                    data = json.loads(result["body"])
                    collected_data.append(data)
                    items_count = len(data.get("items", []))
                    print(f"Got lots: {items_count}")
                except json.JSONDecodeError as e:
                    print(f"error parsing JSON (offset={offset}): {e}")
            else:
                print(f"error API. Status: {result['status']}")

            sleep_time = random.uniform(3.5, 7.0)
            print(f"   [Sleep: {sleep_time:.2f}s]")
            page.wait_for_timeout(int(sleep_time * 1000))

        print("Success.")

    return collected_data


def main():
    collected_data = collect_sell_orders(18)

    if not collected_data:
        print("Error: Data wasn't collected.")
        return

    stored = store_snapshot(collected_data)
    print(f"Saved in PostgreSQL: {stored} variants")


if __name__ == "__main__":
    main()