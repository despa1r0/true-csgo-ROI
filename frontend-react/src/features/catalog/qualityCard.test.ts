import { describe, expect, it } from "vitest";

import type { MarketPrice, ProfitOpportunity, VariantComparison } from "@/shared/api";
import { selectQualityCardMarketData } from "./qualityCard";

function quote(price_cents: number): MarketPrice {
  return {
    marketplace: "csfloat",
    price_cents,
    item_url: "https://example.test",
    listing_id: null,
    float_value: null,
    quantity: 1,
    fetched_at: null,
    stale: false,
  };
}

function opportunity(profit_cents: number): ProfitOpportunity {
  return {
    buy_marketplace: "csfloat",
    sell_marketplace: "csgomarket",
    sell_mode: "listing",
    profit_mode: "smart",
    buy_price_cents: 5904,
    deposit_fee_cents: 59,
    sell_price_cents: 6373,
    sell_fee_cents: 319,
    withdraw_fee_cents: 100,
    gross_profit_cents: 469,
    market_profit_cents: 150,
    profit_cents,
    gross_roi_percent: 7.94,
    market_roi_percent: 2.54,
    cash_roi_percent: -0.15,
    roi_percent: -0.15,
    effective_buy_cents: 5963,
    effective_payout_cents: 5954,
    break_even_sell_price_cents: 6288,
  };
}

function variant(id: string, price: number, profit: number): VariantComparison {
  return {
    variant_id: id,
    market_hash_name: id,
    markets: { csfloat: quote(price) },
    errors: {},
    cheapest_marketplace: "csfloat",
    cheapest_price_cents: price,
    gross_spread_cents: null,
    opportunities: [opportunity(profit)],
  };
}

describe("selectQualityCardMarketData", () => {
  it("does not pair a normal skin price with a Souvenir opportunity", () => {
    const normal = variant("golden-coil-ft", 5904, -9);
    const souvenir = variant("souvenir-golden-coil-ft", 31627, 16224);

    const result = selectQualityCardMarketData([normal, souvenir], "all", "auto");

    expect(result.cheapest?.variant.variant_id).toBe("golden-coil-ft");
    expect(result.cheapest?.quote.price_cents).toBe(5904);
    expect(result.best?.profit_cents).toBe(-9);
  });

  it("applies an explicit sell-market filter even when buying from all markets", () => {
    const normal = variant("golden-coil-ft", 5904, -9);

    const result = selectQualityCardMarketData([normal], "all", "whitemarket");

    expect(result.best).toBeUndefined();
  });
});
