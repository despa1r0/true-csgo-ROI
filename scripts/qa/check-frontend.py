"""Offline browser check of browse history and calculator layout against a running Vite.

Run from the repository: python scripts/qa/check-frontend.py --output <directory>
Requires Playwright and an installed Edge browser. All API/image responses are fixtures.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from playwright.sync_api import sync_playwright
from backend.app.main import marketplace_options
from backend.app.marketplaces_fees import FeeRule
from backend.app.profit import calculate_profit


def check(url: str, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    name = "Desert Eagle | Code Red"
    variant_name = f"{name} (Field-Tested)"
    skin = dict(id="skin-qa", name=name, item_type="skin", image_url=f"{url}/qa-skin.svg",
        weapon_id="deagle", weapon_name="Desert Eagle", rarity_id="covert", rarity_name="Covert",
        rarity_color="#eb4b4b", min_float=0, max_float=1, has_stattrak=False, has_souvenir=False, variant_count=1)
    variant = dict(id="variant-qa", name=variant_name, market_hash_name=variant_name, wear_id="ft",
        wear_name="Field-Tested", stattrak=False, souvenir=False, image_url=skin["image_url"])
    prices = dict(csfloat=4088, csgomarket=5200, csmoney=3900, whitemarket=4700)
    quotes = {market: dict(marketplace=market, price_cents=price, item_url="https://example.test/",
        listing_id=f"{market}-1", float_value=.22, quantity=1, fetched_at=now, stale=False,
        source="storefront" if market == "csmoney" else "listing") for market, price in prices.items()}
    compared = dict(skin_id=skin["id"], marketplaces=[], variants=[dict(variant_id=variant["id"],
        market_hash_name=variant_name, markets=quotes, errors={}, cheapest_marketplace="csmoney",
        cheapest_price_cents=3900, gross_spread_cents=1300, opportunities=[dict(
            variant_id=variant["id"], buy_marketplace="csmoney", sell_marketplace="csfloat",
            buy_price_cents=3900, sell_price_cents=4088,
            profit_cents=188, cash_roi_percent=4.82, risk_level="unknown", sell_liquidity=None)])])

    def listing(market: str) -> dict:
        return dict(listing_id=f"{market}-1", variant_id=variant["id"], market_hash_name=variant_name,
            marketplace_id=market, image_url=skin["image_url"], price_cents=prices[market], float_value=.22,
            paint_seed=123, item_url="https://example.test/", stale=False, stickers=[], charms=[])

    def api_response(route) -> None:
        request = route.request
        parsed = urlparse(request.url)
        path = parsed.path
        if path == "/api/health": data = {"catalogue": {"skins": 100}}
        elif path == "/api/marketplaces": data = marketplace_options()
        elif path == "/api/catalog/filters": data = dict(item_types=[], weapons=[], rarities=[], collections=[])
        elif path == "/api/items/search": data = [skin] + [dict(skin, id=f"skin-other-{index}", name=f"{skin['name']} {index}") for index in range(1, 8)]
        elif path == f"/api/skins/{skin['id']}": data = dict(**skin, collections=[], qualities=[dict(wear="Field-Tested", variants=[variant])])
        elif path.endswith("/markets/compare"): data = compared
        elif path == f"/api/skins/{skin['id']}/market/csmoney": data = dict(marketplace="CS.MONEY",
            cache_ttl_seconds=1800, refresh_queued=False, variants=[dict(variant_id=variant["id"], market_hash_name=variant_name, listing=quotes["csmoney"])])
        elif path.endswith("/listings"):
            market = path.split("/")[-2]
            data = dict(marketplace=market, listings=[dict(listing(market), listing_id=f"{market}-{index}") for index in range(1, 33)], cached=True, stale=False,
                fetched_at=now, source_state="listings_available", quote_source="storefront")
        elif path.endswith("/price-history"): data = dict(source="csmoney_wiki_trade_quote", points=[], latest_at=None)
        elif "/api/variants/" in path:
            market = path.split("/")[-1]
            data = dict(marketplace=market, variant_id=variant["id"], market_hash_name=variant_name,
                overview=dict(price_cents=prices[market], active_listings=1), listings=[listing(market)], sales=[],
                stats=dict(liquidity_score=None, liquidity_data_status="missing_sales"), quick_sell=dict(orders=[]),
                components={key: dict(status="fresh", fetched_at=now) for key in ["listings", "sales", "buy_orders"]},
                cached=True, stale=False, fetched_at=now, quote_source="storefront")
        elif path == "/api/calculate":
            body = request.post_data_json
            data = calculate_profit(buy_price_cents=body["buy_price_cents"], sell_price_cents=body["sell_price_cents"],
                deposit_rule=FeeRule(), sell_rule=FeeRule(), withdraw_rule=FeeRule()).model_dump()
            data["break_even_sell_price_cents"] = body["buy_price_cents"]
        else: data = dict(orders=[], best_price_cents=None)
        route.fulfill(status=200, content_type="application/json", body=json.dumps(data))

    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport=dict(width=1440, height=1000))
        context.add_init_script("localStorage.setItem('trueroi-theme','dark'); if (!localStorage.getItem('trueroi-language')) localStorage.setItem('trueroi-language','en');")
        context.route(f"{url}/api/**", api_response)
        context.route("**/qa-skin.svg", lambda route: route.fulfill(content_type="image/svg+xml", body=
            '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="220" viewBox="0 0 320 220"><path fill="#df423c" d="M50 55h215v50H165v90h-45l-15-90H50z"/><path fill="#303b3c" d="M125 107h39v75h-35z"/><path stroke="#f2cfc9" stroke-width="5" d="M64 72h184"/></svg>'))
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(f"{url}/?q=Code")
        try:
            page.locator("#skin-search-suggestions button").first.wait_for(timeout=10000)
        except Exception:
            page.screenshot(path=str(output / "initial-failure.png"), full_page=True)
            print("Initial page:", page.locator("body").inner_text(), "Errors:", errors, flush=True)
            raise
        page.locator("#skin-search-suggestions button").first.click()
        quality_card = page.locator("button[class*='qualityCard']").first
        quality_card.locator("[role='status']").wait_for()
        assert quality_card.locator("[role='status']").inner_text() == "Liquidity not rated"
        assert quality_card.locator("[role='status']").evaluate("e => getComputedStyle(e).backgroundColor") == "rgba(0, 0, 0, 0)"
        assert quality_card.locator("[class*='sourceNote']").count() == 0
        page.screenshot(path=str(output / "catalogue-compact-card.png"), full_page=True)
        quality_card.scroll_into_view_if_needed()
        catalogue_scroll = page.evaluate("window.scrollY")
        quality_card.click()
        page.locator("select[name='listing-marketplace']").select_option("csmoney")
        assert page.locator("div[class*='snapshotStatus']").filter(has_text="Updated").count() == 0
        page.locator("input[name='minimum-price']").fill("10")
        page.get_by_role("button", name="Apply", exact=True).click()
        last_listing = page.locator("button[class*='listingCard']").last
        last_listing.scroll_into_view_if_needed()
        list_scroll = page.locator("div[class*='browserView']").evaluate("element => element.scrollTop")
        assert list_scroll > 0
        last_listing.click()
        page.get_by_role("tab", name="Compare", exact=True).click()
        detail_url = page.url
        page.get_by_role("link", name="Profit calculator").last.click()
        page.wait_for_url("**/calculator?**")
        page.go_back()
        page.wait_for_url(detail_url)
        assert page.get_by_role("tab", name="Compare", exact=True).get_attribute("aria-selected") == "true"
        page.get_by_role("button", name="Back to listings", exact=False).click()
        page.locator("select[name='listing-marketplace']").wait_for()
        assert page.locator("select[name='listing-marketplace']").input_value() == "csmoney"
        assert page.locator("input[name='minimum-price']").input_value() == "10"
        assert abs(page.locator("div[class*='browserView']").evaluate("element => element.scrollTop") - list_scroll) < 2
        page.go_back()
        page.locator("button[class*='qualityCard']").first.wait_for()
        assert not parse_qs(urlparse(page.url).query).get("wear")
        assert abs(page.evaluate("window.scrollY") - catalogue_scroll) < 2
        page.go_forward()
        page.locator("select[name='listing-marketplace']").wait_for()
        page.reload()
        assert page.locator("select[name='listing-marketplace']").input_value() == "csmoney"
        print("Browse: calculator return, Back, Forward, filters, scroll restoration and reload passed", flush=True)

        # Reproduce the reported overlap with no skin selected and with an active reference.
        for width, selected in [(1440, False), (1440, True), (390, False), (320, True)]:
            page.set_viewport_size(dict(width=width, height=1000))
            suffix = f"?skin={skin['id']}&variant={variant['id']}" if selected else ""
            page.goto(f"{url}/calculator{suffix}")
            if selected: page.locator("select[name='skin-variant']").wait_for()
            search = page.locator("#calculator-skin-search")
            search.fill("code")
            results = page.locator("#calculator-suggestions button")
            results.first.wait_for()
            search.scroll_into_view_if_needed()
            # Hit-test a visible result where the list overlaps the form underneath.
            results.nth(1).scroll_into_view_if_needed()
            assert results.nth(1).evaluate("""button => {
                const r = button.getBoundingClientRect();
                const hit = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
                return button.contains(hit);
            }"""), f"Suggestions obscured: {width}px selected={selected}"
            assert page.locator("html").evaluate("e => e.scrollWidth") <= width
            page.screenshot(path=str(output / f"calculator-suggestions-{width}-{'selected' if selected else 'empty'}.png"), full_page=True)
            search.press("ArrowDown")
            assert results.first.evaluate("button => button === document.activeElement")
            results.first.press("Escape")
            assert page.locator("#calculator-suggestions").count() == 0
            assert search.evaluate("input => input === document.activeElement")
            search.fill("code r")
            results.first.wait_for()
            results.first.click()
            page.locator("select[name='skin-variant']").wait_for()
            assert page.locator("#calculator-suggestions").count() == 0
            search.fill("code")
            results.first.wait_for()
            page.locator("h1").click()
            assert page.locator("#calculator-suggestions").count() == 0
            print(f"Suggestions: {width}px selected={selected}, overlay, keyboard, selection and dismissal passed", flush=True)

        for language, width in [("en", 1440), ("ru", 1024), ("ru", 390), ("ru", 320)]:
            if width == 320:
                skin["name"] = "Souvenir Desert Eagle | Extremely Long Collection Reference Name"
                variant["market_hash_name"] = skin["name"] + " (Field-Tested)"
            page.set_viewport_size(dict(width=width, height=1000))
            page.goto(f"{url}/calculator?skin={skin['id']}&variant={variant['id']}&buy=4000&market=csfloat")
            page.evaluate("language => localStorage.setItem('trueroi-language',language)", language)
            page.reload()
            page.locator("select[name='skin-variant']").wait_for()
            page.locator("p[class*='savings']").wait_for()
            page.locator("button[type='submit']").click()
            page.locator("div[class*='heroResult']").wait_for()
            assert page.locator("html").get_attribute("lang") == language
            metrics = page.evaluate("""() => {
                const box = selector => document.querySelector(selector).getBoundingClientRect().toJSON();
                return { viewport: innerWidth, width: document.documentElement.scrollWidth,
                    savings: box('p[class*=savings]'), image: box('div[class*=referencePreview] img'),
                    preview: box('div[class*=referencePreview]'),
                    buy: box('input[name=buy-price]'), sell: box('input[name=sell-price]') };
            }""")
            assert metrics["width"] <= width, metrics
            assert abs((metrics["image"]["x"] + metrics["image"]["width"] / 2) -
                       (metrics["preview"]["x"] + metrics["preview"]["width"] / 2)) < 1, metrics
            if width > 704: assert abs(metrics["buy"]["y"] - metrics["sell"]["y"]) < 1, metrics
            assert metrics["savings"]["height"] < 110, metrics
            page.evaluate("window.scrollTo(0, 0)")
            page.screenshot(path=str(output / f"calculator-{language}-{width}.png"), full_page=True)
            print(f"Calculator: {language} {width}px centered, aligned, no overflow", flush=True)
        assert not errors, errors
        context.close()
        browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:5173")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    check(args.url.rstrip("/"), args.output)
