"""Offline Edge check: development diagnostics work, production has none."""
import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")


def check(dev: str, production: str, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    secret = "DEBUG_SECRET_SENTINEL"
    timestamp = "2026-10-03T10:00:00Z"
    served = []
    def response(route):
        path = urlparse(route.request.url).path
        served.append(path)
        status = 200
        if path == "/api/health":
            status = 503
            data = {"detail": f"Service failed api_key={secret}"}
        elif path == "/api/marketplaces": data = []
        elif path == "/api/catalog/filters": data = dict(item_types=[], weapons=[], rarities=[], collections=[])
        elif path == "/api/items/search": data = []
        elif path == "/api/skins/skin-qa": data = dict(id="skin-qa", name="Debug item", item_type="skin", collections=[],
            image_url="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'/%3E",
            qualities=[dict(wear="Field-Tested", variants=[dict(id="v1", market_hash_name="Debug item (Field-Tested)")])])
        elif path.endswith("/markets/compare"): data = dict(skin_id="skin-qa", marketplaces=[], variants=[])
        elif path.endswith("/market/csmoney"):
            data = dict(marketplace="CS.MONEY", cache_ttl_seconds=1800, refresh_queued=False,
                variants=[dict(variant_id="v1", market_hash_name="Debug item", error=f"Refresh failed token={secret}",
                    listing=dict(price_cents=1000, item_url="https://example.test/", source="wiki_market_summary", fetched_at=timestamp, stale=False))])
        else: data = {}
        route.fulfill(status=status, content_type="application/json", body=json.dumps(data))

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport=dict(width=1440, height=1000))
        context.add_init_script("localStorage.setItem('trueroi-language','en'); localStorage.setItem('trueroi-theme','dark'); localStorage.setItem('trueroi-debug','true');")
        context.route(dev + "/api/**", response)
        context.route(production + "/api/**", response)
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
        try:
            with page.expect_response(lambda response: urlparse(response.url).path.endswith("/market/csmoney"), timeout=10000) as source_response:
                page.goto(dev + "/?skin=skin-qa")
            assert source_response.value.status == 200
            page.get_by_role("heading", name="Debug item", exact=True).wait_for(timeout=10000)
            page.get_by_text("From $10.00", exact=True).wait_for(timeout=10000)
        except Exception:
            page.screenshot(path=str(output / "debug-initial-failure.png"), full_page=True)
            print("Page errors:", errors, "Served API:", served, "URL:", page.url, "UI:", page.locator("body").inner_text(), flush=True)
            raise
        page.get_by_role("link", name="Debug", exact=True).click()
        marker = page.get_by_test_id("TRUEROI_DEV_DIAGNOSTICS")
        marker.wait_for()
        page.locator("summary").filter(has_text="csmoney-prices").click()
        try:
            page.get_by_text("wiki_market_summary", exact=True).wait_for(timeout=10000)
        except Exception:
            print("Diagnostic UI:", marker.inner_text(), "Errors:", errors, flush=True)
            page.screenshot(path=str(output / "debug-source-failure.png"), full_page=True)
            raise
        shown = marker.inner_text()
        assert timestamp in shown and "Refresh failed token=[redacted]" in shown
        assert "503" in shown and "api_key=[redacted]" in shown
        assert secret not in shown
        page.screenshot(path=str(output / "debug-en-desktop.png"), full_page=True)
        page.set_viewport_size(dict(width=390, height=1000))
        page.get_by_role("button", name="Switch language to RU").click()
        page.get_by_role("heading", name="Диагностика данных", exact=True).wait_for()
        assert page.locator("html").evaluate("e => e.scrollWidth") <= 390
        page.screenshot(path=str(output / "debug-ru-mobile.png"), full_page=True)
        print("Development: HTTP failures, backend sources, dates, redaction and RU mobile layout passed", flush=True)

        for target in ["/debug", "/?debug=true"]:
            page.goto(production + target)
            page.locator("body").wait_for()
            assert page.get_by_test_id("TRUEROI_DEV_DIAGNOSTICS").count() == 0
            assert page.get_by_role("link", name="Debug", exact=True).count() == 0
        print("Production: /debug, URL flag and localStorage cannot enable diagnostics", flush=True)
        context.close()
        browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev", default="http://127.0.0.1:5174")
    parser.add_argument("--production", default="http://127.0.0.1:5175")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    check(args.dev.rstrip("/"), args.production.rstrip("/"), args.output)
