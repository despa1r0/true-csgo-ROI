import { beforeAll, describe, expect, it } from "vitest";
import { createInstance } from "i18next";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { I18nextProvider } from "react-i18next";

import type { Listing, ListingFilters, ListingsResponse, MarketPrice, MarketSourceState, MarketplaceDetails, MarketplaceOption, WikiPriceHistory } from "@/shared/api";
import en from "@/shared/i18n/locales/en.json";
import ru from "@/shared/i18n/locales/ru.json";
import {
  activeListingCount,
  attachmentTooltip,
  detailComponentForTab,
  detailComponentFresh,
  liquidityScoreIfFresh,
  wikiTradeHistoryFresh,
  filtersForMarketplace,
  isPaintIndexUnavailable,
  listingSnapshotStale,
  selectedListingIsStale,
  SourceStateStatus,
  sourceStatusKey,
  unsupportedAttachmentFilters,
} from "./ListingDialog";
import { marketQuoteSource, opportunityQuoteSources, QuoteProvenance, resolveMarketAsk } from "./quoteSource";

function marketplace(overrides: Partial<MarketplaceOption["capabilities"]> = {}): MarketplaceOption {
  return {
    id: "test-market",
    display_name: "Test Market",
    currency: "USD",
    can_buy: true,
    can_sell: true,
    supports_fast_buy: false,
    capabilities: {
      can_buy: true,
      can_sell: true,
      supports_listings: true,
      supports_sales_history: false,
      supports_quick_sell: false,
      supports_float: false,
      supports_stickers: false,
      supports_charms: false,
      supports_best_deal_sort: false,
      ...overrides,
    },
    deposit_methods: ["crypto"],
    withdraw_methods: ["crypto"],
    fees: { deposit: {}, sell: null, withdraw: {} },
    fee_configuration_version: "test",
  };
}

describe("listing marketplace helpers", () => {
  it("keeps all-market requests compatible with each provider", () => {
    const filters: ListingFilters = { sort_by: "best_deal", has_stickers: true, has_charm: true };
    const basicMarket = marketplace({ supports_stickers: true });

    expect(filtersForMarketplace(filters, basicMarket).sort_by).toBe("lowest_price");
    expect(unsupportedAttachmentFilters(filters, basicMarket)).toEqual(["charms"]);
  });

  it("shows an attachment price in the hover text when the provider supplies it", () => {
    expect(attachmentTooltip("Sticker | Test", 256, "en-US", "Reference price", "Unavailable"))
      .toContain("$2.56");
    expect(attachmentTooltip("Charm | Test", null, "en-US", "Reference price", "Unavailable"))
      .toBe("Charm | Test · Unavailable");
  });

  it("recognizes both English and Russian legacy paint-index errors", () => {
    expect(isPaintIndexUnavailable("This item has no paint index")).toBe(true);
    expect(isPaintIndexUnavailable("Для скина отсутствует индекс покраски")).toBe(true);
  });

  it("maps analytics tabs to independently refreshed cache components", () => {
    expect(detailComponentForTab("history")).toBe("sales");
    expect(detailComponentForTab("active")).toBe("listings");
    expect(detailComponentForTab("quick")).toBe("buy_orders");
    expect(detailComponentForTab("compare")).toBeUndefined();
  });
});

describe("CS.MONEY source status", () => {
  const i18n = createInstance();
  beforeAll(async () => {
    await i18n.init({ lng: "en", resources: { en: { translation: en }, ru: { translation: ru } }, interpolation: { escapeValue: false } });
  });
  const cases: Array<[MarketSourceState, string]> = [
    ["listings_available", "marketSource.listingsAvailable"],
    ["summary_only", "marketSource.summaryOnly"],
    ["provider_unavailable", "marketSource.providerUnavailable"],
    ["stale", "marketSource.stale"],
    ["empty", "marketSource.empty"],
    ["partial", "marketSource.partial"],
  ];
  function render(snapshot: Partial<ListingsResponse>, fallback = false) {
    return renderToStaticMarkup(createElement(I18nextProvider, { i18n }, createElement(SourceStateStatus, { snapshot, locale: "en-US", fallback })));
  }

  it.each(cases)("maps %s independently of HTTP success and legacy cache flags", (state, key) => {
    expect(sourceStatusKey({ source_state: state, fetched_at: "2026-09-30T00:00:00Z", cached: false, stale: false })).toBe(key);
    expect(sourceStatusKey({ source_state: state, cached: true, stale: true })).toBe(key);
    const html = render({ source_state: state });
    expect(html).toContain(i18n.t(key));
    expect(html).not.toContain("Current data");
    for (const language of [en, ru]) {
      expect(language.marketSource[key.split(".")[1] as keyof typeof language.marketSource]).toBeTruthy();
      const note = state === "summary_only" ? "summaryNote" : `${state}Note`;
      expect(language.marketSource[note as keyof typeof language.marketSource]).toBeTruthy();
    }
  });

  it("falls back only when source_state is absent, without claiming live data", () => {
    const fetched_at = "2026-09-30T00:00:00Z";
    expect(sourceStatusKey()).toBe("analytics.quoteUnavailable");
    expect(sourceStatusKey({ fetched_at })).toBe("analytics.dataFresh");
    expect(sourceStatusKey({ fetched_at, cached: true })).toBe("common.cached");
    expect(sourceStatusKey({ fetched_at, stale: true })).toBe("common.cached");
    expect(sourceStatusKey({ fetched_at, stale: true, is_stale: false })).toBe("analytics.dataFresh");
    expect(render({ fetched_at })).toBe("");
    expect(render({ fetched_at, stale: true, is_partial: true }, true)).toContain("stale cache");
    expect(render({ fetched_at }, true)).not.toContain("Current data");
  });

  it("keeps healthy and failed variant states visible in a partial response", () => {
    const variant_states: ListingsResponse["variant_states"] = cases.slice(0, 5).map(([source_state], index) => ({
      variant_id: `variant-${index}`, source_state, status: source_state === "provider_unavailable" ? "unavailable" : "ok", stale: false, is_partial: false,
    }));
    const html = render({ source_state: "partial", variant_states });
    variant_states.forEach((state) => {
      expect(html).toContain(state.variant_id);
      expect(html).toContain(i18n.t(sourceStatusKey(state)));
    });
  });

  it("never counts the Wiki Market aggregate as concrete listings", () => {
    const details: MarketplaceDetails = { marketplace: "csmoney", variant_id: "test", market_hash_name: "Test", overview: { active_listings: 900 }, listings: [] };
    expect(activeListingCount({ ...details, source_state: "summary_only" })).toBe(0);
    expect(activeListingCount({ ...details, quote_source: "wiki_market_summary" })).toBe(0);
    expect(activeListingCount(details)).toBe(900);
    expect(activeListingCount(undefined)).toBeUndefined();
    const html = render({ source_state: "summary_only" });
    expect(html).toContain("not executable or filtered listings");
    expect(html).toContain("individual listing IDs");
  });

  it("uses the selected variant freshness rather than a degraded group flag", () => {
    const snapshot: Partial<ListingsResponse> = {
      source_state: "partial", stale: true, variant_states: [
        { variant_id: "healthy", source_state: "listings_available", status: "ok", stale: false, is_partial: false },
        { variant_id: "old", source_state: "stale", status: "stale", stale: true, is_partial: false },
      ],
    };
    expect(listingSnapshotStale(snapshot, "healthy")).toBe(false);
    expect(listingSnapshotStale(snapshot, "old")).toBe(true);
    expect(listingSnapshotStale({ source_state: "stale", stale: false })).toBe(true);
    expect(listingSnapshotStale({ is_stale: false, stale: true })).toBe(false);
    expect(listingSnapshotStale()).toBe(false);
  });
});

describe("quote provenance and component freshness", () => {
  const listing: Listing = { listing_id: "fresh", variant_id: "v1", market_hash_name: "Test", price_cents: 200 };
  const quote: MarketPrice = {
    marketplace: "csmoney", price_cents: 100, quantity: 1, stale: true, source: "wiki_market_summary",
    item_url: "https://example.invalid", listing_id: null, float_value: null, fetched_at: null,
  };
  const details: MarketplaceDetails = {
    marketplace: "csmoney", variant_id: "v1", market_hash_name: "Test",
    overview: { price_cents: 200 }, quote_source: "storefront", listings: [listing],
  };

  it("rejects a stale row even when its variant has a fresh sibling", () => {
    const snapshot: Partial<ListingsResponse> = { variant_states: [
      { variant_id: "v1", source_state: "listings_available", status: "ok", stale: false, is_partial: false },
    ] };
    const oldListing = { ...listing, listing_id: "old", price_cents: 1, stale: true };
    expect(selectedListingIsStale(oldListing, snapshot)).toBe(true);
    expect(selectedListingIsStale(listing, snapshot)).toBe(false);
    expect(resolveMarketAsk(undefined, undefined, false, oldListing)).toEqual({ price_cents: null, source: null });
  });

  it("takes price, source and preview from the same fresh fallback", () => {
    expect(resolveMarketAsk(quote, details, true)).toEqual({ price_cents: 200, source: "storefront", listing });
    expect(resolveMarketAsk({ ...quote, source: "storefront" }, { ...details, quote_source: "wiki_market_summary", listings: [] }, true))
      .toEqual({ price_cents: 200, source: "wiki_market_summary", listing: undefined });
    expect(resolveMarketAsk(quote, details, false)).toEqual({ price_cents: null, source: null });
  });

  it("does not attach an unrelated selected lot to a market ask", () => {
    const marketAsk = { ...quote, source: "storefront" as const, stale: false, price_cents: 200, listing_id: "fresh" };
    const selected = { ...listing, listing_id: "selected", price_cents: 250 };
    expect(resolveMarketAsk(marketAsk, details, true, selected)).toEqual({ price_cents: 250, source: "listing", listing: selected });
    expect(resolveMarketAsk(marketAsk, details, true)).toEqual({ price_cents: 200, source: "storefront", listing });
    expect(resolveMarketAsk({ ...marketAsk, listing_id: "unavailable" }, details, true).listing).toBeUndefined();
  });

  it("uses the opportunity's actual source for both sides of ROI", async () => {
    const opportunity = {
      buy_marketplace: "csmoney", sell_marketplace: "csfloat",
      buy_quote_source: "wiki_market_summary", sell_quote_source: "best_bid",
    } as Parameters<typeof opportunityQuoteSources>[0];
    expect(opportunityQuoteSources(opportunity)).toEqual({ buy: "wiki_market_summary", sell: "best_bid" });
    expect(marketQuoteSource({ source: "wiki_market_summary" } as Parameters<typeof marketQuoteSource>[0])).toBe("wiki_market_summary");
    expect(marketQuoteSource(undefined, undefined, true)).toBe("listing");
    const i18n = createInstance();
    await i18n.init({ lng: "en", resources: { en: { translation: en } }, interpolation: { escapeValue: false } });
    const html = renderToStaticMarkup(createElement(I18nextProvider, { i18n }, createElement(QuoteProvenance, { buy: "wiki_market_summary", sell: "best_bid" })));
    expect(html).toContain("Wiki Market aggregate reference");
    expect(html).toContain("buy order");
    expect(html).toContain("not executable or filtered listings");
  });

  it("keeps a fresh bid and ask usable when sales failed", () => {
    const details = {
      marketplace: "csmoney", variant_id: "v1", market_hash_name: "Test",
      overview: { price_cents: 100 }, stats: { liquidity_score: 75 }, stale: true,
      components: {
        listings: { status: "fresh" }, buy_orders: { status: "fresh" }, sales: { status: "unavailable" },
      },
    } as MarketplaceDetails;
    expect(detailComponentFresh(details, "listings")).toBe(true);
    expect(detailComponentFresh(details, "buy_orders")).toBe(true);
    expect(detailComponentFresh(details, "sales")).toBe(false);
    expect(liquidityScoreIfFresh(details)).toBeUndefined();
    expect(liquidityScoreIfFresh({ ...details, components: { ...details.components, sales: { status: "fresh" } } })).toBe(75);
    expect(detailComponentFresh({ ...details, components: { listings: { status: "stale" } } }, "listings")).toBe(false);
  });

  it("hides Wiki Trade quotes as soon as the 72-hour window expires", () => {
    const latest = Date.parse("2026-09-27T12:00:00Z");
    const history = {
      source: "csmoney_wiki_trade_quote", source_url: "", currency: "USD",
      points: [{ at: "2026-09-27T12:00:00Z", price_cents: 100 }],
      latest_at: "2026-09-27T12:00:00Z", fetched_at: "2026-09-27T12:01:00Z", error: null,
    } as WikiPriceHistory;
    expect(wikiTradeHistoryFresh(history, latest + 72 * 60 * 60 * 1000)).toBe(true);
    expect(wikiTradeHistoryFresh(history, latest + 72 * 60 * 60 * 1000 + 1)).toBe(false);
    expect(wikiTradeHistoryFresh({ ...history, error: "provider unavailable" }, latest)).toBe(false);
    expect(wikiTradeHistoryFresh({ ...history, latest_at: null }, latest)).toBe(false);
  });
});
