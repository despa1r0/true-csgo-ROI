import { useTranslation } from "react-i18next";

import type { Listing, MarketplaceDetails, MarketPrice, ProfitOpportunity, QuoteSource, VariantComparison } from "@/shared/api";
import styles from "./market.module.css";

export function marketQuoteSource(quote?: MarketPrice | null, details?: MarketplaceDetails, selectedListing = false): QuoteSource {
  if (selectedListing) return "listing";
  if (quote?.source) return quote.source;
  if (quote?.listing_id) return "listing";
  if (details?.quote_source === "wiki_market_summary") return "wiki_market_summary";
  if (details?.quote_source === "storefront") return "storefront";
  return "index";
}

export type ResolvedAsk = { price_cents: number | null; source: QuoteSource | null; listing?: Listing };

export function resolveMarketAsk(
  quote?: MarketPrice | null,
  details?: MarketplaceDetails,
  detailListingsFresh = false,
  selectedListing?: Listing,
): ResolvedAsk {
  if (selectedListing && !selectedListing.stale) {
    return { price_cents: selectedListing.price_cents, source: "listing", listing: selectedListing };
  }
  if (quote && !quote.stale) {
    const source = marketQuoteSource(quote);
    const listing = detailListingsFresh && (source === "listing" || source === "storefront")
      ? details?.listings?.find((item) => !item.stale && item.listing_id === quote.listing_id && item.price_cents === quote.price_cents)
      : undefined;
    return { price_cents: quote.price_cents, source, listing };
  }
  const price = detailListingsFresh ? details?.overview.price_cents : null;
  if (price == null) return { price_cents: null, source: null };
  const source = details?.quote_source === "wiki_market_summary" ? "wiki_market_summary"
    : details?.quote_source === "storefront" ? "storefront"
      : details?.quote_source === "mixed" ? null : "index";
  const listing = source === "storefront"
    ? details?.listings?.find((item) => !item.stale && item.price_cents === price)
    : undefined;
  return { price_cents: price, source, listing };
}

export function opportunityQuoteSources(opportunity: ProfitOpportunity, comparison?: VariantComparison): { buy: QuoteSource; sell: QuoteSource } {
  return {
    buy: opportunity.buy_quote_source ?? marketQuoteSource(comparison?.markets[opportunity.buy_marketplace]),
    sell: opportunity.sell_quote_source ?? (opportunity.sell_price_source === "best_bid" ? "best_bid" : marketQuoteSource(comparison?.markets[opportunity.sell_marketplace])),
  };
}

export function QuoteProvenance({ buy, sell }: { buy: QuoteSource | null; sell: QuoteSource | null }) {
  const { t } = useTranslation();
  if (buy !== "wiki_market_summary" && sell !== "wiki_market_summary") return null;
  return <span className={styles.quoteLabel}>{t("marketSource.referenceQuote")}</span>;
}
