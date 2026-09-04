import type { MarketPrice, ProfitOpportunity, VariantComparison } from "@/shared/api";

export type QualityCardQuote = {
  marketplaceId: string;
  quote: MarketPrice;
  variant: VariantComparison;
};

/**
 * Keep the displayed price and profit tied to the same exact market variant.
 * A wear group can contain normal, StatTrak and Souvenir variants whose prices
 * differ by hundreds of dollars, so mixing their metrics is misleading.
 */
export function selectQualityCardMarketData(
  variants: VariantComparison[],
  buyMarketplace: string,
  sellMarketplace: string,
): { quotes: QualityCardQuote[]; cheapest?: QualityCardQuote; best?: ProfitOpportunity } {
  const quotes = variants
    .flatMap((variant) => Object.entries(variant.markets)
      .filter((entry): entry is [string, MarketPrice] => entry[1] != null)
      .map(([marketplaceId, quote]) => ({ marketplaceId, quote, variant })))
    .sort((left, right) => left.quote.price_cents - right.quote.price_cents);

  const cheapest = quotes[0];
  const opportunities = (cheapest?.variant.opportunities ?? [])
    .filter((item) => (
      (buyMarketplace === "all" || item.buy_marketplace === buyMarketplace)
      && (sellMarketplace === "auto" || item.sell_marketplace === sellMarketplace)
    ))
    .sort((left, right) => right.profit_cents - left.profit_cents);

  return { quotes, cheapest, best: opportunities[0] };
}
