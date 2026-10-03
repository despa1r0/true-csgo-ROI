import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { api, type CatalogueSearchResult } from "@/shared/api";
import { useBrowseHistory, wearParams } from "@/shared/lib/browseHistory";
import { formatUsd } from "@/shared/lib/format";
import { ProfitSettings, type ProfitSettingsValue } from "./ProfitSettings";
import { ListingDialog } from "./ListingDialog";
import { FlipRiskNotice } from "./FlipRiskNotice";
import { CsMoneyTextSearch } from "./CsMoneyTextSearch";
import { shouldOfferCsMoneySearch } from "./shouldOfferCsMoneySearch";
import { csMoneyRefreshInterval, mergeCsMoneyPrices } from "./csMoneyComparison";
import { selectQualityCardMarketData } from "./qualityCard";
import { QuoteProvenance, opportunityQuoteSources } from "./quoteSource";
import styles from "./market.module.css";

const wearCodes: Record<string, string> = { "Factory New": "FN", "Minimal Wear": "MW", "Field-Tested": "FT", "Well-Worn": "WW", "Battle-Scarred": "BS" };

export function CatalogPage() {
  const { i18n, t } = useTranslation();
  const { params: searchParams, update, back } = useBrowseHistory();
  const [query, setQuery] = useState(() => searchParams.get("q") ?? "");
  const debouncedQuery = searchParams.get("q") ?? "";
  const selectedSkinId = searchParams.get("skin");
  const filters = { item_type: searchParams.get("type") ?? "", weapon: searchParams.get("weapon") ?? "", rarity: searchParams.get("rarity") ?? "", collection: searchParams.get("collection") ?? "" };
  function setFilters(next: typeof filters) {
    update({ type: next.item_type, weapon: next.weapon, rarity: next.rarity, collection: next.collection,
      skin: null, ...wearParams }, true);
  }
  const [suggestionsOpen, setSuggestionsOpen] = useState(true);
  const profit: ProfitSettingsValue = {
    mode: (["raw", "smart", "enhanced", "quick_flip"] as const).find((mode) => mode === searchParams.get("profit_mode")) ?? "smart",
    buyMarketplace: searchParams.get("buy_market") ?? "all", sellMarketplace: searchParams.get("sell_market") ?? "auto",
    depositMethod: searchParams.get("deposit") === "card" ? "card" : "crypto",
    withdrawMethod: searchParams.get("withdraw") === "card" ? "card" : "crypto", useDepositFee: searchParams.get("deposit_fee") !== "0",
  };
  function setProfit(next: ProfitSettingsValue) {
    update({ profit_mode: next.mode, buy_market: next.buyMarketplace, sell_market: next.sellMarketplace,
      deposit: next.depositMethod, withdraw: next.withdrawMethod, deposit_fee: next.useDepositFee ? "1" : "0" }, true);
  }

  useEffect(() => {
    if (query.trim() === debouncedQuery) return;
    const timer = window.setTimeout(() => update({ q: query.trim(), skin: null, ...wearParams }, true), 280);
    return () => window.clearTimeout(timer);
  }, [query, debouncedQuery, searchParams]);

  useEffect(() => {
    setQuery(debouncedQuery);
  }, [debouncedQuery]);
  useEffect(() => { if (!selectedSkinId) setSuggestionsOpen(true); }, [selectedSkinId]);

  const marketplaceQuery = useQuery({ queryKey: ["marketplaces"], queryFn: ({ signal }) => api.marketplaces(signal) });
  const filterQuery = useQuery({ queryKey: ["catalog-filters"], queryFn: ({ signal }) => api.catalogFilters(signal) });
  const searchEnabled = debouncedQuery.length >= 2 || Object.values(filters).some(Boolean);
  const searchQuery = useQuery({
    queryKey: ["skin-search", debouncedQuery, filters],
    queryFn: ({ signal }) => api.searchSkins({ q: debouncedQuery, ...filters, limit: 12 }, signal),
    enabled: searchEnabled,
    staleTime: 300_000,
  });
  const showCsMoneySearch = shouldOfferCsMoneySearch({ query, searchedQuery: debouncedQuery,
    hasFilters: Object.values(filters).some(Boolean), searchComplete: searchQuery.isSuccess,
    matches: searchQuery.data?.length ?? 0, selected: Boolean(selectedSkinId) });
  const skinQuery = useQuery({
    queryKey: ["skin", selectedSkinId],
    queryFn: ({ signal }) => api.skinDetails(selectedSkinId!, signal),
    enabled: Boolean(selectedSkinId),
    staleTime: 300_000,
  });
  const comparisonQuery = useQuery({
    queryKey: ["market-comparison", selectedSkinId, profit.mode, profit.depositMethod, profit.withdrawMethod, profit.useDepositFee],
    queryFn: ({ signal }) => api.marketComparison(selectedSkinId!, { profit_mode: profit.mode, deposit_method: profit.depositMethod, withdraw_method: profit.withdrawMethod, use_deposit_fee: profit.useDepositFee }, signal),
    enabled: Boolean(skinQuery.data?.qualities.some((quality) => quality.variants.length)),
    staleTime: 300_000,
  });
  const cachedComparisonQuery = useQuery({
    queryKey: ["cached-comparison", selectedSkinId, profit.mode, profit.depositMethod, profit.withdrawMethod, profit.useDepositFee],
    queryFn: ({ signal }) => api.marketComparison(selectedSkinId!, { profit_mode: profit.mode, deposit_method: profit.depositMethod,
      withdraw_method: profit.withdrawMethod, use_deposit_fee: profit.useDepositFee, cached_only: true }, signal),
    enabled: Boolean(skinQuery.data?.qualities.some((quality) => quality.variants.length)),
    staleTime: 15_000,
  });

  const csMoneyPriceQuery = useQuery({
    queryKey: ["csmoney-prices", selectedSkinId],
    queryFn: ({ signal }) => api.csMoneyPrices(selectedSkinId!, signal),
    enabled: Boolean(skinQuery.data?.qualities.some((quality) => quality.variants.length)),
    staleTime: 15_000,
    refetchInterval: (query) => csMoneyRefreshInterval(query.state.data),
  });
  const comparisonByVariant = useMemo(() => mergeCsMoneyPrices(comparisonQuery.data ?? cachedComparisonQuery.data, csMoneyPriceQuery.data), [comparisonQuery.data, cachedComparisonQuery.data, csMoneyPriceQuery.data]);
  const marketplaces = marketplaceQuery.data ?? [];
  const locale = i18n.resolvedLanguage === "ru" ? "ru-RU" : "en-US";
  const selectedQuality = skinQuery.data?.qualities.find((quality) => quality.wear === searchParams.get("wear"));

  function chooseSkin(result: CatalogueSearchResult) {
    update({ q: result.name, skin: result.id, ...wearParams });
    setQuery(result.name);
    setSuggestionsOpen(false);
  }

  return (
    <div className={styles.page}>
      <section className={styles.hero}>
        <div><span className={styles.eyebrow}>{t("catalog.eyebrow")}</span><h1>{t("catalog.title")}</h1><p>{t("catalog.subtitle")}</p></div>
        <div className={styles.heroSignal}><span>{t("common.live")}</span><strong>{marketplaces.filter((item) => item.capabilities.supports_listings).length || "—"}</strong><small>{t("catalog.marketFeeds")}</small></div>
      </section>

      <section className={styles.searchPanel}>
        <div className={styles.searchBox}>
          <label htmlFor="skin-search">{t("catalog.search")}</label>
          <input id="skin-search" name="skin-search" type="search" autoComplete="off" aria-autocomplete="list" aria-controls="skin-search-suggestions" aria-expanded={suggestionsOpen && searchEnabled && query !== skinQuery.data?.name} value={query} placeholder={t("catalog.searchPlaceholder")} onFocus={() => setSuggestionsOpen(true)} onKeyDown={(event) => { if (event.key === "Escape") setSuggestionsOpen(false); }} onChange={(event) => { setSuggestionsOpen(true); setQuery(event.target.value); }} />
          <svg className={styles.searchIcon} aria-hidden="true" viewBox="0 0 24 24"><circle cx="11" cy="11" r="6" /><path d="m16 16 4 4" /></svg>
          {suggestionsOpen && searchEnabled && query !== skinQuery.data?.name && (
            <div className={styles.suggestions} id="skin-search-suggestions" aria-live="polite" aria-busy={searchQuery.isLoading}>
              <div className={styles.suggestionHeader}><span>{t("catalog.search")}</span><strong>{searchQuery.isLoading ? t("common.loading") : t("catalog.results", { count: searchQuery.data?.length ?? 0 })}</strong></div>
              {searchQuery.isLoading && Array.from({ length: 3 }, (_, index) => <div className={styles.suggestionSkeleton} key={index} />)}
              {searchQuery.data?.map((result) => (
                <button className={styles.suggestionCard} type="button" key={result.id} onClick={() => chooseSkin(result)}>
                  <span className={styles.suggestionVisual}><img src={result.image_url ?? ""} alt="" width="128" height="88" loading="lazy" /></span>
                  <span className={styles.suggestionCopy}><strong>{result.name}</strong><small>{result.weapon_name ?? t(`catalogTypes.${result.item_type}`, { defaultValue: result.item_type })}</small></span>
                  <span className={styles.suggestionMeta}>{t("catalog.variants", { count: result.variant_count })}<i style={{ background: result.rarity_color ?? undefined }} /></span>
                </button>
              ))}
              {searchQuery.data?.length === 0 && <p>{t("catalog.results", { count: 0 })}</p>}
            </div>
          )}
        </div>
        <div className={styles.catalogFilters}>
          <label><span>{t("catalog.itemType")}</span><select name="item-type" value={filters.item_type} onChange={(event) => { setSuggestionsOpen(true); setFilters({ ...filters, item_type: event.target.value, weapon: event.target.value && event.target.value !== "skin" ? "" : filters.weapon }); }}><option value="">{t("catalog.any")}</option>{filterQuery.data?.item_types.map((item) => <option key={item.id} value={item.id}>{t(`catalogTypes.${item.id}`, { defaultValue: item.name })} · {item.count}</option>)}</select></label>
          <label><span>{t("catalog.weapon")}</span><select name="weapon" value={filters.weapon} onChange={(event) => { setSuggestionsOpen(true); setFilters({ ...filters, weapon: event.target.value }); }}><option value="">{t("catalog.any")}</option>{filterQuery.data?.weapons.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.count}</option>)}</select></label>
          <label><span>{t("catalog.rarity")}</span><select name="rarity" value={filters.rarity} onChange={(event) => { setSuggestionsOpen(true); setFilters({ ...filters, rarity: event.target.value }); }}><option value="">{t("catalog.any")}</option>{filterQuery.data?.rarities.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.count}</option>)}</select></label>
          <label><span>{t("catalog.collection")}</span><select name="collection" value={filters.collection} onChange={(event) => { setSuggestionsOpen(true); setFilters({ ...filters, collection: event.target.value }); }}><option value="">{t("catalog.any")}</option>{filterQuery.data?.collections.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.count}</option>)}</select></label>
        </div>
        <p className={styles.searchHint}>{searchEnabled && searchQuery.data ? t("catalog.results", { count: searchQuery.data.length }) : t("catalog.searchHint")}</p>
      </section>

      {showCsMoneySearch && <CsMoneyTextSearch key={debouncedQuery} query={debouncedQuery} />}

      <ProfitSettings value={profit} marketplaces={marketplaces} onChange={setProfit} />

      {skinQuery.data && (
        <section className={styles.skinSection}>
          <button type="button" className={styles.backButton} onClick={() => back({ skin: null, ...wearParams })}>← {t("common.back")}</button>
          <header className={styles.skinHeader}>
            <img src={skinQuery.data.image_url ?? ""} alt="" width="224" height="176" />
            <div><span>{t("catalog.selected")}</span><h2>{skinQuery.data.name}</h2><p>{[skinQuery.data.weapon_name ?? t(`catalogTypes.${skinQuery.data.item_type}`, { defaultValue: skinQuery.data.item_type }), skinQuery.data.rarity_name, skinQuery.data.collections?.map((item) => item.name).join(" · ")].filter(Boolean).join(" · ")}</p></div>
            <div className={styles.dataState} role="status">{comparisonQuery.isFetching ? comparisonByVariant.size ? t("listings.snapshotQueued") : t("common.loading") : comparisonQuery.isError ? t("catalog.marketError") : t("common.live")}</div>
          </header>
          <div className={styles.sectionHeading}><div><span>{t("catalog.conditions")}</span><h3>{t("catalog.conditionsHint")}</h3></div></div>
          <div className={styles.qualityGrid}>
            {skinQuery.data.qualities.map((quality) => {
              const variants = quality.variants.map((variant) => comparisonByVariant.get(variant.id)).filter((item) => item != null);
              const { quotes, cheapest, best } = selectQualityCardMarketData(variants, profit.buyMarketplace, profit.sellMarketplace);
              const wearLabel = quality.wear === "Standard" ? t("catalog.standard") : quality.wear;
              return <button type="button" className={styles.qualityCard} key={quality.wear} onClick={() => update({ wear: quality.wear })}>
                <div className={styles.qualityTop}><strong>{wearCodes[quality.wear] ?? "1"}</strong><span>{wearLabel}</span></div>
                <img src={quality.variants[0]?.image_url ?? skinQuery.data.image_url ?? ""} alt="" width="320" height="200" loading="lazy" />
                <div className={styles.qualityPrice}><strong>{cheapest ? t("catalog.marketFrom", { price: formatUsd(cheapest.quote.price_cents, locale) }) : t("catalog.noPrice")}</strong><span>{cheapest ? marketplaces.find((item) => item.id === cheapest.marketplaceId)?.display_name ?? cheapest.marketplaceId : "—"}</span></div>
                {cheapest?.quote.source === "wiki_market_summary" && <span className={styles.sourceNote}>{t("marketSource.summaryNote")}</span>}
                <div className={styles.marketMini}>{marketplaces.filter((market) => market.capabilities.supports_listings).map((market) => { const marketQuote = quotes.find((item) => item.marketplaceId === market.id && item.variant.variant_id === cheapest?.variant.variant_id)?.quote; return <span key={market.id}><small>{market.display_name}</small><b>{formatUsd(marketQuote?.price_cents, locale)}</b></span>; })}</div>
                {best && <div className={best.profit_cents >= 0 ? styles.positive : styles.negative}>{best.buy_marketplace} → {best.sell_marketplace} · {best.profit_cents > 0 ? "+" : ""}{formatUsd(best.profit_cents, locale)} · {best.cash_roi_percent}%</div>}
                {best && <QuoteProvenance {...opportunityQuoteSources(best, variants.find((item) => item.variant_id === best.variant_id) ?? cheapest?.variant)} />}
                {best && <FlipRiskNotice level={best.risk_level} score={best.sell_liquidity?.score} cashRoiPercent={best.cash_roi_percent} sellMarketplace={best.sell_marketplace} dataStatus={best.sell_liquidity?.data_status} compact />}
              </button>;
            })}
            {skinQuery.data.qualities.length === 0 && <p className={styles.emptyState}>{t("catalog.marketDataUnavailable")}</p>}
          </div>
        </section>
      )}

      {skinQuery.data && selectedQuality && <ListingDialog key={`${skinQuery.data.id}:${selectedQuality.wear}`} skin={skinQuery.data} quality={selectedQuality} marketplaces={marketplaces} comparison={comparisonByVariant} open onOpenChange={(open) => !open && back(wearParams)} />}
    </div>
  );
}
