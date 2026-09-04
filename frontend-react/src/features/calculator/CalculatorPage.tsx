import { useMutation, useQuery } from "@tanstack/react-query";
import { motion } from "motion/react";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";

import { api, type CalculationRequest, type CatalogueSearchResult, type PaymentMethod, type ProfitMode, type SellMode } from "@/shared/api";
import { feeLabel, formatUsd, parseMoneyToCents } from "@/shared/lib/format";
import styles from "./calculator.module.css";

type FeeFlags = { deposit: boolean; sell: boolean; withdraw: boolean };
const presetFlags: Record<Exclude<ProfitMode, "custom">, FeeFlags> = {
  raw: { deposit: false, sell: false, withdraw: false },
  smart: { deposit: true, sell: true, withdraw: true },
  enhanced: { deposit: false, sell: true, withdraw: true },
  quick_flip: { deposit: true, sell: true, withdraw: true },
};

export function CalculatorPage() {
  const { i18n, t } = useTranslation();
  const [searchParams] = useSearchParams();
  const [buyPrice, setBuyPrice] = useState(() => searchParams.get("buy") ? String(Number(searchParams.get("buy")) / 100) : "100.00");
  const [sellPrice, setSellPrice] = useState("120.00");
  const [buyMarket, setBuyMarket] = useState(searchParams.get("market") ?? "csfloat");
  const [sellMarket, setSellMarket] = useState("csgomarket");
  const [depositMethod, setDepositMethod] = useState<PaymentMethod>("crypto");
  const [withdrawMethod, setWithdrawMethod] = useState<PaymentMethod>("crypto");
  const [mode, setMode] = useState<ProfitMode>("smart");
  const [sellMode, setSellMode] = useState<SellMode>("listing");
  const [fees, setFees] = useState<FeeFlags>(presetFlags.smart);
  const [skinSearch, setSkinSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [skinId, setSkinId] = useState<string | null>(searchParams.get("skin"));
  const [variantId, setVariantId] = useState<string | null>(searchParams.get("variant"));
  const [referenceAtSubmit, setReferenceAtSubmit] = useState<number | null>(null);
  const locale = i18n.resolvedLanguage === "ru" ? "ru-RU" : "en-US";

  useEffect(() => { const timer = window.setTimeout(() => setDebouncedSearch(skinSearch.trim()), 280); return () => window.clearTimeout(timer); }, [skinSearch]);
  const marketplacesQuery = useQuery({ queryKey: ["marketplaces"], queryFn: ({ signal }) => api.marketplaces(signal) });
  const skinSearchQuery = useQuery({ queryKey: ["calculator-search", debouncedSearch], queryFn: ({ signal }) => api.searchSkins({ q: debouncedSearch, limit: 8 }, signal), enabled: debouncedSearch.length >= 2 });
  const skinQuery = useQuery({ queryKey: ["skin", skinId], queryFn: ({ signal }) => api.skinDetails(skinId!, signal), enabled: Boolean(skinId) });
  const comparisonQuery = useQuery({ queryKey: ["calculator-comparison", skinId], queryFn: ({ signal }) => api.marketComparison(skinId!, { profit_mode: "raw", deposit_method: "crypto", withdraw_method: "crypto", use_deposit_fee: false }, signal), enabled: Boolean(skinId) });
  const selectedVariant = useMemo(() => {
    if (!comparisonQuery.data?.variants.length) return undefined;
    return comparisonQuery.data.variants.find((item) => item.variant_id === variantId) ?? comparisonQuery.data.variants[0];
  }, [comparisonQuery.data, variantId]);
  useEffect(() => { if (selectedVariant && !variantId) setVariantId(selectedVariant.variant_id); }, [selectedVariant, variantId]);
  const sellDetailsQuery = useQuery({ queryKey: ["calculator-detail", selectedVariant?.variant_id, sellMarket], queryFn: ({ signal }) => api.variantDetails(selectedVariant!.variant_id, sellMarket, signal), enabled: Boolean(selectedVariant?.variant_id && sellMode === "fast_buy") });

  const marketplaces = marketplacesQuery.data ?? [];
  const buyOptions = marketplaces.filter((item) => item.capabilities.can_buy);
  const sellOptions = marketplaces.filter((item) => item.capabilities.can_sell);
  const buyConfig = marketplaces.find((item) => item.id === buyMarket);
  const sellConfig = marketplaces.find((item) => item.id === sellMarket);
  const eligibleSellOptions = mode === "quick_flip" || sellMode === "fast_buy" ? sellOptions.filter((item) => item.capabilities.supports_quick_sell) : sellOptions;
  const buyReference = selectedVariant?.markets[buyMarket]?.price_cents;
  const sellReference = sellMode === "fast_buy" ? sellDetailsQuery.data?.quick_sell?.best_price_cents : selectedVariant?.markets[sellMarket]?.price_cents;
  const buyCents = parseMoneyToCents(buyPrice);
  const sellCents = parseMoneyToCents(sellPrice);
  const calculationRequest = (purchasePriceCents: number): CalculationRequest => ({ buy_price_cents: purchasePriceCents, sell_price_cents: sellCents!, buy_marketplace: buyMarket, sell_marketplace: sellMarket, profit_mode: mode, deposit_method: depositMethod, withdraw_method: withdrawMethod, sell_mode: sellMode, use_deposit_fee: fees.deposit, use_sell_fee: fees.sell, use_withdraw_fee: fees.withdraw });
  const calculation = useMutation({ mutationFn: (request: CalculationRequest) => api.calculate(request) });
  const referenceCalculation = useQuery({
    queryKey: ["calculator-reference-result", referenceAtSubmit, calculation.variables],
    queryFn: ({ signal }) => api.calculate({ ...calculation.variables!, buy_price_cents: referenceAtSubmit! }, signal),
    enabled: Boolean(calculation.data && calculation.variables && referenceAtSubmit != null),
  });

  useEffect(() => {
    if (!marketplaces.length) return;
    if (!buyOptions.some((item) => item.id === buyMarket)) setBuyMarket(buyOptions[0]?.id ?? "");
    if (!sellOptions.some((item) => item.id === sellMarket)) setSellMarket(sellOptions.find((item) => item.id !== buyMarket)?.id ?? sellOptions[0]?.id ?? "");
  }, [buyMarket, buyOptions, marketplaces.length, sellMarket, sellOptions]);
  useEffect(() => {
    if (buyConfig && !buyConfig.deposit_methods.includes(depositMethod)) setDepositMethod(buyConfig.deposit_methods[0] ?? "crypto");
  }, [buyConfig, depositMethod]);
  useEffect(() => {
    if (sellConfig && !sellConfig.withdraw_methods.includes(withdrawMethod)) setWithdrawMethod(sellConfig.withdraw_methods[0] ?? "crypto");
    if ((mode === "quick_flip" || sellMode === "fast_buy") && sellConfig && !sellConfig.capabilities.supports_quick_sell) setSellMarket(eligibleSellOptions[0]?.id ?? "");
  }, [eligibleSellOptions, mode, sellConfig, sellMode, withdrawMethod]);

  function selectSkin(result: CatalogueSearchResult) { setSkinId(result.id); setVariantId(null); setSkinSearch(result.name); }
  function setPreset(next: ProfitMode) { setMode(next); if (next !== "custom") { setFees(presetFlags[next]); setSellMode(next === "quick_flip" ? "fast_buy" : "listing"); } }
  function toggleFee(key: keyof FeeFlags) { if (!(mode === "quick_flip" && key === "deposit")) setMode("custom"); setFees((current) => ({ ...current, [key]: !current[key] })); }
  function submit(event: React.FormEvent) { event.preventDefault(); if (buyCents != null && sellCents != null && buyMarket && sellMarket) { setReferenceAtSubmit(buyReference ?? null); calculation.mutate(calculationRequest(buyCents)); } }
  function useReference(type: "buy" | "sell") { const cents = type === "buy" ? buyReference : sellReference; if (cents != null) (type === "buy" ? setBuyPrice : setSellPrice)((cents / 100).toFixed(2)); }
  function swap() { const oldBuy = buyMarket; setBuyMarket(sellMarket); setSellMarket(oldBuy); }
  const savings = buyReference != null && buyCents != null ? buyReference - buyCents : null;
  const savingsPercent = savings != null && buyReference ? savings / buyReference * 100 : null;

  return <div className={styles.page}>
    <header className={styles.hero}><span>{t("calculator.eyebrow")}</span><h1>{t("calculator.title")}</h1><p>{t("calculator.subtitle")}</p></header>
    <section className={styles.skinReference}>
      <div className={styles.searchWrap}><label htmlFor="calculator-skin-search">{t("calculator.optionalSkin")}</label><input id="calculator-skin-search" type="search" value={skinSearch} onChange={(event) => setSkinSearch(event.target.value)} placeholder={t("calculator.skinPlaceholder")} />{debouncedSearch.length >= 2 && skinSearch !== skinQuery.data?.name && <div className={styles.suggestions}>{skinSearchQuery.data?.map((item) => <button type="button" key={item.id} onClick={() => selectSkin(item)}><img src={item.image_url ?? ""} alt="" /><span><strong>{item.name}</strong><small>{item.weapon_name}</small></span></button>)}</div>}</div>
      {skinQuery.data ? <div className={styles.selectedSkin}><img src={skinQuery.data.image_url ?? ""} alt="" /><div><span>{t("calculator.marketReference")}</span><strong>{skinQuery.data.name}</strong><select aria-label={t("calculator.variant")} value={selectedVariant?.variant_id ?? ""} onChange={(event) => setVariantId(event.target.value)}>{comparisonQuery.data?.variants.map((item) => <option value={item.variant_id} key={item.variant_id}>{item.market_hash_name}</option>)}</select></div><button type="button" onClick={() => { setSkinId(null); setVariantId(null); setSkinSearch(""); }}>{t("calculator.clearSkin")}</button></div> : <p className={styles.referenceHint}>{t("calculator.noReference")}</p>}
    </section>

    <form className={styles.calculatorGrid} onSubmit={submit}>
      <section className={styles.formPanel}>
        <div className={styles.priceGrid}>
          <label><span>{t("calculator.buyPrice")}, USD</span><input inputMode="decimal" value={buyPrice} onChange={(event) => setBuyPrice(event.target.value)} aria-invalid={buyCents == null} /><small>{buyReference == null ? t("calculator.manual") : `${t("calculator.marketReference")}: ${formatUsd(buyReference, locale)}`}</small>{buyReference != null && <button type="button" onClick={() => useReference("buy")}>{t("calculator.useQuote", { price: formatUsd(buyReference, locale) })}</button>}</label>
          <div className={styles.direction}>→</div>
          <label><span>{t("calculator.sellPrice")}, USD</span><input inputMode="decimal" value={sellPrice} onChange={(event) => setSellPrice(event.target.value)} aria-invalid={sellCents == null} /><small>{sellReference == null ? t("calculator.manual") : `${t("calculator.marketReference")}: ${formatUsd(sellReference, locale)}`}</small>{sellReference != null && <button type="button" onClick={() => useReference("sell")}>{t("calculator.useQuote", { price: formatUsd(sellReference, locale) })}</button>}</label>
        </div>
        {(buyCents == null || sellCents == null) && <p className={styles.error}>{t("calculator.invalidMoney")}</p>}
        {savings != null && savings > 0 && <p className={styles.savings}>{t("calculator.savings", { amount: formatUsd(savings, locale), percent: savingsPercent?.toFixed(2) })}</p>}
        <div className={styles.marketGrid}>
          <label><span>{t("calculator.buyMarket")}</span><select value={buyMarket} onChange={(event) => setBuyMarket(event.target.value)}>{buyOptions.map((item) => <option key={item.id} value={item.id}>{item.display_name}</option>)}</select></label>
          <button className={styles.swap} type="button" onClick={swap} aria-label={t("profit.swap")}>⇄</button>
          <label><span>{t("calculator.sellMarket")}</span><select value={sellMarket} onChange={(event) => setSellMarket(event.target.value)}>{eligibleSellOptions.map((item) => <option key={item.id} value={item.id}>{item.display_name}</option>)}</select></label>
        </div>
        <div className={styles.optionsGrid}>
          <label><span>{t("profit.mode")}</span><select value={mode} onChange={(event) => setPreset(event.target.value as ProfitMode)}>{(["raw", "smart", "enhanced", "quick_flip", "custom"] as ProfitMode[]).map((item) => <option value={item} key={item}>{t(item === "custom" ? "common.custom" : `profit.${item}`)}</option>)}</select></label>
          <label><span>{t("profit.deposit")}</span><select value={depositMethod} onChange={(event) => setDepositMethod(event.target.value as PaymentMethod)}>{(buyConfig?.deposit_methods ?? ["crypto"]).map((item) => <option value={item} key={item}>{t(`profit.${item}`)}</option>)}</select></label>
          <label><span>{t("profit.withdraw")}</span><select value={withdrawMethod} onChange={(event) => setWithdrawMethod(event.target.value as PaymentMethod)}>{(sellConfig?.withdraw_methods ?? ["crypto"]).map((item) => <option value={item} key={item}>{t(`profit.${item}`)}</option>)}</select></label>
          <label><span>{t("calculator.sellType")}</span><select value={sellMode} onChange={(event) => setSellMode(event.target.value as SellMode)}><option value="listing">{t("calculator.listing")}</option><option value="fast_buy" disabled={!sellConfig?.capabilities.supports_quick_sell}>{t("calculator.fastBuy")}</option></select></label>
        </div>
        <fieldset className={styles.fees}><legend>{t("calculator.fees")}</legend><p>{t("calculator.feeLocked")}</p>
          <FeeToggle checked={fees.deposit} disabled={mode !== "custom" && mode !== "quick_flip"} onChange={() => toggleFee("deposit")} title={t("calculator.depositFee")} rule={buyConfig?.fees.deposit[depositMethod]} />
          <FeeToggle checked={fees.sell} disabled={mode !== "custom"} onChange={() => toggleFee("sell")} title={t("calculator.sellFee")} rule={sellConfig?.fees.sell} />
          <FeeToggle checked={fees.withdraw} disabled={mode !== "custom"} onChange={() => toggleFee("withdraw")} title={t("calculator.withdrawFee")} rule={sellConfig?.fees.withdraw[withdrawMethod]} />
        </fieldset>
        <button className={styles.submit} type="submit" disabled={buyCents == null || sellCents == null || calculation.isPending}>{calculation.isPending ? t("common.loading") : t("calculator.calculate")}</button>
        {calculation.isError && <p className={styles.error}>{calculation.error.message || t("calculator.serverError")}</p>}
      </section>

      <section className={styles.resultPanel} aria-live="polite">
        <header><span>{t("calculator.result")}</span>{calculation.data && <strong className={calculation.data.profit_cents > 0 ? styles.resultPositive : calculation.data.profit_cents < 0 ? styles.resultNegative : ""}>{t(calculation.data.profit_cents > 0 ? "calculator.positive" : calculation.data.profit_cents < 0 ? "calculator.negative" : "calculator.neutral")}</strong>}</header>
        {calculation.data ? <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className={styles.resultBody}>
          <div className={styles.heroResult}><span>{t("calculator.netProfit")}</span><strong className={calculation.data.profit_cents >= 0 ? styles.resultPositive : styles.resultNegative}>{calculation.data.profit_cents > 0 ? "+" : ""}{formatUsd(calculation.data.profit_cents, locale)}</strong><small>{t("calculator.cashRoi")} · {calculation.data.effective_buy_cents === 0 ? "—" : `${calculation.data.cash_roi_percent}%`}</small></div>
          <ResultRow label={t("calculator.effectiveBuy")} value={formatUsd(calculation.data.effective_buy_cents, locale)} /><ResultRow label={t("calculator.depositFee")} value={formatUsd(calculation.data.deposit_fee_cents, locale)} />
          <ResultRow label={t("calculator.effectivePayout")} value={formatUsd(calculation.data.effective_payout_cents, locale)} /><ResultRow label={t("calculator.sellFee")} value={formatUsd(calculation.data.sell_fee_cents, locale)} /><ResultRow label={t("calculator.withdrawFee")} value={formatUsd(calculation.data.withdraw_fee_cents, locale)} />
          <div className={styles.roiGrid}><ResultMetric label={t("calculator.grossProfit")} value={formatUsd(calculation.data.gross_profit_cents, locale)} note={`${t("calculator.grossRoi")} · ${calculation.data.buy_price_cents === 0 ? "—" : `${calculation.data.gross_roi_percent}%`}`} /><ResultMetric label={t("calculator.marketProfit")} value={formatUsd(calculation.data.market_profit_cents, locale)} note={`${t("calculator.marketRoi")} · ${calculation.data.buy_price_cents === 0 ? "—" : `${calculation.data.market_roi_percent}%`}`} /><ResultMetric label={t("calculator.breakEven")} value={formatUsd(calculation.data.break_even_sell_price_cents, locale)} /></div>
          {referenceAtSubmit != null && <div className={styles.baseline}>
            <strong>{t("calculator.comparisonTitle")}</strong>
            {referenceCalculation.isPending ? <small>{t("common.loading")}</small> : referenceCalculation.data ? <div className={styles.baselineGrid}>
              <ResultMetric label={t("calculator.actualBuyResult")} value={formatUsd(calculation.data.profit_cents, locale)} note={calculation.data.effective_buy_cents === 0 ? `${t("calculator.cashRoi")} · —` : `${t("calculator.cashRoi")} · ${calculation.data.cash_roi_percent}%`} />
              <ResultMetric label={t("calculator.referenceBuyResult")} value={formatUsd(referenceCalculation.data.profit_cents, locale)} note={referenceCalculation.data.effective_buy_cents === 0 ? `${t("calculator.cashRoi")} · —` : `${t("calculator.cashRoi")} · ${referenceCalculation.data.cash_roi_percent}%`} />
              <ResultMetric label={t("calculator.extraProfit")} value={formatUsd(calculation.data.profit_cents - referenceCalculation.data.profit_cents, locale)} note={calculation.data.effective_buy_cents === 0 || referenceCalculation.data.effective_buy_cents === 0 ? `${t("calculator.roiDelta")} · —` : `${t("calculator.roiDelta")} · ${(calculation.data.cash_roi_percent - referenceCalculation.data.cash_roi_percent).toFixed(2)} p.p.`} />
            </div> : <small>{t("calculator.referenceError")}</small>}
          </div>}
        </motion.div> : <div className={styles.resultPlaceholder}><span>ROI</span><p>{t("calculator.subtitle")}</p></div>}
      </section>
    </form>
  </div>;
}

function FeeToggle({ checked, disabled, onChange, title, rule }: { checked: boolean; disabled: boolean; onChange: () => void; title: string; rule?: { percent: number; fixed_cents: number } | null }) { return <label><input type="checkbox" checked={checked} disabled={disabled} onChange={onChange} /><span>{title}</span><strong>{feeLabel(rule)}</strong></label>; }
function ResultRow({ label, value }: { label: string; value: string }) { return <div className={styles.resultRow}><span>{label}</span><strong>{value}</strong></div>; }
function ResultMetric({ label, value, note }: { label: string; value: string; note?: string }) { return <div><span>{label}</span><strong>{value}</strong>{note && <small>{note}</small>}</div>; }
