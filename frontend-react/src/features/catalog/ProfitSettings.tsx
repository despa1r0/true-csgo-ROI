import type { MarketplaceOption, PaymentMethod, ProfitMode } from "@/shared/api";
import { useTranslation } from "react-i18next";
import styles from "./market.module.css";

export type ProfitSettingsValue = {
  mode: Exclude<ProfitMode, "custom">;
  buyMarketplace: string;
  sellMarketplace: string;
  depositMethod: PaymentMethod;
  withdrawMethod: PaymentMethod;
  useDepositFee: boolean;
};

type Props = {
  value: ProfitSettingsValue;
  marketplaces: MarketplaceOption[];
  onChange: (next: ProfitSettingsValue) => void;
};

const modes: Array<ProfitSettingsValue["mode"]> = ["raw", "smart", "enhanced", "quick_flip"];

export function ProfitSettings({ value, marketplaces, onChange }: Props) {
  const { t } = useTranslation();
  const enabledMarkets = marketplaces.filter((market) => market.capabilities.supports_listings);
  const patch = (next: Partial<ProfitSettingsValue>) => onChange({ ...value, ...next });
  const automatic = value.buyMarketplace === "all";
  const selectedBuy = marketplaces.find((market) => market.id === value.buyMarketplace);
  const selectedSell = marketplaces.find((market) => market.id === value.sellMarketplace);
  const commonMethods = (kind: "deposit_methods" | "withdraw_methods") => (["crypto", "card"] as PaymentMethod[]).filter((method) => enabledMarkets.every((market) => market[kind].includes(method)));
  const depositMethods = automatic ? commonMethods("deposit_methods") : selectedBuy?.deposit_methods ?? ["crypto"];
  const withdrawMethods = value.sellMarketplace === "auto" ? commonMethods("withdraw_methods") : selectedSell?.withdraw_methods ?? ["crypto"];

  function swap() {
    if (automatic || value.sellMarketplace === "auto") return;
    patch({ buyMarketplace: value.sellMarketplace, sellMarketplace: value.buyMarketplace });
  }

  return (
    <section className={styles.profitBar} aria-label={t("profit.settings")}>
      <div className={styles.profitIntro}>
        <span>{t("profit.settings")}</span>
        <strong>{t(`profit.${value.mode}`)}</strong>
      </div>
      <label><span>{t("profit.mode")}</span><select value={value.mode} onChange={(event) => patch({ mode: event.target.value as ProfitSettingsValue["mode"] })}>{modes.map((mode) => <option key={mode} value={mode}>{t(`profit.${mode}`)}</option>)}</select></label>
      <label><span>{t("profit.buyOn")}</span><select disabled={value.mode === "quick_flip"} value={value.buyMarketplace} onChange={(event) => { const nextId = event.target.value; const nextMarket = marketplaces.find((item) => item.id === nextId); const nextDeposit = nextId === "all" ? commonMethods("deposit_methods") : nextMarket?.deposit_methods ?? []; patch({ buyMarketplace: nextId, depositMethod: nextDeposit.includes(value.depositMethod) ? value.depositMethod : nextDeposit[0] ?? "crypto", sellMarketplace: nextId === "all" ? "auto" : value.sellMarketplace === nextId ? enabledMarkets.find((item) => item.id !== nextId)?.id ?? "auto" : value.sellMarketplace }); }}><option value="all">{t("common.all")}</option>{enabledMarkets.map((market) => <option key={market.id} value={market.id}>{market.display_name}</option>)}</select></label>
      <button className={styles.swapButton} type="button" onClick={swap} disabled={automatic || value.mode === "quick_flip"} aria-label={t("profit.swap")}>⇄</button>
      <label><span>{t("profit.sellOn")}</span><select disabled={automatic || value.mode === "quick_flip"} value={automatic ? "auto" : value.sellMarketplace} onChange={(event) => { const nextId = event.target.value; const methods = nextId === "auto" ? commonMethods("withdraw_methods") : marketplaces.find((item) => item.id === nextId)?.withdraw_methods ?? []; patch({ sellMarketplace: nextId, withdrawMethod: methods.includes(value.withdrawMethod) ? value.withdrawMethod : methods[0] ?? "crypto" }); }}><option value="auto">{t("profit.auto")}</option>{enabledMarkets.map((market) => <option key={market.id} value={market.id}>{market.display_name}</option>)}</select></label>
      <label><span>{t("profit.deposit")}</span><select disabled={value.mode === "raw" || value.mode === "enhanced"} value={depositMethods.includes(value.depositMethod) ? value.depositMethod : depositMethods[0]} onChange={(event) => patch({ depositMethod: event.target.value as PaymentMethod })}>{depositMethods.map((method) => <option value={method} key={method}>{t(`profit.${method}`)}</option>)}</select></label>
      <label><span>{t("profit.withdraw")}</span><select disabled={value.mode === "raw"} value={withdrawMethods.includes(value.withdrawMethod) ? value.withdrawMethod : withdrawMethods[0]} onChange={(event) => patch({ withdrawMethod: event.target.value as PaymentMethod })}>{withdrawMethods.map((method) => <option value={method} key={method}>{t(`profit.${method}`)}</option>)}</select></label>
      {value.mode === "quick_flip" && <label className={styles.inlineCheck}><input type="checkbox" checked={value.useDepositFee} onChange={(event) => patch({ useDepositFee: event.target.checked })} />{t("profit.includeDeposit")}</label>}
    </section>
  );
}
