import * as Dialog from "@radix-ui/react-dialog";
import { useQueries, useQuery } from "@tanstack/react-query";
import { motion, useReducedMotion } from "motion/react";
import { lazy, Suspense, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { api, type Listing, type ListingFilters, type MarketplaceDetails, type MarketplaceOption, type ProfitMode, type Sale, type SellMode, type SkinDetails, type SkinQuality, type VariantComparison, type VariantKind } from "@/shared/api";
import { formatDate, formatNumber, formatUsd } from "@/shared/lib/format";
import type { HistoryPeriod } from "@/features/analytics/SalesChart";
import styles from "./market.module.css";

const wearSlugs: Record<string, ListingFilters["wear"]> = { "Factory New": "factory-new", "Minimal Wear": "minimal-wear", "Field-Tested": "field-tested", "Well-Worn": "well-worn", "Battle-Scarred": "battle-scarred" };
const SalesChart = lazy(() => import("@/features/analytics/SalesChart").then((module) => ({ default: module.SalesChart })));
const wearCodes: Record<string, string> = { "Factory New": "FN", "Minimal Wear": "MW", "Field-Tested": "FT", "Well-Worn": "WW", "Battle-Scarred": "BS" };
const ALL_MARKETS = "all";
type Tab = "history" | "active" | "quick" | "compare";

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
  const listMarkets = marketplaces.filter((item) => item.capabilities.supports_listings);
  const [marketId, setMarketId] = useState(listMarkets[0]?.id ?? "csfloat");
  const [sort, setSort] = useState<ListingFilters["sort_by"]>("lowest_price");
  const [variant, setVariant] = useState<VariantKind>("any");
  const [minFloat, setMinFloat] = useState("");
  const [maxFloat, setMaxFloat] = useState("");
  const [minPrice, setMinPrice] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [hasStickers, setHasStickers] = useState(false);
  const [hasCharm, setHasCharm] = useState(false);
  const [appliedFilters, setAppliedFilters] = useState<ListingFilters>({ wear: wearSlugs[quality.wear], sort_by: "lowest_price", variant: "any", has_stickers: false, has_charm: false, limit: 30 });
  const [selectedListing, setSelectedListing] = useState<Listing | null>(null);
  const [tab, setTab] = useState<Tab>("history");
  const [analyticsMarket, setAnalyticsMarket] = useState(marketId);
  const [period, setPeriod] = useState<HistoryPeriod>("7d");
  const [compareBuy, setCompareBuy] = useState(listMarkets[0]?.id ?? "csfloat");
  const [compareSell, setCompareSell] = useState(listMarkets[1]?.id ?? listMarkets[0]?.id ?? "csgomarket");
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
    };
  }) });
  const visibleListingCount = listingQueries.reduce((count, query) => count + (query.data?.listings.length ?? 0), 0);

  const analyticsMarkets = listMarkets;
  const detailQueries = useQueries({ queries: analyticsMarkets.map((item) => ({
    queryKey: ["variant-details", selectedListing?.variant_id, item.id],
    queryFn: ({ signal }: { signal: AbortSignal }) => api.variantDetails(selectedListing!.variant_id!, item.id, signal),
    enabled: Boolean(selectedListing?.variant_id && (item.id === analyticsMarket || tab === "compare")), staleTime: 600_000,
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
  const selectedComparison = selectedListing?.variant_id ? comparison.get(selectedListing.variant_id) : undefined;

  function resetFilters() { setVariant("any"); setMinFloat(""); setMaxFloat(""); setMinPrice(""); setMaxPrice(""); setHasStickers(false); setHasCharm(false); setAppliedFilters({ wear: wearSlugs[quality.wear], sort_by: "lowest_price", variant: "any", has_stickers: false, has_charm: false, limit: 30 }); }
  function applyFilters() { setAppliedFilters(listingFilters); }
  function openDetail(listing: Listing, marketplaceId: string) { setSelectedListing({ ...listing, marketplace_id: listing.marketplace_id ?? marketplaceId }); setAnalyticsMarket(listing.marketplace_id ?? marketplaceId); setTab("history"); }
  function switchMarket(next: string) { setMarketId(next); if (next !== ALL_MARKETS) setAnalyticsMarket(next); }
  const currentSales = selectedDetails?.sales ?? [];
  const visibleSales = useMemo(() => filterSalesByPeriod(currentSales, period), [currentSales, period]);
  const selectedQuickSell = analyticsMarket === "csfloat" && selectedListing?.marketplace_id === "csfloat" && listingQuickSellQuery.data
    ? { ...selectedDetails?.quick_sell, ...listingQuickSellQuery.data }
    : selectedDetails?.quick_sell;

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className={styles.dialogOverlay} />
        <Dialog.Content className={styles.dialogContent} aria-describedby={undefined}>
          <Dialog.Close className={styles.dialogClose} aria-label={t("common.close")}>×</Dialog.Close>
          {!selectedListing ? (
            <div className={styles.browserView}>
              <header className={styles.dialogHeader}><div><span>{t("listings.title")}</span><Dialog.Title>{skin.name}</Dialog.Title><p>{marketId === ALL_MARKETS ? t("listings.subtitleAll", { wear: quality.wear }) : t("listings.subtitle", { wear: quality.wear, market: market?.display_name ?? marketId })}</p></div><strong>{t("listings.count", { count: visibleListingCount })}</strong></header>
              <section className={styles.listingToolbar}>
                <label><span>{t("listings.marketplace")}</span><select value={marketId} onChange={(event) => switchMarket(event.target.value)}><option value={ALL_MARKETS}>{t("listings.allMarketplaces")}</option>{listMarkets.map((item) => <option key={item.id} value={item.id}>{item.display_name}</option>)}</select></label>
                <label><span>{t("listings.sort")}</span><select value={sort} onChange={(event) => setSort(event.target.value as ListingFilters["sort_by"])}><option value="lowest_price">{t("listings.lowest")}</option><option disabled={!canSortBestDeal && sort !== "best_deal"} value="best_deal">{t("listings.bestDeal")}</option></select></label>
                <label><span>{t("listings.variant")}</span><select value={variant} onChange={(event) => setVariant(event.target.value as VariantKind)}><option value="any">{t("catalog.any")}</option><option value="normal">{t("listings.normal")}</option><option value="stattrak">{t("listings.stattrak")}</option><option value="souvenir">{t("listings.souvenir")}</option></select></label>
                <fieldset><legend>{t("listings.float")}</legend><input aria-label="Minimum float" value={minFloat} onChange={(event) => setMinFloat(event.target.value)} placeholder="0.00" /><span>—</span><input aria-label="Maximum float" value={maxFloat} onChange={(event) => setMaxFloat(event.target.value)} placeholder="1.00" /></fieldset>
                <fieldset><legend>{t("listings.price")}</legend><input aria-label="Minimum price" value={minPrice} onChange={(event) => setMinPrice(event.target.value)} placeholder="0" /><span>—</span><input aria-label="Maximum price" value={maxPrice} onChange={(event) => setMaxPrice(event.target.value)} placeholder="∞" /></fieldset>
                <label className={styles.inlineCheck} title={!canFilterStickers ? t("listings.filtersUnsupported") : undefined}><input type="checkbox" checked={hasStickers} disabled={!canFilterStickers && !hasStickers} onChange={(event) => setHasStickers(event.target.checked)} />{t("listings.stickers")}</label>
                <label className={styles.inlineCheck} title={!canFilterCharms ? t("listings.filtersUnsupported") : undefined}><input type="checkbox" checked={hasCharm} disabled={!canFilterCharms && !hasCharm} onChange={(event) => setHasCharm(event.target.checked)} />{t("listings.charms")}</label>
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
                  {unsupportedFilters.length > 0 && <MarketplaceListingState title={t("listings.filterUnsupportedTitle")} detail={t("listings.filterUnsupportedMarket", { market: marketplace.display_name, filters: unsupportedFilters.map((filter) => t(`listings.${filter}`)).join(", ") })} />}
                  {query?.isLoading && <MarketplaceListingState title={t("common.loading")} />}
                  {query?.isError && <MarketplaceListingState title={t("listings.providerError", { market: marketplace.display_name })} detail={t("listings.providerErrorHint")} onRetry={() => void query.refetch()} />}
                  {paintIndexUnavailable && <MarketplaceListingState title={t("listings.paintIndexUnavailableTitle")} detail={t("listings.paintIndexUnavailable", { market: marketplace.display_name })} />}
                  {!paintIndexUnavailable && query?.data?.error && <MarketplaceListingState title={t("listings.providerError", { market: marketplace.display_name })} detail={t("listings.providerErrorHint")} onRetry={() => void query.refetch()} />}
                  {!query?.isLoading && !query?.isError && !query?.data?.error && unsupportedFilters.length === 0 && query?.data?.listings.length === 0 && <MarketplaceListingState title={t("listings.none")} detail={t("listings.noneOnMarket", { market: marketplace.display_name })} />}
                  {query?.data?.listings.length ? <div className={styles.listingGrid}>{query.data.listings.map((listing, index) => <ListingCard key={`${marketplace.id}-${listing.listing_id ?? listing.variant_id}-${index}`} listing={{ ...listing, marketplace_id: listing.marketplace_id ?? marketplace.id }} marketplaceName={marketplace.display_name} fallbackImage={skin.image_url} locale={locale} onClick={() => openDetail(listing, marketplace.id)} />)}</div> : null}
                </section>;
              })}</div>
            </div>
          ) : (
            <div className={styles.detailView}>
              <aside className={styles.detailAside}>
                <button className={styles.backButton} type="button" onClick={() => setSelectedListing(null)}>← {t("analytics.backToListings")}</button>
                <span className={styles.eyebrow}>{t("analytics.selectedListing")}</span><Dialog.Title>{selectedListing.market_hash_name}</Dialog.Title>
                <div className={styles.detailImage}><img src={selectedListing.image_url ?? skin.image_url ?? ""} alt="" /></div>
                <strong className={styles.detailPrice}>{formatUsd(selectedListing.price_cents, locale)}</strong>
                <dl className={styles.facts}><div><dt>Float</dt><dd>{selectedListing.float_value?.toFixed(8) ?? "—"}</dd></div><div><dt>Seed</dt><dd>{selectedListing.paint_seed ?? "—"}</dd></div><div><dt>{t("analytics.market")}</dt><dd>{marketplaces.find((item) => item.id === selectedListing.marketplace_id)?.display_name ?? selectedListing.marketplace_id}</dd></div></dl>
                <AttachmentRow items={selectedListing.stickers} label={t("attachments.sticker")} locale={locale} />
                <AttachmentRow items={selectedListing.charms} label={t("attachments.charm")} locale={locale} />
                <div className={styles.detailActions}>{selectedListing.item_url && <a href={selectedListing.item_url} target="_blank" rel="noreferrer">{t("common.open")} ↗</a>}<Link to={`/calculator?skin=${encodeURIComponent(skin.id)}&variant=${encodeURIComponent(selectedListing.variant_id ?? "")}&buy=${selectedListing.price_cents}&market=${selectedListing.marketplace_id ?? marketId}`}>{t("navigation.calculator")} →</Link></div>
              </aside>
              <main className={styles.analyticsPane}>
                <header className={styles.analyticsHeader}><div><span>{t("analytics.title")}</span><h2>{selectedListing.market_hash_name}</h2></div><div className={styles.marketTabs}>{analyticsMarkets.map((item) => <button className={analyticsMarket === item.id ? styles.activeChip : ""} type="button" key={item.id} onClick={() => setAnalyticsMarket(item.id)}>{item.display_name}</button>)}</div></header>
                <nav className={styles.analyticsTabs} role="tablist">{(["history", "active", "quick", "compare"] as Tab[]).map((item) => <button role="tab" aria-selected={tab === item} className={tab === item ? styles.activeTab : ""} type="button" key={item} onClick={() => setTab(item)}>{t(`analytics.${item}`)}</button>)}</nav>
                {detailQueries.some((item) => item.isLoading) && !selectedDetails && <div className={styles.emptyState}>{t("common.loading")}</div>}
                {tab === "history" && <section className={styles.analyticsSection}>
                  <div className={styles.metricGrid}><Metric label={t("analytics.minPrice")} value={formatUsd(selectedDetails?.overview?.price_cents, locale)} /><Metric label={t("analytics.bestBid")} value={formatUsd(selectedQuickSell?.best_price_cents, locale)} /><Metric label={t("analytics.liquidity")} value={selectedDetails?.stats?.liquidity_score == null ? "—" : `${selectedDetails.stats.liquidity_score}%`} /><Metric label={t("analytics.salesDay")} value={formatNumber(selectedDetails?.stats?.sales_per_day, locale)} /></div>
                  <div className={styles.chartHeader}><div><h3>{t("analytics.history")}</h3><span>{t("analytics.points", { count: visibleSales.length })}</span></div><div>{(["24h", "7d", "14d", "all"] as HistoryPeriod[]).map((item) => <button className={period === item ? styles.activeChip : ""} type="button" key={item} disabled={item !== period && filterSalesByPeriod(currentSales, item).length === 0} onClick={() => setPeriod(item)}>{t(item === "all" ? "analytics.periodAll" : `analytics.period${item}`)}</button>)}</div></div>
                  {!selectedCapability?.supports_sales_history ? <div className={styles.emptyState}>{t("analytics.historyUnavailable")}</div> : currentSales.length ? <Suspense fallback={<div className={styles.emptyState}>{t("common.loading")}</div>}><SalesChart sales={visibleSales} period="all" /></Suspense> : <div className={styles.emptyState}>{selectedDetails?.sales_error ?? t("analytics.historyEmpty")}</div>}
                  <p className={styles.sourceNote}>{t("analytics.sourceNote")}</p>
                  <DataTable headers={[t("analytics.date"), t("analytics.price"), "Float"]} rows={visibleSales.slice(0, 50).map((sale) => [formatDate(sale.sold_at, locale), formatUsd(sale.price_cents, locale), sale.float_value?.toFixed(8) ?? "—"])} />
                </section>}
                {tab === "active" && <section className={styles.analyticsSection}><div className={styles.metricGrid}><Metric label={t("analytics.minPrice")} value={formatUsd(selectedDetails?.overview?.price_cents, locale)} /><Metric label={t("listings.title")} value={String(selectedDetails?.overview?.active_listings ?? selectedDetails?.listings?.length ?? "—")} /></div><DataTable headers={[t("analytics.price"), "Float", "Seed", t("analytics.attachments")]} rows={(selectedDetails?.listings ?? []).map((item) => [formatUsd(item.price_cents, locale), item.float_value?.toFixed(8) ?? "—", String(item.paint_seed ?? "—"), <AttachmentPreview listing={item} compact locale={locale} />])} /></section>}
                {tab === "quick" && <section className={styles.analyticsSection}><div className={styles.metricGrid}><Metric label={t("analytics.bestBid")} value={formatUsd(selectedQuickSell?.best_price_cents, locale)} /><Metric label={t("analytics.bidDepth")} value={String(selectedQuickSell?.near_bid_depth ?? "—")} /></div>{listingQuickSellQuery.isLoading && analyticsMarket === "csfloat" && <p className={styles.sourceNote}>{t("common.loading")}</p>}<DataTable headers={[t("analytics.price"), t("analytics.quantity"), t("analytics.conditions")]} rows={(selectedQuickSell?.orders ?? []).map((order) => [formatUsd(order.price_cents, locale), String(order.quantity), order.min_float == null && order.max_float == null ? "—" : `${order.min_float ?? 0}–${order.max_float ?? 1}`])} /><p className={styles.sourceNote}>{selectedQuickSell?.note}</p></section>}
                {tab === "compare" && <ComparePanel marketplaces={analyticsMarkets} details={detailsByMarket} comparison={selectedComparison} selectedListing={selectedListing} listingQuickSell={listingQuickSellQuery.data} buy={compareBuy} sell={compareSell} onBuy={setCompareBuy} onSell={setCompareSell} onSwap={() => { setCompareBuy(compareSell); setCompareSell(compareBuy); }} locale={locale} />}
              </main>
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function MarketplaceListingState({ title, detail, onRetry }: { title: string; detail?: string; onRetry?: () => void }) {
  const { t } = useTranslation();
  return <div className={styles.marketplaceState} role="status"><strong>{title}</strong>{detail && <p>{detail}</p>}{onRetry && <button type="button" onClick={onRetry}>{t("common.retry")}</button>}</div>;
}

function ListingCard({ listing, marketplaceName, fallbackImage, locale, onClick }: { listing: Listing; marketplaceName: string; fallbackImage?: string | null; locale: string; onClick: () => void }) {
  const { t } = useTranslation();
  const reduceMotion = useReducedMotion();
  return <motion.button whileHover={reduceMotion ? undefined : { y: -3 }} className={styles.listingCard} type="button" onClick={onClick}><div className={styles.listingChips}><span className={styles.listingMarketplace}>{marketplaceName}</span><span>{listing.wear_name ? wearCodes[listing.wear_name] ?? listing.wear_name : "—"}</span>{listing.stattrak && <span>StatTrak™</span>}{listing.souvenir && <span>Souvenir</span>}{Boolean(listing.charms?.length) && <span>Charm</span>}</div><img src={listing.image_url ?? fallbackImage ?? ""} alt="" /><AttachmentPreview listing={listing} compact locale={locale} /><div className={styles.listingBottom}><strong>{formatUsd(listing.price_cents, locale)}</strong><span>Float {listing.float_value?.toFixed(6) ?? "—"}</span>{listing.predicted_price_cents && <small>{t("listings.estimate", { price: formatUsd(listing.predicted_price_cents, locale) })}</small>}</div></motion.button>;
}
function AttachmentRow({ items, label, locale }: { items?: Listing["stickers"]; label: string; locale: string }) {
  const { t } = useTranslation();
  if (!items?.length) return null;
  return <div className={styles.attachmentList}>{items.map((item, index) => { const name = item.name ?? label; const tooltip = attachmentTooltip(name, item.csfloat_price_cents, locale, t("attachments.referencePrice"), t("attachments.priceUnavailable")); return <div title={tooltip} key={`${item.name}-${index}`}>{item.icon_url && <img src={item.icon_url} alt="" />}<span><strong>{name}</strong><small>{item.csfloat_price_cents == null ? t("attachments.priceUnavailable") : formatUsd(item.csfloat_price_cents, locale)}</small></span></div>; })}</div>;
}
function AttachmentPreview({ listing, compact = false, locale = "en-US" }: { listing: Listing; compact?: boolean; locale?: string }) {
  const { t } = useTranslation();
  const attachments = [
    ...(listing.stickers ?? []).map((item) => ({ ...item, kind: "S" })),
    ...(listing.charms ?? []).map((item) => ({ ...item, kind: "C" })),
  ].slice(0, compact ? 5 : 8);
  if (!attachments.length) return <span className={styles.noAttachments}>—</span>;
  return <div className={styles.attachments}>{attachments.map((item, index) => { const name = item.name ?? t(item.kind === "C" ? "attachments.charm" : "attachments.sticker"); const tooltip = attachmentTooltip(name, item.csfloat_price_cents, locale, t("attachments.referencePrice"), t("attachments.priceUnavailable")); return <span className={`${styles.attachmentTooltip} ${item.kind === "C" ? styles.charmBadge : styles.stickerBadge}`} data-tooltip={tooltip} title={tooltip} key={`${item.kind}-${index}`}>{item.icon_url ? <img className={item.kind === "C" ? styles.charmIcon : undefined} src={item.icon_url} alt="" /> : item.kind}</span>; })}</div>;
}
function Metric({ label, value, tone }: { label: string; value: string; tone?: "positive" | "negative" }) { return <div className={`${styles.metric} ${tone === "positive" ? styles.metricPositive : tone === "negative" ? styles.metricNegative : ""}`}><span>{label}</span><strong>{value}</strong></div>; }
function DataTable({ headers, rows }: { headers: string[]; rows: ReactNode[][] }) { return rows.length ? <div className={styles.tableWrap}><table><thead><tr>{headers.map((item) => <th key={item}>{item}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={index}>{row.map((cell, cellIndex) => <td key={cellIndex}>{cell}</td>)}</tr>)}</tbody></table></div> : <div className={styles.emptyState}>—</div>; }
function ComparePanel({ marketplaces, details, comparison, selectedListing, listingQuickSell, buy, sell, onBuy, onSell, onSwap, locale }: { marketplaces: MarketplaceOption[]; details: Map<string, MarketplaceDetails>; comparison?: VariantComparison; selectedListing: Listing; listingQuickSell?: { best_price_cents?: number | null }; buy: string; sell: string; onBuy: (value: string) => void; onSell: (value: string) => void; onSwap: () => void; locale: string }) {
  const { t } = useTranslation();
  const [mode, setMode] = useState<Exclude<ProfitMode, "custom">>("smart");
  const [sellMode, setSellMode] = useState<SellMode>("listing");
  const buyOptions = marketplaces.filter((item) => item.capabilities.can_buy);
  const sellOptions = marketplaces.filter((item) => item.capabilities.can_sell);
  const buyConfig = marketplaces.find((item) => item.id === buy);
  const sellConfig = marketplaces.find((item) => item.id === sell);
  const listingMarket = selectedListing.marketplace_id;
  const buyQuote = buy === listingMarket ? selectedListing.price_cents : comparison?.markets[buy]?.price_cents ?? details.get(buy)?.overview.price_cents;
  const sellAsk = comparison?.markets[sell]?.price_cents ?? details.get(sell)?.overview.price_cents;
  const sellBid = sell === listingMarket && sell === "csfloat" && listingQuickSell ? listingQuickSell.best_price_cents : details.get(sell)?.quick_sell?.best_price_cents;
  const effectiveSellMode: SellMode = mode === "quick_flip" ? "fast_buy" : sellMode;
  const sellQuote = effectiveSellMode === "fast_buy" ? sellBid : sellAsk;
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
  const sellSource = details.get(sell);
  const buyPreview = buy === listingMarket ? selectedListing : details.get(buy)?.listings?.[0];
  const sellPreview = sell === listingMarket ? selectedListing : details.get(sell)?.listings?.[0];
  const status = sellSource?.fetched_at ? `${sellSource.cached ? t("common.cached") : t("common.live")} · ${t("analytics.updated", { date: formatDate(sellSource.fetched_at, locale) })}${sellSource.stale ? ` · ${t("analytics.stale")}` : ""}` : t("analytics.quoteUnavailable");

  return <section className={styles.comparePanel}>
    <div className={styles.compareControls}>
      <label><span>{t("analytics.buy")}</span><select value={buy} onChange={(event) => onBuy(event.target.value)}>{buyOptions.map((item) => <option value={item.id} key={item.id}>{item.display_name}</option>)}</select></label>
      <button type="button" className={styles.swapButton} onClick={onSwap} aria-label={t("profit.swap")}>⇄</button>
      <label><span>{t("analytics.sell")}</span><select value={sell} onChange={(event) => onSell(event.target.value)}>{sellOptions.map((item) => <option value={item.id} key={item.id}>{item.display_name}</option>)}</select></label>
    </div>
    <div className={styles.compareOptions}>
      <label><span>{t("profit.mode")}</span><select value={mode} onChange={(event) => setMode(event.target.value as Exclude<ProfitMode, "custom">)}>{(["raw", "smart", "enhanced", "quick_flip"] as const).map((item) => <option value={item} key={item}>{t(`profit.${item}`)}</option>)}</select></label>
      <label><span>{t("calculator.sellType")}</span><select value={effectiveSellMode} disabled={mode === "quick_flip"} onChange={(event) => setSellMode(event.target.value as SellMode)}><option value="listing">{t("calculator.listing")}</option><option value="fast_buy" disabled={!sellConfig?.capabilities.supports_quick_sell}>{t("calculator.fastBuy")}</option></select></label>
    </div>
    <div className={styles.comparePreviews}>
      <ComparisonPreview title={t("analytics.buyPreview")} marketplace={buyConfig?.display_name ?? buy} listing={buyPreview} fallbackImage={selectedListing.image_url} price={buyQuote} locale={locale} />
      <ComparisonPreview title={t("analytics.sellPreview")} marketplace={sellConfig?.display_name ?? sell} listing={sellPreview} fallbackImage={selectedListing.image_url} price={sellQuote} locale={locale} />
    </div>
    <div className={styles.metricGrid}><Metric label={`${t("analytics.buy")} · ask`} value={formatUsd(buyQuote, locale)} /><Metric label={effectiveSellMode === "fast_buy" ? `${t("analytics.sell")} · bid` : `${t("analytics.sell")} · ask`} value={formatUsd(sellQuote, locale)} /><Metric label={t("analytics.bidDepth")} value={String(details.get(sell)?.quick_sell?.near_bid_depth ?? "—")} /><Metric label={t("analytics.netProfit")} value={formatUsd(result?.profit_cents, locale)} tone={result ? (result.profit_cents >= 0 ? "positive" : "negative") : undefined} /><Metric label={t("analytics.roi")} value={result ? (result.effective_buy_cents === 0 ? "—" : `${result.cash_roi_percent}%`) : "—"} tone={result ? (result.profit_cents >= 0 ? "positive" : "negative") : undefined} /></div>
    {result?.applied_fees && <div className={styles.feeBreakdown}><Metric label={t("calculator.depositFee")} value={formatUsd(result.deposit_fee_cents, locale)} /><Metric label={t("calculator.sellFee")} value={formatUsd(result.sell_fee_cents, locale)} /><Metric label={t("calculator.withdrawFee")} value={formatUsd(result.withdraw_fee_cents, locale)} /></div>}
    {!supportsSelectedSale && <p className={styles.sourceNote}>{t("analytics.quickUnavailable")}</p>}
    {calculationQuery.isError && <p className={styles.sourceNote}>{t("calculator.serverError")}</p>}
    <p className={styles.sourceNote}>{status}</p>
  </section>;
}

function ComparisonPreview({ title, marketplace, listing, fallbackImage, price, locale }: { title: string; marketplace: string; listing?: Listing; fallbackImage?: string | null; price?: number | null; locale: string }) {
  return <article className={styles.comparePreview}><div><span>{title}</span><strong>{marketplace}</strong></div><img src={listing?.image_url ?? fallbackImage ?? ""} alt="" /><strong>{formatUsd(price, locale)}</strong>{listing ? <AttachmentPreview listing={listing} locale={locale} /> : <span className={styles.noAttachments}>—</span>}</article>;
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
