import type { CachedMarketPrices, MarketComparisonResponse, MarketPrice, VariantComparison } from "@/shared/api";

export function csMoneyRefreshInterval(snapshot?: { refresh_queued?: boolean }): number {
  return snapshot?.refresh_queued ? 5_000 : 60_000;
}

export function mergeCsMoneyPrices(
  comparison?: MarketComparisonResponse,
  snapshot?: CachedMarketPrices,
): Map<string, VariantComparison> {
  const variants = new Map((comparison?.variants ?? []).map((item) => [item.variant_id, item]));
  for (const item of snapshot?.variants ?? []) {
    const previous = variants.get(item.variant_id);
    const oldQuote = previous?.markets.csmoney;
    const oldTime = Date.parse(oldQuote?.fetched_at ?? "");
    const newTime = Date.parse(item.listing?.fetched_at ?? "");
    const newerComparison = Boolean(oldQuote && item.listing && oldTime > newTime);
    const quote = newerComparison ? oldQuote! : item.listing;
    const markets: VariantComparison["markets"] = {
      ...previous?.markets, csmoney: quote ? { ...quote, marketplace: "csmoney" } : null,
    };
    const fresh = Object.entries(markets)
      .filter((entry): entry is [string, MarketPrice] => entry[1] != null && !entry[1].stale)
      .sort((left, right) => left[1].price_cents - right[1].price_cents);
    const errors = { ...previous?.errors };
    if (!newerComparison) {
      delete errors.csmoney;
      if (item.error) errors.csmoney = item.error;
    }
    // Profit calculations from the earlier snapshot cannot be paired with a new ask.
    const opportunities = (previous?.opportunities ?? []).filter((opportunity) => {
      if (opportunity.buy_marketplace === "csmoney" &&
          (!quote || quote.stale || opportunity.buy_price_cents !== quote.price_cents ||
            (opportunity.buy_quote_source && quote.source && opportunity.buy_quote_source !== quote.source))) return false;
      if (opportunity.sell_marketplace === "csmoney" &&
          (!quote || quote.stale || opportunity.sell_price_cents !== quote.price_cents ||
            (opportunity.sell_quote_source && quote.source && opportunity.sell_quote_source !== quote.source))) return false;
      return true;
    });
    variants.set(item.variant_id, {
      variant_id: item.variant_id, market_hash_name: item.market_hash_name,
      markets, errors,
      cheapest_marketplace: fresh[0]?.[0] ?? null,
      cheapest_price_cents: fresh[0]?.[1]?.price_cents ?? null,
      gross_spread_cents: fresh.length > 1 ? fresh.at(-1)![1].price_cents - fresh[0]![1].price_cents : null,
      opportunities,
    });
  }
  return variants;
}
