"""Offline geometry check: centring and alignment of data in the interface.

Run from the repository, against a running Vite dev server:
    python scripts/qa/check-alignment.py --output <directory>
Requires Playwright and an installed Edge browser. All API responses are fixtures.

Every rule compares measured boxes, so a pass means the pixels line up, not that
a stylesheet declares it. Tolerance is one CSS pixel.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from playwright.sync_api import sync_playwright
from backend.app.main import marketplace_options
from backend.app.marketplaces_fees import FeeRule
from backend.app.profit import calculate_profit

TOLERANCE = 1.0
WEARS = [("Factory New", "fn"), ("Minimal Wear", "mw"), ("Field-Tested", "ft"),
         ("Well-Worn", "ww"), ("Battle-Scarred", "bs")]
SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="320" height="220" viewBox="0 0 320 220">'
       '<path fill="#df423c" d="M50 55h215v50H165v90h-45l-15-90H50z"/></svg>')


def fixtures(url: str):
    now = datetime.now(timezone.utc)
    stamp = now.isoformat()
    markets = marketplace_options()
    ids = [market["id"] for market in markets]
    name = "Desert Eagle | Code Red With A Deliberately Long Name"
    skin = dict(id="skin-qa", name=name, item_type="skin", image_url=f"{url}/qa-skin.svg",
        weapon_id="deagle", weapon_name="Desert Eagle", rarity_id="covert", rarity_name="Covert",
        rarity_color="#eb4b4b", min_float=0, max_float=1, has_stattrak=True, has_souvenir=False, variant_count=10)
    qualities, compared = [], []
    for index, (wear, code) in enumerate(WEARS):
        variants = []
        for stattrak in (False, True):
            title = f"{'StatTrak™ ' if stattrak else ''}{name} ({wear})"
            variant_id = f"variant-{code}{'-st' if stattrak else ''}"
            variants.append(dict(id=variant_id, name=title, market_hash_name=title, wear_id=code, wear_name=wear,
                stattrak=stattrak, souvenir=False, image_url=skin["image_url"]))
            base = 4000 + index * 1234 + (9000 if stattrak else 0)
            # Deliberately uneven data: missing quotes and prices of different lengths.
            quotes = {market: None if (index + position) % 4 == 3 else dict(
                marketplace=market, price_cents=base + position * 137, item_url="https://example.test/",
                listing_id=f"{market}-{variant_id}", float_value=.22, quantity=3, fetched_at=stamp, stale=False,
                source="listing") for position, market in enumerate(ids)}
            opportunities = [] if index == 1 else [dict(variant_id=variant_id, buy_marketplace=ids[0],
                sell_marketplace=ids[1], buy_price_cents=base, sell_price_cents=base + 500,
                profit_cents=188 if index % 2 else -42, cash_roi_percent=4.82, sell_mode="listing",
                risk_level="unknown" if index % 2 else None, sell_liquidity=None)]
            available = [quote for quote in quotes.values() if quote]
            compared.append(dict(variant_id=variant_id, market_hash_name=title, markets=quotes, errors={},
                cheapest_marketplace=min(available, key=lambda quote: quote["price_cents"])["marketplace"],
                cheapest_price_cents=min(quote["price_cents"] for quote in available),
                gross_spread_cents=500, opportunities=opportunities))
        qualities.append(dict(wear=wear, variants=variants))
    selected = qualities[2]["variants"][0]

    def listing(market: str, index: int) -> dict:
        stickers = [dict(name=f"Sticker {n}", icon_url=skin["image_url"]) for n in range(index % 5)]
        return dict(listing_id=f"{market}-{index}", variant_id=selected["id"], market_hash_name=selected["market_hash_name"],
            marketplace_id=market, image_url=skin["image_url"], price_cents=4000 + index * 997,
            float_value=.15 + index / 1000, paint_seed=100 + index, wear_name="Field-Tested",
            stattrak=False, souvenir=False, item_url="https://example.test/", stale=False,
            predicted_price_cents=4100 if index % 3 == 0 else None,
            stickers=stickers, charms=[dict(name="Charm", icon_url=skin["image_url"])] if index % 4 == 0 else [])

    def respond(route) -> None:
        path = urlparse(route.request.url).path
        if path == "/api/health": data = {"catalogue": {"skins": 26707}}
        elif path == "/api/marketplaces": data = markets
        elif path == "/api/catalog/filters":
            data = dict(item_types=[dict(id="skin", name="Skin", count=1)], weapons=[], rarities=[], collections=[])
        elif path == "/api/items/search": data = [dict(skin, id=f"skin-{n}" if n else skin["id"]) for n in range(6)]
        elif path == f"/api/skins/{skin['id']}": data = dict(**skin, collections=[], qualities=qualities)
        elif path.endswith("/markets/compare"): data = dict(skin_id=skin["id"], marketplaces=[], variants=compared)
        elif path == f"/api/skins/{skin['id']}/market/csmoney":
            data = dict(marketplace="CS.MONEY", cache_ttl_seconds=1800, refresh_queued=False, variants=[])
        elif path.endswith("/listings"):
            market = path.split("/")[-2]
            data = dict(marketplace=market, listings=[listing(market, n) for n in range(1, 12)], cached=True,
                stale=False, fetched_at=stamp)
        elif path.endswith("/price-history"): data = dict(source="csmoney_wiki_trade_quote", points=[], latest_at=None)
        elif "/api/variants/" in path:
            market = path.split("/")[-1]
            data = dict(marketplace=market, variant_id=selected["id"], market_hash_name=selected["market_hash_name"],
                overview=dict(price_cents=4088, active_listings=11), listings=[listing(market, n) for n in range(1, 6)],
                sales=[dict(sold_at=(now - timedelta(hours=n * 7)).isoformat(), price_cents=4000 + n * 31,
                            float_value=.2) for n in range(1, 20)],
                stats=dict(liquidity_score=71, sales_per_day=2.7, liquidity_data_status="ok"),
                quick_sell=dict(best_price_cents=3900, near_bid_depth=4, orders=[
                    dict(price_cents=3900 - n * 10, quantity=n + 1) for n in range(5)]),
                components={key: dict(status="fresh", fetched_at=stamp) for key in ["listings", "sales", "buy_orders"]},
                cached=True, stale=False, fetched_at=stamp)
        elif path == "/api/calculate":
            body = route.request.post_data_json
            data = calculate_profit(buy_price_cents=body["buy_price_cents"], sell_price_cents=body["sell_price_cents"],
                deposit_rule=FeeRule(percent=1), sell_rule=FeeRule(percent=2), withdraw_rule=FeeRule()).model_dump()
            data["break_even_sell_price_cents"] = body["buy_price_cents"]
            data["applied_fees"] = {key: dict(enabled=True, amount_cents=1, percent=1, fixed_cents=0)
                                    for key in ("deposit", "sell", "withdraw")}
        else: data = dict(orders=[], best_price_cents=None)
        route.fulfill(status=200, content_type="application/json", body=json.dumps(data))

    return respond, selected


BOXES = """(selector) => [...document.querySelectorAll(selector)].filter(e => e.getClientRects().length).map(e => {
  const r = e.getBoundingClientRect(), s = getComputedStyle(e);
  return {x: r.x, y: r.y, w: r.width, h: r.height, cx: r.x + r.width / 2, cy: r.y + r.height / 2,
    right: r.right, bottom: r.bottom, pl: parseFloat(s.paddingLeft), pr: parseFloat(s.paddingRight),
    bl: parseFloat(s.borderLeftWidth), br: parseFloat(s.borderRightWidth), align: s.textAlign};
})"""


class Report:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.passed = 0
        self.scope = ""

    def check(self, condition: bool, rule: str, detail: object = "") -> None:
        if condition: self.passed += 1
        else: self.failures.append(f"[{self.scope}] {rule} {detail}".strip())

    def same(self, values: list[float], rule: str) -> None:
        self.check(bool(values), f"{rule}: nothing measured")
        if values: self.check(max(values) - min(values) <= TOLERANCE, rule, [round(value, 1) for value in values])


INNER = """([card, child]) => [...document.querySelectorAll(card)].filter(e => e.getClientRects().length).map(e => {
  const inner = e.querySelector(child);
  return {row: Math.round(e.getBoundingClientRect().y), y: inner ? inner.getBoundingClientRect().y : null,
          bottom: inner ? inner.getBoundingClientRect().bottom : null};
})"""


def inner_lines(page, report: "Report", card: str, child: str, rule: str, edge: str = "y") -> None:
    """Within each visual row of cards, the same inner element must sit on one line."""
    grouped: dict[int, list[float]] = {}
    for item in page.evaluate(INNER, [card, child]):
        if item[edge] is not None: grouped.setdefault(item["row"], []).append(item[edge])
    report.check(bool(grouped), f"{rule}: nothing measured")
    for values in grouped.values(): report.same(values, rule)


def rows(boxes: list[dict]) -> list[list[dict]]:
    """Group boxes that share a grid row."""
    grouped: dict[int, list[dict]] = {}
    for box in boxes: grouped.setdefault(round(box["y"]), []).append(box)
    return [row for _, row in sorted(grouped.items())]


def check_page(page, report: Report, width: int) -> None:
    box = lambda selector: page.evaluate(BOXES, selector)
    report.check(page.evaluate("document.documentElement.scrollWidth") <= width, "no horizontal overflow")
    # Images sit in the middle of the box that frames them.
    def centred_images(container: str, rule: str) -> None:
        pairs = page.evaluate("""(selector) => [...document.querySelectorAll(selector)].map(e => {
          const image = e.querySelector(':scope > img'); if (!image) return null;
          const c = e.getBoundingClientRect(), i = image.getBoundingClientRect(), s = getComputedStyle(e);
          const inner = c.x + parseFloat(s.borderLeftWidth) + parseFloat(s.paddingLeft)
            + (c.width - parseFloat(s.borderLeftWidth) - parseFloat(s.borderRightWidth)
               - parseFloat(s.paddingLeft) - parseFloat(s.paddingRight)) / 2;
          return Math.abs(inner - (i.x + i.width / 2));
        }).filter(v => v !== null)""", container)
        report.check(bool(pairs), f"{rule}: nothing measured")
        report.check(all(offset <= TOLERANCE for offset in pairs), rule, [round(v, 1) for v in pairs if v > TOLERANCE])
    report.centred_images = centred_images  # type: ignore[attr-defined]
    report.box = box  # type: ignore[attr-defined]


def check_header(report: Report) -> None:
    box = report.box  # type: ignore[attr-defined]
    inner = box("header div[class*=headerInner]")[0]
    parts = box("a[class*=brand], nav[class*=navigation] a, div[class*=headerTools] > *")
    report.same([part["cy"] for part in parts], "header: brand, links and tools share one centre line")
    report.check(abs(inner["cy"] - parts[0]["cy"]) <= TOLERANCE, "header: content is vertically centred in the bar")


def check_catalogue(page, report: Report, width: int) -> None:
    box = report.box  # type: ignore[attr-defined]
    report.centred_images("button[class*=qualityCard]", "quality card: image is horizontally centred")  # type: ignore[attr-defined]
    cards = box("button[class*=qualityCard]")
    for row in rows(cards):
        report.same([card["h"] for card in row], "quality cards: equal height within a row")
    for selector, rule in [("div[class*=qualityPrice]", "price rows"), ("div[class*=marketMini]", "market tables"),
                           ("div[class*=positive], div[class*=negative]", "profit lines")]:
        inner_lines(page, report, "button[class*=qualityCard]", selector, f"quality cards: {rule} start on the same line")
    values = page.evaluate("""() => [...document.querySelectorAll('button[class*=qualityCard]')].map(card => {
      const cr = card.getBoundingClientRect(), s = getComputedStyle(card);
      const edge = cr.right - parseFloat(s.paddingRight) - parseFloat(s.borderRightWidth);
      return [...card.querySelectorAll('div[class*=marketMini] b, div[class*=qualityPrice] > span')]
        .map(e => Math.abs(edge - e.getBoundingClientRect().right));
    }).flat()""")
    report.check(all(v <= TOLERANCE for v in values), "quality card: prices are flush with the right edge",
                 [round(v, 1) for v in values if v > TOLERANCE])
    controls = box("section[class*=profitBar] select, section[class*=profitBar] button[class*=swapButton]")
    for row in rows([dict(control, y=control["bottom"]) for control in controls]):
        report.same([control["h"] for control in row], "ROI settings: controls in a row have one height")
    if width >= 1200:
        report.same([control["bottom"] for control in controls], "ROI settings: controls share a baseline")
        filters = box("div[class*=catalogFilters] select, div[class*=searchBox] > input")
        report.same([control["bottom"] for control in filters], "search and filters share a baseline")
        report.same([control["h"] for control in filters], "search and filters have one height")
    icon, field = box("svg[class*=searchIcon]")[0], box("div[class*=searchBox] > input")[0]
    report.check(abs(icon["cy"] - field["cy"]) <= TOLERANCE, "search icon is vertically centred in the field")


def check_listings(page, report: Report, width: int) -> None:
    box = report.box  # type: ignore[attr-defined]
    dialog = box("div[role=dialog]")[0]
    report.check(abs(dialog["cx"] - width / 2) <= TOLERANCE, "dialog is horizontally centred in the viewport")
    report.centred_images("button[class*=listingCard]", "listing card: image is horizontally centred")  # type: ignore[attr-defined]
    for row in rows(box("button[class*=listingCard]")):
        report.same([card["h"] for card in row], "listing cards: equal height within a row")
    for selector, rule in [("div[class*=listingBottom]", "price blocks"), ("div[class*=listingBottom] strong", "prices"),
                           (":scope > img", "images"), ("div[class*=attachments], span[class*=noAttachments]", "attachment rows")]:
        inner_lines(page, report, "button[class*=listingCard]", selector, f"listing cards: {rule} start on the same line")
    toolbar = box("section[class*=listingToolbar] select, section[class*=listingToolbar] input:not([type=checkbox]),"
                  " section[class*=listingToolbar] > button")
    for row in rows([dict(control, y=control["bottom"]) for control in toolbar]):
        report.same([control["h"] for control in row], "listing filters: controls in a row have one height")
    checks = page.evaluate("""() => [...document.querySelectorAll('label[class*=inlineCheck]')].map(label => {
      const input = label.querySelector('input').getBoundingClientRect(), l = label.getBoundingClientRect();
      return Math.abs((input.y + input.height / 2) - (l.y + l.height / 2));
    })""")
    report.check(all(v <= TOLERANCE for v in checks), "listing filters: checkbox is centred on its label", checks)
    close, header = box("button[class*=dialogClose]")[0], box("header[class*=dialogHeader]")[0]
    report.check(close["right"] <= header["right"] + TOLERANCE, "dialog: close button stays inside the header")


def check_detail(page, report: Report, width: int) -> None:
    box = report.box  # type: ignore[attr-defined]
    report.centred_images("div[class*=detailImage]", "detail: item image is centred in its frame")  # type: ignore[attr-defined]
    tabs = box("nav[class*=analyticsTabs] button")
    report.same([tab["w"] for tab in tabs], "analytics tabs: equal width")
    report.same([tab["cy"] for tab in tabs], "analytics tabs: one centre line")
    report.check(all(tab["align"] == "center" for tab in tabs), "analytics tabs: labels are centred")
    active = box("nav[class*=analyticsTabs] button[aria-selected=true]")[0]
    indicator = box("span[class*=tabIndicator]")[0]
    report.check(abs(active["cx"] - indicator["cx"]) <= TOLERANCE, "analytics tabs: indicator is centred under the active tab")
    for row in rows(box("div[class*=metricGrid] > div, div[class*=feeBreakdown] > div")):
        report.same([tile["h"] for tile in row], "metric tiles: equal height within a row")
    chips = box("div[class*=marketTabs] button")
    for row in rows(chips):
        report.same([chip["h"] for chip in row], "marketplace chips: equal height")
    report.check(all(chip["align"] == "center" for chip in chips), "marketplace chips: labels are centred")


def check_compare(page, report: Report, width: int) -> None:
    box = report.box  # type: ignore[attr-defined]
    previews = box("article[class*=comparePreview]")
    for row in rows(previews):
        report.same([preview["h"] for preview in row], "compare: previews have equal height")
    if width >= 700:
        controls = box("div[class*=compareControls] select, div[class*=compareControls] button")
        report.same([control["bottom"] for control in controls], "compare: selects and swap share a baseline")
        report.same([control["h"] for control in controls], "compare: selects and swap have one height")
        selects = box("div[class*=compareControls] select")
        swap = box("div[class*=compareControls] button")[0]
        report.check(abs(swap["cx"] - (selects[0]["right"] + selects[1]["x"]) / 2) <= TOLERANCE,
                     "compare: swap button is centred between the two selects")
    for selector, rule in [(":scope > div:first-child", "titles"), (":scope > strong", "prices"), (":scope > img", "images")]:
        inner_lines(page, report, "article[class*=comparePreview]", selector, f"compare: preview {rule} start on the same line")
    if width >= 700:
        upper, lower = box("div[class*=compareControls] select"), box("div[class*=compareOptions] select")
        report.same([upper[0]["x"], lower[0]["x"]], "compare: left selects share a left edge")
        report.same([upper[1]["x"], lower[1]["x"]], "compare: right selects share a left edge")
        report.same([upper[1]["right"], lower[1]["right"]], "compare: right selects share a right edge")
    for row in rows(box("div[class*=metricGrid] > div, div[class*=feeBreakdown] > div")):
        report.same([tile["h"] for tile in row], "compare: metric tiles have equal height within a row")


def check_calculator(page, report: Report, width: int) -> None:
    box = report.box  # type: ignore[attr-defined]
    report.centred_images("div[class*=referencePreview]", "calculator: reference image is centred")  # type: ignore[attr-defined]
    buy, sell = box("input[name=buy-price]")[0], box("input[name=sell-price]")[0]
    markets = box("select[name=calculator-buy-marketplace], select[name=calculator-sell-marketplace]")
    arrow, swap = box("div[class*=direction]")[0], box("button[class*=swap]")[0]
    report.same([buy["h"], sell["h"]], "calculator: price fields have one height")
    if width > 704:
        report.same([buy["y"], sell["y"]], "calculator: price fields share a line")
        report.check(abs(arrow["cy"] - buy["cy"]) <= TOLERANCE, "calculator: arrow is centred on the price fields")
        report.check(abs(arrow["cx"] - (buy["right"] + sell["x"]) / 2) <= TOLERANCE, "calculator: arrow is centred between the price fields")
        report.same([market["y"] for market in markets], "calculator: marketplace selects share a line")
        report.check(abs(swap["cy"] - markets[0]["cy"]) <= TOLERANCE, "calculator: swap is centred on the selects")
        report.check(abs(swap["cx"] - (markets[0]["right"] + markets[1]["x"]) / 2) <= TOLERANCE, "calculator: swap is centred between the selects")
    else:
        column = box("section[class*=formPanel]")[0]
        middle = column["x"] + column["w"] / 2
        report.check(abs(arrow["cx"] - middle) <= TOLERANCE, "calculator: arrow is centred in the column")
        report.check(abs(swap["cx"] - middle) <= TOLERANCE, "calculator: swap is centred in the column")
    for row in rows(box("div[class*=optionsGrid] select")):
        report.same([select["h"] for select in row], "calculator: option selects have one height")
    fees = page.evaluate("""() => [...document.querySelectorAll('fieldset[class*=fees] label')].map(label => {
      const l = label.getBoundingClientRect(), input = label.querySelector('input').getBoundingClientRect();
      const text = label.querySelector('span').getBoundingClientRect();
      return Math.abs((input.y + input.height / 2) - (text.y + text.height / 2));
    })""")
    report.check(all(v <= TOLERANCE for v in fees), "calculator: fee checkbox is centred on its label", fees)
    rows_right = box("div[class*=resultRow] strong")
    report.same([value["right"] for value in rows_right], "result: amounts are flush with one right edge")
    submit, panel = box("button[type=submit]")[0], box("section[class*=formPanel]")[0]
    report.check(abs(submit["cx"] - (panel["x"] + panel["w"] / 2)) <= TOLERANCE, "calculator: submit button is centred in the form")


def run(url: str, output: Path) -> int:
    output.mkdir(parents=True, exist_ok=True)
    respond, selected = fixtures(url)
    report = Report()
    errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        for language, theme, width in [("en", "dark", 1440), ("ru", "light", 1024), ("ru", "dark", 390)]:
            context = browser.new_context(viewport=dict(width=width, height=1000))
            context.add_init_script(f"localStorage.setItem('trueroi-theme','{theme}'); localStorage.setItem('trueroi-language','{language}');")
            context.route(f"{url}/api/**", respond)
            context.route("**/qa-skin.svg", lambda route: route.fulfill(content_type="image/svg+xml", body=SVG))
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            base = f"{url}/?q=Code&skin=skin-qa"

            def open_view(scope: str, query: str, ready: str, checks) -> None:
                report.scope = f"{scope} {width}px {language}"
                page.goto(base + query)
                page.locator(ready).first.wait_for(timeout=15000)
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(500)  # tab indicator and dialog transitions
                check_page(page, report, width)
                for check in checks: check()
                page.screenshot(path=str(output / f"alignment-{scope}-{language}-{width}.png"), full_page=True)

            open_view("catalogue", "", "button[class*=qualityCard]",
                      [lambda: check_header(report), lambda: check_catalogue(page, report, width)])
            open_view("listings", "&wear=Field-Tested&listing_market=all", "button[class*=listingCard]",
                      [lambda: check_listings(page, report, width)])
            detail = f"&wear=Field-Tested&detail_variant={selected['id']}&listing=csfloat-1&analytics_market=csfloat"
            for tab in ("history", "active", "quick"):
                open_view(f"detail-{tab}", f"{detail}&tab={tab}", "nav[class*=analyticsTabs]",
                          [lambda: check_detail(page, report, width)])
            open_view("compare", f"{detail}&tab=compare&compare_buy=csfloat&compare_sell=dmarket",
                      "article[class*=comparePreview]",
                      [lambda: check_detail(page, report, width), lambda: check_compare(page, report, width)])

            report.scope = f"calculator {width}px {language}"
            page.goto(f"{url}/calculator?skin=skin-qa&variant={selected['id']}")
            page.locator("select[name='skin-variant']").wait_for()
            page.locator("button[type='submit']").click()
            page.locator("div[class*='heroResult']").wait_for()
            page.wait_for_load_state("networkidle")
            check_page(page, report, width)
            check_header(report)
            check_calculator(page, report, width)
            page.screenshot(path=str(output / f"alignment-calculator-{language}-{width}.png"), full_page=True)
            context.close()
        browser.close()
    for failure in report.failures: print("FAIL", failure, flush=True)
    for error in errors: print("PAGE ERROR", error, flush=True)
    print(f"Alignment: {report.passed} checks passed, {len(report.failures)} failed", flush=True)
    return 1 if report.failures or errors else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:5173")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.exit(run(args.url.rstrip("/"), args.output))
