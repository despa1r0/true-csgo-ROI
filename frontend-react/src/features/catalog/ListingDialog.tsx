import * as Dialog from "@radix-ui/react-dialog";
import { useQueries, useQuery } from "@tanstack/react-query";
import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { api, type DetailComponentName, type Listing, type ListingFilters, type ListingsResponse, type MarketSourceState, type MarketplaceDetails, type MarketplaceOption, type ProfitMode, type Sale, type SellMode, type SkinDetails, type SkinQuality, type VariantComparison, type VariantKind, type SkinVariant, type WikiPriceHistory } from "@/shared/api";
import { formatDate, formatNumber, formatUsd } from "@/shared/lib/format";
import { detailParams, useBrowseHistory, useBrowseScroll } from "@/shared/lib/browseHistory";
import type { HistoryPeriod } from "@/features/analytics/SalesChart";
import styles from "./market.module.css";
import { FlipRiskNotice } from "./FlipRiskNotice";
import { flipRiskLevel } from "./flipRisk";
import { QuoteProvenance, resolveMarketAsk } from "./quoteSource";

const wearSlugs: Record<string, ListingFilters["wear"]> = { "Factory New": "factory-new", "Minimal Wear": "minimal-wear", "Field-Tested": "field-tested", "Well-Worn": "well-worn", "Battle-Scarred": "battle-scarred" };
const SalesChart = lazy(() => import("@/features/analytics/SalesChart").then((module) => ({ default: module.SalesChart })));
const PriceHistoryChart = lazy(() => import("@/features/analytics/PriceHistoryChart").then((module) => ({ default: module.PriceHistoryChart })));
const wearCodes: Record<string, string> = { "Factory New": "FN", "Minimal Wear": "MW", "Field-Tested": "FT", "Well-Worn": "WW", "Battle-Scarred": "BS" };
const ALL_MARKETS = "all";
type Tab = "history" | "active" | "quick" | "compare";
const analyticsTabs: Tab[] = ["history", "active", "quick", "compare"];
const detailComponentLabels: Record<DetailComponentName, string> = {
  listings: "analytics.dataListings",
  sales: "analytics.dataSales",
  buy_orders: "analytics.dataBuyOrders",
};
const detailStatusLabels = {
  fresh: "analytics.dataFresh",
  stale: "analytics.dataStale",
  unavailable: "analytics.dataUnavailable",
} as const;

function browseFilters(params: URLSearchParams, wear: string): ListingFilters {
  const number = (key: string) => params.get(key) ? Number(params.get(key)!.replace(",", ".")) : undefined;
  const minPrice = number("min_price"), maxPrice = number("max_price");
  return { wear: wearSlugs[wear], sort_by: params.get("sort") === "best_deal" ? "best_deal" : "lowest_price",
    variant: (["normal", "stattrak", "souvenir"] as VariantKind[]).find((item) => item === params.get("kind")) ?? "any",
    min_float: number("min_float"), max_float: number("max_float"),
    min_price_cents: minPrice == null ? undefined : Math.round(minPrice * 100),
    max_price_cents: maxPrice == null ? undefined : Math.round(maxPrice * 100),
    has_stickers: params.get("stickers") === "1", has_charm: params.get("charm") === "1", limit: 30 };
}

type Props = {
  skin: SkinDetails;
  quality: SkinQuality;
  marketplaces: MarketplaceOption[];
  comparison: Map<string, VariantComparison>;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

export function ListingDialog({ skin, quality, marketplaces, comparison, open, onOpenChange }: Props) {
  const { i18n, t } = useTranslation();
  const { params, location, update, back } = useBrowseHistory();
  const listScroll = useBrowseScroll();
  const listMarkets = marketplaces.filter((item) => item.capabilities.supports_listings);
  const marketId = params.get("listing_market") ?? listMarkets[0]?.id ?? "csfloat";
  const [sort, setSort] = useState<ListingFilters["sort_by"]>("lowest_price");
  const [variant, setVariant] = useState<VariantKind>("any");
  const [minFloat, setMinFloat] = useState("");
  const [maxFloat, setMaxFloat] = useState("");
  const [minPrice, setMinPrice] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [hasStickers, setHasStickers] = useState(false);
  const [hasCharm, setHasCharm] = useState(false);
  const [appliedFilters, setAppliedFilters] = useState<ListingFilters>(() => browseFilters(params, quality.wear));
  const detailVariantId = params.get("detail_variant") ?? undefined;
  const tab: Tab = analyticsTabs.find((item) => item === params.get("tab")) ?? "history";
  function setTab(value: Tab) { update({ tab: value }, true); }
  const analyticsMarket = params.get("analytics_market") ?? marketId;
  function setAnalyticsMarket(value: string) { update({ analytics_market: value }, true); }
  const period = (["24h", "7d", "14d", "all"] as HistoryPeriod[]).find((item) => item === params.get("period")) ?? "7d";
  function setPeriod(value: HistoryPeriod) { update({ period: value }, true); }
  const compareBuy = params.get("compare_buy") ?? listMarkets[0]?.id ?? "csfloat";
  const compareSell = params.get("compare_sell") ?? listMarkets[1]?.id ?? listMarkets[0]?.id ?? "csgomarket";
  function setCompareBuy(value: string) { update({ compare_buy: value }, true); }
  function setCompareSell(value: string) { update({ compare_sell: value }, true); }
  const market = marketplaces.find((item) => item.id === marketId);
  const listingMarkets = marketId === ALL_MARKETS ? listMarkets : listMarkets.filter((item) => item.id === marketId);
  const canSortBestDeal = listingMarkets.some((item) => item.capabilities.supports_best_deal_sort);
  const canFilterStickers = listingMarkets.some((item) => item.capabilities.supports_stickers);
  const canFilterCharms = listingMarkets.some((item) => item.capabilities.supports_charms);
  const locale = i18n.resolvedLanguage === "ru" ? "ru-RU" : "en-US";

  const listingFilters: ListingFilters = {
    wear: wearSlugs[quality.wear], sort_by: sort, variant, limit: 30,
    min_float: minFloat ? Number(minFloat) : undefined, max_float: maxFloat ? Number(maxFloat) : undefined,
    min_price_cents: minPrice ? Math.round(Number(minPrice.replace(",", ".")) * 100) : undefined,
    max_price_cents: maxPrice ? Math.round(Number(maxPrice.replace(",", ".")) * 100) : undefined,
    has_stickers: hasStickers, has_charm: hasCharm,
  };
  const listingQueries = useQueries({ queries: listingMarkets.map((marketplace) => {
    const filters = filtersForMarketplace(appliedFilters, marketplace);
    const unsupportedFilters = unsupportedAttachmentFilters(appliedFilters, marketplace);
    return {
      queryKey: ["listings", skin.id, marketplace.id, filters],
      queryFn: ({ signal }: { signal: AbortSignal }) => api.skinListings(skin.id, marketplace.id, filters, signal),
      enabled: open && unsupportedFilters.length === 0,
      staleTime: 120_000,
      refetchInterval: (query: { state: { data?: ListingsResponse } }) => query.state.data?.refresh_queued ? 5_000 : false,
    };
  }) });
  const visibleListingCount = listingQueries.reduce((count, query) => count + (query.data?.listings.length ?? 0), 0);
  const rememberedListing = location.state?.selectedListing as Listing | undefined;
  const listingId = params.get("listing");
  const selectedListing = listingId ? (rememberedListing?.listing_id === listingId && rememberedListing.variant_id === detailVariantId
    ? rememberedListing : listingQueries.flatMap((query, index) => (query.data?.listings ?? [])
      .map((listing) => ({ ...listing, marketplace_id: listing.marketplace_id ?? listingMarkets[index]?.id })))
      .find((listing) => listing.listing_id === listingId && listing.variant_id === detailVariantId)) ?? null : null;
  const selectedVariant = detailVariantId ? quality.variants.find((item) => item.id === detailVariantId) ?? null : null;
  const selectedListingStale = Boolean(selectedListing && (selectedListing.stale || location.state?.listingSnapshotStale));

  const analyticsMarkets = listMarkets;
  const detailQueries = useQueries({ queries: analyticsMarkets.map((item) => ({
    queryKey: ["variant-details", detailVariantId, item.id],
    queryFn: ({ signal }: { signal: AbortSignal }) => api.variantDetails(detailVariantId!, item.id, signal),
    enabled: Boolean(detailVariantId && (item.id === analyticsMarket || tab === "compare")), staleTime: 0,
    refetchInterval: item.id === "csmoney" ? (query: { state: { data?: MarketplaceDetails } }) => query.state.data?.refresh_queued ? 5_000 : 60_000 : false,
  })) });
  const detailsByMarket = useMemo(() => new Map<string, MarketplaceDetails>(detailQueries.map((query, index) => [analyticsMarkets[index]?.id ?? "", query.data]).filter((entry): entry is [string, MarketplaceDetails] => Boolean(entry[0] && entry[1]))), [analyticsMarkets, detailQueries]);
  const listingQuickSellQuery = useQuery({
    queryKey: ["listing-quick-sell", selectedListing?.listing_id],
    queryFn: ({ signal }) => api.listingQuickSell(selectedListing!.listing_id!, signal),
    enabled: Boolean(selectedListing?.listing_id && selectedListing.marketplace_id === "csfloat" && (tab === "quick" || tab === "compare")),
    staleTime: 600_000,
  });
  const selectedDetails = detailsByMarket.get(analyticsMarket);
  const selectedCapability = marketplaces.find((item) => item.id === analyticsMarket)?.capabilities;
  const selectedComparison = detailVariantId ? comparison.get(detailVariantId) : undefined;
  const selectedDetailQuery = detailQueries[analyticsMarkets.findIndex((item) => item.id === analyticsMarket)];
  const activeTabIndex = analyticsTabs.indexOf(tab);

  const filterState = ["sort", "kind", "min_float", "max_float", "min_price", "max_price", "stickers", "charm"].map((key) => params.get(key) ?? "").join("|");
  useEffect(() => {
    const restoredSort = params.get("sort") === "best_deal" ? "best_deal" : "lowest_price";
    const restoredVariant = (["normal", "stattrak", "souvenir"] as VariantKind[]).find((item) => item === params.get("kind")) ?? "any";
    const lowFloat = params.get("min_float") ?? "", highFloat = params.get("max_float") ?? "";
    const lowPrice = params.get("min_price") ?? "", highPrice = params.get("max_price") ?? "";
    const stickers = params.get("stickers") === "1", charm = params.get("charm") === "1";
    setSort(restoredSort); setVariant(restoredVariant); setMinFloat(lowFloat); setMaxFloat(highFloat);
    setMinPrice(lowPrice); setMaxPrice(highPrice); setHasStickers(stickers); setHasCharm(charm);
    setAppliedFilters(browseFilters(params, quality.wear));
  }, [filterState, quality.wear]);
  function resetFilters() { update({ sort: null, kind: null, min_float: null, max_float: null,
    min_price: null, max_price: null, stickers: null, charm: null }, true); }
  function applyFilters() {
    setAppliedFilters(listingFilters);
    update({ sort: sort ?? "lowest_price", kind: variant, min_float: minFloat, max_float: maxFloat,
      min_price: minPrice, max_price: maxPrice, stickers: hasStickers ? "1" : null, charm: hasCharm ? "1" : null }, true);
  }
  function openDetail(listing: Listing, marketplaceId: string, snapshot?: ListingsResponse) {
    const market = listing.marketplace_id ?? marketplaceId;
    update({ detail_variant: listing.variant_id ?? quality.variants.find((item) => item.market_hash_name === listing.market_hash_name)?.id ?? null,
      listing: listing.listing_id ?? null, analytics_market: market, tab: "history" }, false,
      { selectedListing: { ...listing, marketplace_id: market }, listingSnapshotStale: selectedListingIsStale(listing, snapshot) });
  }
  function openVariant(next: SkinVariant) { update({ detail_variant: next.id, listing: null, analytics_market: "csmoney", tab: "history" }); }
  function switchMarket(next: string) { update({ listing_market: next, ...(next !== ALL_MARKETS ? { analytics_market: next } : {}) }, true); }
  const currentSales = selectedDetails?.sales ?? [];
  const visibleSales = useMemo(() => filterSalesByPeriod(currentSales, period), [currentSales, period]);
  const freshListings = selectedDetails && detailComponentFresh(selectedDetails, "listings") ? selectedDetails : undefined;
  const freshSales = selectedDetails && detailComponentFresh(selectedDetails, "sales") ? selectedDetails : undefined;
  const freshBuyOrders = selectedDetails && detailComponentFresh(selectedDetails, "buy_orders") ? selectedDetails : undefined;
  const selectedQuickSell = analyticsMarket === "csfloat" && selectedListing?.marketplace_id === "csfloat" && !selectedListingStale && listingQuickSellQuery.data
    ? { ...freshBuyOrders?.quick_sell, ...listingQuickSellQuery.data }
    : freshBuyOrders?.quick_sell;

  return (
    <Dialog.Root open={open} onOpenChange={(next) => {
      if (!next && detailVariantId) back(detailParams); else onOpenChange(next);
    }}>
      <Dialog.Portal>
        <Dialog.Overlay className={styles.dialogOverlay} />
        <Dialog.Content className={styles.dialogContent} aria-describedby={undefined}>
          <Dialog.Close className={styles.dialogClose} aria-label={t("common.close")}>×</Dialog.Close>
          {!selectedListing && !selectedVariant ? (
            <div className={styles.browserView} ref={listScroll.ref} onScroll={listScroll.onScroll}>
              <header className={styles.dialogHeader}><div><span>{t("listings.title")}</span><Dialog.Title>{skin.name}</Dialog.Title><p>{marketId === ALL_MARKETS ? t("listings.subtitleAll", { wear: quality.wear }) : t("listings.subtitle", { wear: quality.wear, market: market?.display_name ?? marketId })}</p></div><strong>{t("listings.count", { count: visibleListingCount })}</strong></header>
              <section className={styles.listingToolbar}>
                <label><span>{t("listings.marketplace")}</span><select name="listing-marketplace" value={marketId} onChange={(event) => switchMarket(event.target.value)}><option value={ALL_MARKETS}>{t("listings.allMarketplaces")}</option>{listMarkets.map((item) => <option key={item.id} value={item.id}>{item.display_name}</option>)}</select></label>
                <label><span>{t("listings.sort")}</span><select name="listing-sort" value={sort} onChange={(event) => setSort(event.target.value as ListingFilters["sort_by"])}><option value="lowest_price">{t("listings.lowest")}</option><option disabled={!canSortBestDeal && sort !== "best_deal"} value="best_deal">{t("listings.bestDeal")}</option></select></label>
                <label><span>{t("listings.variant")}</span><select name="listing-variant" value={variant} onChange={(event) => setVariant(event.target.value as VariantKind)}><option value="any">{t("catalog.any")}</option><option value="normal">{t("listings.normal")}</option><option value="stattrak">{t("listings.stattrak")}</option><option value="souvenir">{t("listings.souvenir")}</option></select></label>
                <fieldset><legend>{t("listings.float")}</legend><input name="minimum-float" autoComplete="off" inputMode="decimal" aria-label={t("listings.minimumFloat")} value={minFloat} onChange={(event) => setMinFloat(event.target.value)} placeholder="0.00" /><span>—</span><input name="maximum-float" autoComplete="off" inputMode="decimal" aria-label={t("listings.maximumFloat")} value={maxFloat} onChange={(event) => setMaxFloat(event.target.value)} placeholder="1.00" /></fieldset>
                <fieldset><legend>{t("listings.price")}</legend><input name="minimum-price" autoComplete="off" inputMode="decimal" aria-label={t("listings.minimumPrice")} value={minPrice} onChange={(event) => setMinPrice(event.target.value)} placeholder="0" /><span>—</span><input name="maximum-price" autoComplete="off" inputMode="decimal" aria-label={t("listings.maximumPrice")} value={maxPrice} onChange={(event) => setMaxPrice(event.target.value)} placeholder="∞" /></fieldset>
                <label className={styles.inlineCheck} title={!canFilterStickers ? t("listings.filtersUnsupported") : undefined}><input name="has-stickers" type="checkbox" checked={hasStickers} disabled={!canFilterStickers && !hasStickers} onChange={(event) => setHasStickers(event.target.checked)} />{t("listings.stickers")}</label>
                <label className={styles.inlineCheck} title={!canFilterCharms ? t("listings.filtersUnsupported") : undefined}><input name="has-charm" type="checkbox" checked={hasCharm} disabled={!canFilterCharms && !hasCharm} onChange={(event) => setHasCharm(event.target.checked)} />{t("listings.charms")}</label>
                <button className={styles.primaryButton} type="button" onClick={applyFilters}>{t("common.apply")}</button>
                <button className={styles.secondaryButton} type="button" onClick={resetFilters}>{t("common.reset")}</button>
              </section>
              {listingMarkets.length === 0 && <div className={styles.emptyState}>{t("listings.noMarketplaces")}</div>}
              <div className={styles.marketplaceListingGroups}>{listingMarkets.map((marketplace, marketIndex) => {
                const query = listingQueries[marketIndex];
                const unsupportedFilters = unsupportedAttachmentFilters(appliedFilters, marketplace);
                const paintIndexUnavailable = isPaintIndexUnavailable(query?.data?.error);
                return <section className={styles.marketplaceListingGroup} key={marketplace.id} aria-labelledby={`market-listings-${marketplace.id}`}>
                  <header><div><span className={styles.marketplaceChip}>{marketplace.display_name}</span><h3 id={`market-listings-${marketplace.id}`}>{t("listings.marketHeading", { market: marketplace.display_name })}</h3></div><strong>{t("listings.count", { count: query?.data?.listings.length ?? 0 })}</strong></header>
                  {query?.data && <ListingSnapshotStatus snapshot={query.data} />}
                  {!query?.data?.source_state && query?.data?.quote_source === "wiki_market_summary" && <p className={styles.sourceNote}>{t("marketSource.referenceQuote")}</p>}
                  {unsupportedFilters.length > 0 && <MarketplaceListingState title={t("listings.filterUnsupportedTitle")} detail={t("listings.filterUnsupportedMarket", { market: marketplace.display_name, filters: unsupportedFilters.map((filter) => t(`listings.${filter}`)).join(", ") })} />}
                  {query?.isLoading && <MarketplaceListingState title={t("common.loading")} />}
                  {query?.isError && <MarketplaceListingState title={t("listings.providerError", { market: marketplace.display_name })} detail={t("listings.providerErrorHint")} onRetry={() => void query.refetch()} />}
                  {paintIndexUnavailable && <MarketplaceListingState title={t("listings.paintIndexUnavailableTitle")} detail={t("listings.paintIndexUnavailable", { market: marketplace.display_name })} />}
                  {!paintIndexUnavailable && query?.data?.error && !query.data.source_state && <MarketplaceListingState title={t("listings.providerError", { market: marketplace.display_name })} detail={t("listings.providerErrorHint")} onRetry={() => void query.refetch()} />}
                  {!query?.isLoading && !query?.isError && !query?.data?.source_state && !query?.data?.error && !query?.data?.refresh_queued && query?.data?.quote_source !== "wiki_market_summary" && unsupportedFilters.length === 0 && query?.data?.listings.length === 0 && <MarketplaceListingState title={t("listings.none")} detail={t("listings.noneOnMarket", { market: marketplace.display_name })} />}
                  {query?.data?.listings.length ? <div className={styles.listingGrid}>{query.data.listings.map((listing, index) => <ListingCard key={`${marketplace.id}-${listing.listing_id ?? listing.variant_id}-${index}`} listing={{ ...listing, marketplace_id: listing.marketplace_id ?? marketplace.id }} marketplaceName={marketplace.display_name} fallbackImage={skin.image_url} locale={locale} onClick={() => openDetail(listing, marketplace.id, query.data)} />)}</div> : null}
                  {marketplace.id === "csmoney" && quality.variants.filter((item) => !query?.data?.listings.some((listing) => listing.variant_id === item.id) && variantMatchesFilter(item, appliedFilters.variant)).map((item) => <button key={item.id} className={styles.secondaryButton} type="button" onClick={() => openVariant(item)}>{t("analytics.openVariant", { name: item.market_hash_name })}</button>)}
                </section>;
              })}</div>
            </div>
          ) : (
            <div className={styles.detailView}>
              <aside className={styles.detailAside}>
                <button className={styles.backButton} type="button" onClick={() => back(detailParams)}>← {t("analytics.backToListings")}</button>
                <span className={styles.eyebrow}>{t(selectedListing ? "analytics.selectedListing" : "analytics.selectedVariant")}</span><Dialog.Title>{selectedListing?.market_hash_name ?? selectedVariant?.market_hash_name}</Dialog.Title>
                <div className={styles.detailImage}><img src={selectedListing?.image_url ?? selectedVariant?.image_url ?? skin.image_url ?? ""} alt="" width="400" height="224" /></div>
                {selectedListing && <><strong className={styles.detailPrice}>{formatUsd(selectedListing.price_cents, locale)}</strong>
                <dl className={styles.facts}><div><dt>Float</dt><dd>{selectedListing.float_value?.toFixed(8) ?? "—"}</dd></div><div><dt>Seed</dt><dd>{selectedListing.paint_seed ?? "—"}</dd></div><div><dt>{t("analytics.market")}</dt><dd>{marketplaces.find((item) => item.id === selectedListing.marketplace_id)?.display_name ?? selectedListing.marketplace_id}</dd></div></dl>
                <AttachmentRow items={selectedListing.stickers} label={t("attachments.sticker")} locale={locale} />
                <AttachmentRow items={selectedListing.charms} label={t("attachments.charm")} locale={locale} />
                {selectedListingStale && <p className={styles.sourceNote}>{t("listings.snapshotStale")}</p>}
                <div className={styles.detailActions}>{selectedListing.item_url && <a href={selectedListing.item_url} target="_blank" rel="noreferrer">{t("common.open")} ↗</a>}{!selectedListingStale && <Link to={`/calculator?skin=${encodeURIComponent(skin.id)}&variant=${encodeURIComponent(selectedListing.variant_id ?? "")}&buy=${selectedListing.price_cents}&market=${selectedListing.marketplace_id ?? marketId}`}>{t("navigation.calculator")} →</Link>}</div></>}
                {!selectedListing && <p className={styles.sourceNote}>{t("analytics.variantOnlyNote")}</p>}
              </aside>
              <main className={styles.analyticsPane}>
                <header className={styles.analyticsHeader}><div><span>{t("analytics.title")}</span><h2>{selectedListing?.market_hash_name ?? selectedVariant?.market_hash_name}</h2></div><div className={styles.marketTabs}>{analyticsMarkets.map((item) => <button className={analyticsMarket === item.id ? styles.activeChip : ""} type="button" key={item.id} onClick={() => setAnalyticsMarket(item.id)}>{item.display_name}</button>)}</div></header>
                {selectedDetails && <ListingSnapshotStatus snapshot={selectedDetails} />}
                {selectedDetails && <DetailComponentStatus details={selectedDetails} component={detailComponentForTab(tab)} />}
                {!selectedDetails?.source_state && selectedDetails?.quote_source === "wiki_market_summary" && <p className={styles.sourceNote}>{t("marketSource.referenceQuote")}</p>}
                <nav
                  className={styles.analyticsTabs}
                  role="tablist"
                  aria-label={t("analytics.title")}
                  aria-orientation="horizontal"
                  style={{ "--active-index": activeTabIndex } as CSSProperties}
                  onKeyDown={(event) => {
                    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
                    event.preventDefault();
                    const nextIndex = event.key === "Home"
                      ? 0
                      : event.key === "End"
                        ? analyticsTabs.length - 1
                        : (activeTabIndex + (event.key === "ArrowRight" ? 1 : -1) + analyticsTabs.length) % analyticsTabs.length;
                    const nextTab = analyticsTabs[nextIndex];
                    if (!nextTab) return;
                    setTab(nextTab);
                    event.currentTarget.querySelector<HTMLButtonElement>(`#analytics-tab-${nextTab}`)?.focus();
                  }}
                >
                  <span className={styles.tabIndicator} aria-hidden="true" />
                  {analyticsTabs.map((item) => <button id={`analytics-tab-${item}`} role="tab" aria-controls={`analytics-panel-${item}`} aria-selected={tab === item} tabIndex={tab === item ? 0 : -1} className={tab === item ? styles.activeTab : ""} type="button" key={item} onClick={() => setTab(item)}>{t(item === "history" && analyticsMarket === "csmoney" ? "analytics.wikiTradePriceHistory" : `analytics.${item}`)}</button>)}
                </nav>
                {selectedDetailQuery?.isLoading && !selectedDetails && <MarketplaceListingState title={t("common.loading")} />}
                {selectedDetailQuery?.isError && <MarketplaceListingState title={t("analytics.detailError")} onRetry={() => void selectedDetailQuery.refetch()} />}
                {(selectedDetails || tab === "compare" || (analyticsMarket === "csmoney" && tab === "history")) && <div className={styles.tabContent} key={tab} id={`analytics-panel-${tab}`} role="tabpanel" aria-labelledby={`analytics-tab-${tab}`} tabIndex={0}>
                {tab === "history" && <section className={styles.analyticsSection}>
                  <div className={styles.metricGrid}><Metric label={t("analytics.minPrice")} value={formatUsd(freshListings?.overview?.price_cents, locale)} /><Metric label={t("analytics.bestBid")} value={formatUsd(selectedQuickSell?.best_price_cents, locale)} /><Metric label={t("analytics.liquidity")} value={selectedDetails && liquidityScoreIfFresh(selectedDetails) != null ? String(liquidityScoreIfFresh(selectedDetails)) + "/100" : "—"} /><Metric label={t("analytics.salesDay")} value={formatNumber(freshSales?.stats?.sales_per_day, locale)} /></div>
                  {analyticsMarket === "csmoney" && detailVariantId ? <WikiTradeHistory variantId={detailVariantId} locale={locale} /> : <>
                    <div className={styles.chartHeader}><div><h3>{t("analytics.history")}</h3><span>{t("analytics.points", { count: visibleSales.length })}</span></div><div>{(["24h", "7d", "14d", "all"] as HistoryPeriod[]).map((item) => <button className={period === item ? styles.activeChip : ""} type="button" key={item} disabled={item !== period && filterSalesByPeriod(currentSales, item).length === 0} onClick={() => setPeriod(item)}>{t(item === "all" ? "analytics.periodAll" : `analytics.period${item}`)}</button>)}</div></div>
                    {!selectedCapability?.supports_sales_history ? <div className={styles.emptyState}>{t("analytics.historyUnavailable")}</div> : currentSales.length ? <Suspense fallback={<div className={styles.emptyState}>{t("common.loading")}</div>}><SalesChart sales={visibleSales} period="all" /></Suspense> : <div className={styles.emptyState}>{t(selectedDetails?.sales_error ? "analytics.dataUnavailable" : "analytics.historyEmpty")}</div>}
                    {selectedCapability?.supports_sales_history && <><p className={styles.sourceNote}>{t("analytics.sourceNote")}</p><DataTable headers={[t("analytics.date"), t("analytics.price"), "Float"]} rows={visibleSales.slice(0, 50).map((sale) => [formatDate(sale.sold_at, locale), formatUsd(sale.price_cents, locale), sale.float_value?.toFixed(8) ?? "—"])} /></>}
                  </>}
                </section>}
                {tab === "active" && <section className={styles.analyticsSection}><div className={styles.metricGrid}><Metric label={t("analytics.minPrice")} value={formatUsd(selectedDetails?.overview?.price_cents, locale)} /><Metric label={t("listings.title")} value={String(activeListingCount(freshListings) ?? "—")} /></div><DataTable headers={[t("analytics.price"), "Float", "Seed", t("analytics.attachments")]} rows={(freshListings?.listings ?? []).map((item) => [formatUsd(item.price_cents, locale), item.float_value?.toFixed(8) ?? "—", String(item.paint_seed ?? "—"), <AttachmentPreview listing={item} compact locale={locale} />])} /></section>}
                {tab === "quick" && <section className={styles.analyticsSection}>{!selectedCapability?.supports_quick_sell ? <div className={styles.emptyState}>{t("analytics.quickUnavailable")}</div> : <><div className={styles.metricGrid}><Metric label={t("analytics.bestBid")} value={formatUsd(selectedQuickSell?.best_price_cents, locale)} /><Metric label={t("analytics.bidDepth")} value={String(selectedQuickSell?.near_bid_depth ?? "—")} /></div>{listingQuickSellQuery.isLoading && analyticsMarket === "csfloat" && <p className={styles.sourceNote}>{t("common.loading")}</p>}<DataTable headers={[t("analytics.price"), t("analytics.quantity"), t("analytics.conditions")]} rows={(selectedQuickSell?.orders ?? []).map((order) => [formatUsd(order.price_cents, locale), String(order.quantity), order.min_float == null && order.max_float == null ? "—" : `${order.min_float ?? 0}–${order.max_float ?? 1}`])} /><p className={styles.sourceNote}>{selectedQuickSell?.note}</p></>}</section>}
                {tab === "compare" && <ComparePanel marketplaces={analyticsMarkets} details={detailsByMarket} comparison={selectedComparison} selectedListing={selectedListing} fallbackImage={selectedVariant?.image_url ?? skin.image_url} selectedListingStale={selectedListingStale} listingQuickSell={listingQuickSellQuery.data} buy={compareBuy} sell={compareSell} onBuy={setCompareBuy} onSell={setCompareSell} onSwap={() => update({ compare_buy: compareSell, compare_sell: compareBuy }, true)} locale={locale} />}
                </div>}
              </main>
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function WikiTradeHistory({ variantId, locale }: { variantId: string; locale: string }) {
  const { t } = useTranslation();
  const query = useQuery({
    queryKey: ["csmoney-wiki-trade-history", variantId],
    queryFn: ({ signal }) => api.csmoneyPriceHistory(variantId, signal),
    staleTime: 60_000,
    refetchInterval: (query) => !wikiTradeHistoryFresh(query.state.data, Date.now()) ? 60_000 : 5 * 60_000,
    retry: false,
  });
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 60_000);
    const expiresAt = query.data?.latest_at ? Date.parse(query.data.latest_at) + 72 * 60 * 60 * 1000 : NaN;
    const expiryTimer = Number.isFinite(expiresAt) && expiresAt >= Date.now()
      ? window.setTimeout(() => setNow(Date.now()), expiresAt - Date.now() + 1)
      : undefined;
    return () => { window.clearInterval(timer); if (expiryTimer !== undefined) window.clearTimeout(expiryTimer); };
  }, [query.data?.latest_at]);
  const points = wikiTradeHistoryFresh(query.data, now) ? query.data?.points ?? [] : [];
  return <>
    <div className={styles.chartHeader}><div><h3>{t("analytics.wikiTradePriceHistory")}</h3><span>{t("analytics.pricePoints", { count: points.length })}</span></div></div>
    <p className={styles.sourceNote}>{t("analytics.wikiTradePriceNote")}</p>
    {query.isLoading ? <div className={styles.emptyState}>{t("common.loading")}</div>
      : query.isError || query.data?.error ? <MarketplaceListingState title={t("analytics.tradeHistoryError")} onRetry={() => void query.refetch()} />
      : points.length ? <Suspense fallback={<div className={styles.emptyState}>{t("common.loading")}</div>}><PriceHistoryChart points={points} /></Suspense>
        : <div className={styles.emptyState}>{t("analytics.wikiTradePriceUnavailable")}</div>}
    <p className={styles.sourceNote}>{t("analytics.historyUnavailable")}</p>
  </>;
}

function MarketplaceListingState({ title, detail, onRetry }: { title: string; detail?: string; onRetry?: () => void }) {
  const { t } = useTranslation();
  return <div className={styles.marketplaceState} role="status"><strong>{title}</strong>{detail && <p>{detail}</p>}{onRetry && <button type="button" onClick={onRetry}>{t("common.retry")}</button>}</div>;
}

type SourceSnapshot = Pick<ListingsResponse, "source_state" | "variant_states" | "fetched_at" | "cached" | "stale" | "is_stale" | "is_partial" | "refresh_queued" | "quote_source">;

const sourceStatusLabels: Record<MarketSourceState, string> = {
  listings_available: "marketSource.listingsAvailable",
  summary_only: "marketSource.summaryOnly",
  provider_unavailable: "marketSource.providerUnavailable",
  stale: "marketSource.stale",
  empty: "marketSource.empty",
  partial: "marketSource.partial",
};

export function sourceStatusKey(snapshot?: SourceSnapshot): string {
  if (snapshot?.source_state) return sourceStatusLabels[snapshot.source_state];
  if (!snapshot?.fetched_at) return "analytics.quoteUnavailable";
  return snapshot.cached || (snapshot.is_stale ?? snapshot.stale) ? "common.cached" : "analytics.dataFresh";
}

export function activeListingCount(details?: MarketplaceDetails) {
  if (!details) return undefined;
  if (details.source_state === "summary_only" || details.quote_source === "wiki_market_summary") return details.listings?.length ?? 0;
  return details.overview.active_listings ?? details.listings?.length;
}

export function listingSnapshotStale(snapshot?: SourceSnapshot, variantId?: string | null): boolean {
  const state = snapshot?.variant_states?.find((item) => item.variant_id === variantId);
  if (state) return state.source_state === "stale" || state.stale;
  return snapshot?.source_state === "stale" || Boolean(snapshot?.is_stale ?? snapshot?.stale);
}

export function selectedListingIsStale(listing: Listing, snapshot?: SourceSnapshot): boolean {
  return Boolean(listing.stale) || listingSnapshotStale(snapshot, listing.variant_id);
}

export function SourceStateStatus({ snapshot, fallback = false }: { snapshot?: SourceSnapshot; fallback?: boolean }) {
  const { t } = useTranslation();
  if (!snapshot?.source_state && !fallback) return null;
  return <div role="status" className={styles.snapshotStatus}>
    <strong>{t(sourceStatusKey(snapshot))}</strong>
    {!snapshot?.source_state && (snapshot?.is_stale ?? snapshot?.stale) && <span> · {t("analytics.stale")}</span>}
    {!snapshot?.source_state && snapshot?.is_partial && <span> · {t("listings.snapshotPartial")}</span>}
  </div>;
}

function ListingSnapshotStatus({ snapshot }: { snapshot: SourceSnapshot }) {
  const { t } = useTranslation();
  const labels = [
    !snapshot.source_state && (snapshot.is_stale ?? snapshot.stale) && t("listings.snapshotStale"),
    !snapshot.source_state && snapshot.is_partial && snapshot.quote_source !== "wiki_market_summary" && t("listings.snapshotPartial"),
    snapshot.refresh_queued && t("listings.snapshotQueued"),
  ].filter(Boolean);
  return <><SourceStateStatus snapshot={snapshot} />{labels.length ? <p className={styles.snapshotStatus} role="status">{labels.join(" · ")}</p> : null}</>;
}


export function detailComponentFresh(details: MarketplaceDetails, component: DetailComponentName): boolean {
  const state = details.components?.[component];
  return state ? state.status === "fresh" : details.source_state !== "stale" && details.source_state !== "provider_unavailable" && !(details.is_stale ?? details.stale);
}

export function liquidityScoreIfFresh(details: MarketplaceDetails): number | undefined {
  return detailComponentFresh(details, "sales")
    && detailComponentFresh(details, "listings")
    && detailComponentFresh(details, "buy_orders")
    ? details.stats?.liquidity_score ?? undefined : undefined;
}

export function wikiTradeHistoryFresh(history: WikiPriceHistory | undefined, now: number): boolean {
  if (!history?.latest_at || !history.points.length || history.error) return false;
  const latest = Date.parse(history.latest_at);
  return Number.isFinite(latest) && latest <= now && now - latest <= 72 * 60 * 60 * 1000;
}

function variantMatchesFilter(variant: SkinVariant, filter?: VariantKind): boolean {
  return !filter || filter === "any" || (filter === "stattrak" ? variant.stattrak : filter === "souvenir" ? variant.souvenir : !variant.stattrak && !variant.souvenir);
}

export function detailComponentForTab(tab: Tab): DetailComponentName | undefined {
  if (tab === "history") return "sales";
  if (tab === "active") return "listings";
  if (tab === "quick") return "buy_orders";
  return undefined;
}

function DetailComponentStatus({ details, component }: { details: MarketplaceDetails; component?: DetailComponentName }) {
  const { t } = useTranslation();
  if (!component) return null;
  const state = details.components?.[component];
  if (!state || state.status === "fresh") return null;
  const componentLabel = t(detailComponentLabels[component]);
  const statusLabel = t(detailStatusLabels[state.status]);
  const labels = [
    `${componentLabel}: ${statusLabel}`,
  ].filter(Boolean);
  return <p className={styles.snapshotStatus} role="status">{labels.join(" · ")}</p>;
}

function ListingCard({ listing, marketplaceName, fallbackImage, locale, onClick }: { listing: Listing; marketplaceName: string; fallbackImage?: string | null; locale: string; onClick: () => void }) {
  const { t } = useTranslation();
  return <button className={styles.listingCard} type="button" onClick={onClick}><div className={styles.listingChips}><span className={styles.listingMarketplace}>{marketplaceName}</span><span>{listing.wear_name ? wearCodes[listing.wear_name] ?? listing.wear_name : "—"}</span>{listing.stattrak && <span>StatTrak™</span>}{listing.souvenir && <span>Souvenir</span>}{Boolean(listing.charms?.length) && <span>Charm</span>}</div><img src={listing.image_url ?? fallbackImage ?? ""} alt="" width="280" height="180" loading="lazy" /><AttachmentPreview listing={listing} compact locale={locale} /><div className={styles.listingBottom}><strong>{formatUsd(listing.price_cents, locale)}</strong><span>Float {listing.float_value?.toFixed(6) ?? "—"}</span>{listing.stale && <small>{t("listings.snapshotStale")}</small>}{listing.predicted_price_cents && <small>{t("listings.estimate", { price: formatUsd(listing.predicted_price_cents, locale) })}</small>}</div></button>;
}
function AttachmentRow({ items, label, locale }: { items?: Listing["stickers"]; label: string; locale: string }) {
  const { t } = useTranslation();
  if (!items?.length) return null;
  return <div className={styles.attachmentList}>{items.map((item, index) => { const name = item.name ?? label; const tooltip = attachmentTooltip(name, item.csfloat_price_cents, locale, t("attachments.referencePrice"), t("attachments.priceUnavailable")); return <div title={tooltip} key={`${item.name}-${index}`}>{item.icon_url && <img src={item.icon_url} alt="" width="40" height="40" loading="lazy" />}<span><strong>{name}</strong><small>{item.csfloat_price_cents == null ? t("attachments.priceUnavailable") : formatUsd(item.csfloat_price_cents, locale)}</small></span></div>; })}</div>;
}
function AttachmentPreview({ listing, compact = false, locale = "en-US" }: { listing: Listing; compact?: boolean; locale?: string }) {
  const { t } = useTranslation();
  const attachments = [
    ...(listing.stickers ?? []).map((item) => ({ ...item, kind: "S" })),
    ...(listing.charms ?? []).map((item) => ({ ...item, kind: "C" })),
  ].slice(0, compact ? 5 : 8);
  if (!attachments.length) return <span className={styles.noAttachments}>—</span>;
  return <div className={styles.attachments}>{attachments.map((item, index) => { const name = item.name ?? t(item.kind === "C" ? "attachments.charm" : "attachments.sticker"); const tooltip = attachmentTooltip(name, item.csfloat_price_cents, locale, t("attachments.referencePrice"), t("attachments.priceUnavailable")); return <span className={`${styles.attachmentTooltip} ${item.kind === "C" ? styles.charmBadge : styles.stickerBadge}`} data-tooltip={tooltip} title={tooltip} key={`${item.kind}-${index}`}>{item.icon_url ? <img className={item.kind === "C" ? styles.charmIcon : undefined} src={item.icon_url} alt="" width="36" height="36" loading="lazy" /> : item.kind}</span>; })}</div>;
}
function Metric({ label, value, tone }: { label: string; value: string; tone?: "positive" | "negative" }) { return <div className={`${styles.metric} ${tone === "positive" ? styles.metricPositive : tone === "negative" ? styles.metricNegative : ""}`}><span>{label}</span><strong>{value}</strong></div>; }
function DataTable({ headers, rows }: { headers: string[]; rows: ReactNode[][] }) { return rows.length ? <div className={styles.tableWrap}><table><thead><tr>{headers.map((item) => <th key={item}>{item}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={index}>{row.map((cell, cellIndex) => <td key={cellIndex}>{cell}</td>)}</tr>)}</tbody></table></div> : <div className={styles.emptyState}>—</div>; }
function ComparePanel({ marketplaces, details, comparison, selectedListing, fallbackImage, selectedListingStale, listingQuickSell, buy, sell, onBuy, onSell, onSwap, locale }: { marketplaces: MarketplaceOption[]; details: Map<string, MarketplaceDetails>; comparison?: VariantComparison; selectedListing: Listing | null; fallbackImage?: string | null; selectedListingStale: boolean; listingQuickSell?: { best_price_cents?: number | null }; buy: string; sell: string; onBuy: (value: string) => void; onSell: (value: string) => void; onSwap: () => void; locale: string }) {
  const { t } = useTranslation();
  const [mode, setMode] = useState<Exclude<ProfitMode, "custom">>("smart");
  const [sellMode, setSellMode] = useState<SellMode>("listing");
  const buyOptions = marketplaces.filter((item) => item.capabilities.can_buy);
  const sellOptions = marketplaces.filter((item) => item.capabilities.can_sell);
  const buyConfig = marketplaces.find((item) => item.id === buy);
  const sellConfig = marketplaces.find((item) => item.id === sell);
  const listingMarket = selectedListing?.marketplace_id;
  const freshDetails = (marketplaceId: string, component: DetailComponentName) => {
    const detail = details.get(marketplaceId);
    return detail && detailComponentFresh(detail, component) ? detail : undefined;
  };
  const buyAsk = resolveMarketAsk(comparison?.markets[buy], details.get(buy), Boolean(freshDetails(buy, "listings")), selectedListing && buy === listingMarket && !selectedListingStale ? selectedListing : undefined);
  const sellAsk = resolveMarketAsk(comparison?.markets[sell], details.get(sell), Boolean(freshDetails(sell, "listings")));
  const buyQuote = buyAsk.price_cents;
  const sellBid = sell === listingMarket && sell === "csfloat" && listingQuickSell && !selectedListingStale ? listingQuickSell.best_price_cents : freshDetails(sell, "buy_orders")?.quick_sell?.best_price_cents;
  const effectiveSellMode: SellMode = mode === "quick_flip" ? "fast_buy" : sellMode;
  const sellQuote = effectiveSellMode === "fast_buy" ? sellBid : sellAsk.price_cents;
  const supportsSelectedSale = effectiveSellMode === "listing" || Boolean(sellConfig?.capabilities.supports_quick_sell);
  const calculationQuery = useQuery({
    queryKey: ["listing-comparison-result", buy, sell, buyQuote, sellQuote, mode, effectiveSellMode],
    queryFn: ({ signal }) => api.calculate({
      buy_price_cents: buyQuote!, sell_price_cents: sellQuote!, buy_marketplace: buy, sell_marketplace: sell,
      profit_mode: mode, deposit_method: buyConfig?.deposit_methods[0] ?? "crypto", withdraw_method: sellConfig?.withdraw_methods[0] ?? "crypto",
      sell_mode: effectiveSellMode, use_deposit_fee: mode === "smart" || mode === "quick_flip", use_sell_fee: mode !== "raw", use_withdraw_fee: mode !== "raw",
    }, signal),
    enabled: buyQuote != null && sellQuote != null && supportsSelectedSale,
    retry: false,
  });
  const result = calculationQuery.data;
  const sellDetail = details.get(sell);
  const comparedSale = comparison?.opportunities.find((item) => item.buy_marketplace === buy && item.sell_marketplace === sell && item.sell_mode === effectiveSellMode);
  const sellScore = sellDetail ? liquidityScoreIfFresh(sellDetail) : comparedSale?.sell_liquidity?.score;
  const riskLevel = flipRiskLevel(result?.profit_cents, effectiveSellMode, sellScore);
  const sellSource = details.get(sell);
  const buyPreview = buyAsk.listing;
  const sellPreview = effectiveSellMode === "fast_buy" ? undefined : sellAsk.listing;

  return <section className={styles.comparePanel}>
    <div className={styles.compareControls}>
      <label><span>{t("analytics.buy")}</span><select name="compare-buy-marketplace" value={buy} onChange={(event) => onBuy(event.target.value)}>{buyOptions.map((item) => <option value={item.id} key={item.id}>{item.display_name}</option>)}</select></label>
      <button type="button" className={styles.swapButton} onClick={onSwap} aria-label={t("profit.swap")}>⇄</button>
      <label><span>{t("analytics.sell")}</span><select name="compare-sell-marketplace" value={sell} onChange={(event) => onSell(event.target.value)}>{sellOptions.map((item) => <option value={item.id} key={item.id}>{item.display_name}</option>)}</select></label>
    </div>
    <div className={styles.compareOptions}>
      <label><span>{t("profit.mode")}</span><select name="compare-profit-mode" value={mode} onChange={(event) => setMode(event.target.value as Exclude<ProfitMode, "custom">)}>{(["raw", "smart", "enhanced", "quick_flip"] as const).map((item) => <option value={item} key={item}>{t(`profit.${item}`)}</option>)}</select></label>
      <label><span>{t("calculator.sellType")}</span><select name="compare-sell-mode" value={effectiveSellMode} disabled={mode === "quick_flip"} onChange={(event) => setSellMode(event.target.value as SellMode)}><option value="listing">{t("calculator.listing")}</option><option value="fast_buy" disabled={!sellConfig?.capabilities.supports_quick_sell}>{t("calculator.fastBuy")}</option></select></label>
    </div>
    <div className={styles.comparePreviews}>
      <ComparisonPreview title={t("analytics.buyPreview")} marketplace={buyConfig?.display_name ?? buy} listing={buyPreview} fallbackImage={selectedListing?.image_url ?? fallbackImage} price={buyQuote} locale={locale} />
      <ComparisonPreview title={t("analytics.sellPreview")} marketplace={sellConfig?.display_name ?? sell} listing={sellPreview} fallbackImage={selectedListing?.image_url ?? fallbackImage} price={sellQuote} locale={locale} />
    </div>
    <div className={styles.metricGrid}><Metric label={`${t("analytics.buy")} · ask`} value={formatUsd(buyQuote, locale)} /><Metric label={effectiveSellMode === "fast_buy" ? `${t("analytics.sell")} · bid` : `${t("analytics.sell")} · ask`} value={formatUsd(sellQuote, locale)} /><Metric label={t("analytics.bidDepth")} value={String(freshDetails(sell, "buy_orders")?.quick_sell?.near_bid_depth ?? "—")} /><Metric label={t("analytics.netProfit")} value={formatUsd(result?.profit_cents, locale)} tone={result ? (result.profit_cents >= 0 ? "positive" : "negative") : undefined} /><Metric label={t("analytics.roi")} value={result ? (result.effective_buy_cents === 0 ? "—" : `${result.cash_roi_percent}%`) : "—"} tone={result ? (result.profit_cents >= 0 ? "positive" : "negative") : undefined} /></div>
    <FlipRiskNotice level={riskLevel} score={sellScore} />
    <QuoteProvenance buy={buyAsk.source} sell={sellQuote == null ? null : effectiveSellMode === "fast_buy" ? "best_bid" : sellAsk.source} />
    {result?.applied_fees && <div className={styles.feeBreakdown}><Metric label={t("calculator.depositFee")} value={formatUsd(result.deposit_fee_cents, locale)} /><Metric label={t("calculator.sellFee")} value={formatUsd(result.sell_fee_cents, locale)} /><Metric label={t("calculator.withdrawFee")} value={formatUsd(result.withdraw_fee_cents, locale)} /></div>}
    {!supportsSelectedSale && <p className={styles.sourceNote}>{t("analytics.quickUnavailable")}</p>}
    {calculationQuery.isError && <p className={styles.sourceNote}>{t("calculator.serverError")}</p>}
    {effectiveSellMode === "fast_buy" && sellSource?.components?.buy_orders
      ? <DetailComponentStatus details={sellSource} component="buy_orders" />
      : effectiveSellMode === "listing" && !sellSource?.source_state && sellSource?.components?.listings
        ? <DetailComponentStatus details={sellSource} component="listings" />
        : <SourceStateStatus snapshot={sellSource} fallback />}
  </section>;
}

function ComparisonPreview({ title, marketplace, listing, fallbackImage, price, locale }: { title: string; marketplace: string; listing?: Listing; fallbackImage?: string | null; price?: number | null; locale: string }) {
  return <article className={styles.comparePreview}><div><span>{title}</span><strong>{marketplace}</strong></div><img src={listing?.image_url ?? fallbackImage ?? ""} alt="" width="288" height="192" loading="lazy" /><strong>{formatUsd(price, locale)}</strong>{listing ? <AttachmentPreview listing={listing} locale={locale} /> : <span className={styles.noAttachments}>—</span>}</article>;
}

function filterSalesByPeriod(sales: Sale[], period: HistoryPeriod) {
  const hours = period === "24h" ? 24 : period === "7d" ? 168 : period === "14d" ? 336 : null;
  const threshold = hours == null ? 0 : Date.now() - hours * 3_600_000;
  return sales.filter((sale) => Number.isFinite(sale.price_cents) && !Number.isNaN(new Date(sale.sold_at).getTime()) && new Date(sale.sold_at).getTime() >= threshold);
}

export function filtersForMarketplace(filters: ListingFilters, marketplace: MarketplaceOption): ListingFilters {
  return {
    ...filters,
    sort_by: filters.sort_by === "best_deal" && marketplace.capabilities.supports_best_deal_sort
      ? "best_deal"
      : "lowest_price",
  };
}

export function unsupportedAttachmentFilters(filters: ListingFilters, marketplace: MarketplaceOption) {
  const unsupported: Array<"stickers" | "charms"> = [];
  if (filters.has_stickers && !marketplace.capabilities.supports_stickers) unsupported.push("stickers");
  if (filters.has_charm && !marketplace.capabilities.supports_charms) unsupported.push("charms");
  return unsupported;
}

export function isPaintIndexUnavailable(error: string | null | undefined) {
  return Boolean(error && /paint(?:[\s_-]*index)|индекс[^.]*покраск/i.test(error));
}

export function attachmentTooltip(name: string, priceCents: number | null | undefined, locale: string, priceLabel: string, unavailableLabel: string) {
  return priceCents == null
    ? `${name} · ${unavailableLabel}`
    : `${name} · ${priceLabel}: ${formatUsd(priceCents, locale)}`;
}
