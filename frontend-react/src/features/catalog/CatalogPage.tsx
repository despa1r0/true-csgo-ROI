import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { api, type CatalogueSearchResult, type SkinQuality } from "@/shared/api";
import { formatUsd } from "@/shared/lib/format";
import { ProfitSettings, type ProfitSettingsValue } from "./ProfitSettings";
import { ListingDialog } from "./ListingDialog";
import { selectQualityCardMarketData } from "./qualityCard";
import styles from "./market.module.css";

const wearCodes: Record<string, string> = { "Factory New": "FN", "Minimal Wear": "MW", "Field-Tested": "FT", "Well-Worn": "WW", "Battle-Scarred": "BS" };

export function CatalogPage() {
  const { i18n, t } = useTranslation();
  const reduceMotion = useReducedMotion();
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [filters, setFilters] = useState({ item_type: "", weapon: "", rarity: "", collection: "" });
  const [selectedResult, setSelectedResult] = useState<CatalogueSearchResult | null>(null);
  const [selectedQuality, setSelectedQuality] = useState<SkinQuality | null>(null);
  const [profit, setProfit] = useState<ProfitSettingsValue>({ mode: "smart", buyMarketplace: "all", sellMarketplace: "auto", depositMethod: "crypto", withdrawMethod: "crypto", useDepositFee: true });

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query.trim()), 280);
    return () => window.clearTimeout(timer);
  }, [query]);

  const marketplaceQuery = useQuery({ queryKey: ["marketplaces"], queryFn: ({ signal }) => api.marketplaces(signal) });
  const filterQuery = useQuery({ queryKey: ["catalog-filters"], queryFn: ({ signal }) => api.catalogFilters(signal) });
  const searchEnabled = debouncedQuery.length >= 2 || Object.values(filters).some(Boolean);
  const searchQuery = useQuery({
    queryKey: ["skin-search", debouncedQuery, filters],
    queryFn: ({ signal }) => api.searchSkins({ q: debouncedQuery, ...filters, limit: 12 }, signal),
    enabled: searchEnabled,
    staleTime: 300_000,
  });
  const skinQuery = useQuery({
    queryKey: ["skin", selectedResult?.id],
    queryFn: ({ signal }) => api.skinDetails(selectedResult!.id, signal),
    enabled: Boolean(selectedResult),
    staleTime: 300_000,
  });
  const comparisonQuery = useQuery({
    queryKey: ["market-comparison", selectedResult?.id, profit.mode, profit.depositMethod, profit.withdrawMethod, profit.useDepositFee],
    queryFn: ({ signal }) => api.marketComparison(selectedResult!.id, { profit_mode: profit.mode, deposit_method: profit.depositMethod, withdraw_method: profit.withdrawMethod, use_deposit_fee: profit.useDepositFee }, signal),
    enabled: Boolean(skinQuery.data?.qualities.some((quality) => quality.variants.length)),
    staleTime: 300_000,
  });

  const comparisonByVariant = useMemo(() => new Map((comparisonQuery.data?.variants ?? []).map((item) => [item.variant_id, item])), [comparisonQuery.data]);
  const marketplaces = marketplaceQuery.data ?? [];
  const locale = i18n.resolvedLanguage === "ru" ? "ru-RU" : "en-US";

  function chooseSkin(result: CatalogueSearchResult) {
    setSelectedResult(result);
    setQuery(result.name);
    setSelectedQuality(null);
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
          <input id="skin-search" type="search" autoComplete="off" value={query} placeholder={t("catalog.searchPlaceholder")} onChange={(event) => setQuery(event.target.value)} onFocus={() => selectedResult && query !== selectedResult.name && setSelectedResult(null)} />
          <span className={styles.searchIcon}>⌕</span>
          <AnimatePresence>
            {searchEnabled && query !== selectedResult?.name && (
              <motion.div className={styles.suggestions} initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}>
                {searchQuery.isLoading && <p>{t("common.loading")}</p>}
                {searchQuery.data?.map((result) => <button type="button" key={result.id} onClick={() => chooseSkin(result)}><img src={result.image_url ?? ""} alt="" /><span><strong>{result.name}</strong><small>{result.weapon_name ?? t(`catalogTypes.${result.item_type}`, { defaultValue: result.item_type })} · {t("catalog.variants", { count: result.variant_count })}</small></span><i style={{ background: result.rarity_color ?? undefined }} /></button>)}
                {searchQuery.data?.length === 0 && <p>{t("catalog.results", { count: 0 })}</p>}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
        <div className={styles.catalogFilters}>
          <label><span>{t("catalog.itemType")}</span><select value={filters.item_type} onChange={(event) => setFilters({ ...filters, item_type: event.target.value, weapon: event.target.value && event.target.value !== "skin" ? "" : filters.weapon })}><option value="">{t("catalog.any")}</option>{filterQuery.data?.item_types.map((item) => <option key={item.id} value={item.id}>{t(`catalogTypes.${item.id}`, { defaultValue: item.name })} · {item.count}</option>)}</select></label>
          <label><span>{t("catalog.weapon")}</span><select value={filters.weapon} onChange={(event) => setFilters({ ...filters, weapon: event.target.value })}><option value="">{t("catalog.any")}</option>{filterQuery.data?.weapons.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.count}</option>)}</select></label>
          <label><span>{t("catalog.rarity")}</span><select value={filters.rarity} onChange={(event) => setFilters({ ...filters, rarity: event.target.value })}><option value="">{t("catalog.any")}</option>{filterQuery.data?.rarities.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.count}</option>)}</select></label>
          <label><span>{t("catalog.collection")}</span><select value={filters.collection} onChange={(event) => setFilters({ ...filters, collection: event.target.value })}><option value="">{t("catalog.any")}</option>{filterQuery.data?.collections.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.count}</option>)}</select></label>
        </div>
        <p className={styles.searchHint}>{searchEnabled && searchQuery.data ? t("catalog.results", { count: searchQuery.data.length }) : t("catalog.searchHint")}</p>
      </section>

      <ProfitSettings value={profit} marketplaces={marketplaces} onChange={setProfit} />

      {skinQuery.data && (
        <motion.section className={styles.skinSection} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
          <header className={styles.skinHeader}>
            <img src={skinQuery.data.image_url ?? ""} alt="" />
            <div><span>{t("catalog.selected")}</span><h2>{skinQuery.data.name}</h2><p>{[skinQuery.data.weapon_name ?? t(`catalogTypes.${skinQuery.data.item_type}`, { defaultValue: skinQuery.data.item_type }), skinQuery.data.rarity_name, skinQuery.data.collections?.map((item) => item.name).join(" · ")].filter(Boolean).join(" · ")}</p></div>
            <div className={styles.dataState}>{comparisonQuery.isFetching ? t("common.loading") : comparisonQuery.isError ? t("catalog.marketError") : t("common.live")}</div>
          </header>
          <div className={styles.sectionHeading}><div><span>{t("catalog.conditions")}</span><h3>{t("catalog.conditionsHint")}</h3></div></div>
          <div className={styles.qualityGrid}>
            {skinQuery.data.qualities.map((quality) => {
              const variants = quality.variants.map((variant) => comparisonByVariant.get(variant.id)).filter((item) => item != null);
              const { quotes, cheapest, best } = selectQualityCardMarketData(variants, profit.buyMarketplace, profit.sellMarketplace);
              const wearLabel = quality.wear === "Standard" ? t("catalog.standard") : quality.wear;
              return <motion.button whileHover={reduceMotion ? undefined : { y: -4 }} type="button" className={styles.qualityCard} key={quality.wear} onClick={() => setSelectedQuality(quality)}>
                <div className={styles.qualityTop}><strong>{wearCodes[quality.wear] ?? "1"}</strong><span>{wearLabel}</span></div>
                <img src={quality.variants[0]?.image_url ?? skinQuery.data.image_url ?? ""} alt="" />
                <div className={styles.qualityPrice}><strong>{cheapest ? t("catalog.marketFrom", { price: formatUsd(cheapest.quote.price_cents, locale) }) : t("catalog.noPrice")}</strong><span>{cheapest ? marketplaces.find((item) => item.id === cheapest.marketplaceId)?.display_name ?? cheapest.marketplaceId : "—"}</span></div>
                <div className={styles.marketMini}>{marketplaces.filter((market) => market.capabilities.supports_listings).map((market) => { const marketQuote = quotes.find((item) => item.marketplaceId === market.id && item.variant.variant_id === cheapest?.variant.variant_id)?.quote; return <span key={market.id}><small>{market.display_name}</small><b>{formatUsd(marketQuote?.price_cents, locale)}</b></span>; })}</div>
                {best && <div className={best.profit_cents >= 0 ? styles.positive : styles.negative}>{best.buy_marketplace} → {best.sell_marketplace} · {best.profit_cents > 0 ? "+" : ""}{formatUsd(best.profit_cents, locale)} · {best.cash_roi_percent}%</div>}
              </motion.button>;
            })}
            {skinQuery.data.qualities.length === 0 && <p className={styles.emptyState}>{t("catalog.marketDataUnavailable")}</p>}
          </div>
        </motion.section>
      )}

      {skinQuery.data && selectedQuality && <ListingDialog skin={skinQuery.data} quality={selectedQuality} marketplaces={marketplaces} comparison={comparisonByVariant} open onOpenChange={(open) => !open && setSelectedQuality(null)} />}
    </div>
  );
}
