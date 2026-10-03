import { describe, expect, it } from "vitest";
import type { CachedMarketPrices, MarketComparisonResponse, MarketPrice, ProfitOpportunity, VariantComparison } from "@/shared/api";
import { csMoneyRefreshInterval, mergeCsMoneyPrices } from "./csMoneyComparison";
import { selectQualityCardMarketData } from "./qualityCard";
import { resolveMarketAsk } from "./quoteSource";

function quote(price_cents = 1000, extra: Partial<MarketPrice> = {}): MarketPrice {
  return { marketplace: "csmoney", price_cents, item_url: "https://cs.money/", listing_id: "1",
    float_value: null, quantity: 1, fetched_at: "2026-10-03T08:00:00Z", stale: false, source: "storefront", ...extra };
}
function snapshot(listing: MarketPrice | null): CachedMarketPrices {
  return { marketplace: "csmoney", cache_ttl_seconds: 1800, refresh_queued: listing == null,
    variants: [{ variant_id: "normal-ft", market_hash_name: "Redline (Field-Tested)", listing }] };
}
function comparison(opportunities: ProfitOpportunity[] = []): MarketComparisonResponse {
  const variant: VariantComparison = { variant_id: "normal-ft", market_hash_name: "Redline (Field-Tested)",
    markets: { csmoney: quote(), csfloat: quote(1200, { marketplace: "csfloat" }) }, errors: { csmoney: "Old failure" },
    cheapest_marketplace: "csmoney", cheapest_price_cents: 1000, gross_spread_cents: 200, opportunities };
  return { skin_id: "skin-1", marketplaces: [], variants: [variant] };
}

describe("independent CS.MONEY cache", () => {
  it("supplies quality cards and Compare before the combined comparison arrives", () => {
    const variants = mergeCsMoneyPrices(undefined, snapshot(quote()));
    const card = selectQualityCardMarketData([...variants.values()], "all", "auto");
    expect(card.cheapest?.quote.price_cents).toBe(1000);
    expect(resolveMarketAsk(variants.get("normal-ft")?.markets.csmoney).price_cents).toBe(1000);
    expect(card.best).toBeUndefined();
  });

  it("merges exact variant IDs, preserves other markets and clears old CS.MONEY errors", () => {
    const old = comparison();
    old.variants.push({ ...old.variants[0]!, variant_id: "stattrak-ft", markets: { csfloat: quote(9000) } });
    const merged = mergeCsMoneyPrices(old, snapshot(quote(1100)));
    expect(merged.get("normal-ft")?.markets.csfloat?.price_cents).toBe(1200);
    expect(merged.get("normal-ft")?.markets.csmoney?.price_cents).toBe(1100);
    expect(merged.get("normal-ft")?.errors.csmoney).toBeUndefined();
    expect(merged.get("stattrak-ft")?.markets.csmoney).toBeUndefined();
    expect(old.variants[0]?.markets.csmoney?.price_cents).toBe(1000);
  });

  it("does not roll a newer comparison back to an older cache response", () => {
    const merged = mergeCsMoneyPrices(comparison(), snapshot(quote(900, { fetched_at: "2026-10-03T07:59:00Z" })));
    expect(merged.get("normal-ft")?.markets.csmoney?.price_cents).toBe(1000);
  });

  it.each([null, quote(800, { stale: true })])("excludes an expired or missing quote from cards and Compare", (listing) => {
    const merged = mergeCsMoneyPrices(comparison(), snapshot(listing));
    expect(selectQualityCardMarketData([...merged.values()], "all", "auto").cheapest?.marketplaceId).toBe("csfloat");
    expect(resolveMarketAsk(merged.get("normal-ft")?.markets.csmoney).price_cents).toBeNull();
  });

  it.each([quote(1100), quote(1000, { source: "wiki_market_summary" }), null])(
    "drops outdated CS.MONEY ROI while preserving unrelated opportunities", (listing) => {
      // Only the quote fields consumed by the merger are relevant here.
      const csBuy = { buy_marketplace: "csmoney", sell_marketplace: "csfloat", buy_price_cents: 1000,
        sell_price_cents: 1200, buy_quote_source: "storefront" } as ProfitOpportunity;
      const csSell = { ...csBuy, buy_marketplace: "csfloat", sell_marketplace: "csmoney",
        buy_price_cents: 1200, sell_price_cents: 1000, sell_quote_source: "storefront" } as ProfitOpportunity;
      const unrelated = { ...csBuy, buy_marketplace: "whitemarket" };
      expect(mergeCsMoneyPrices(comparison([csBuy, csSell, unrelated]), snapshot(listing))
        .get("normal-ft")?.opportunities).toEqual([unrelated]);
    },
  );

  it("polls queued refreshes promptly and slows down after completion", () => {
    expect(csMoneyRefreshInterval({ refresh_queued: true })).toBe(5000);
    expect(csMoneyRefreshInterval({ refresh_queued: false })).toBe(60000);
  });
});
