import { useEffect, useState } from "react";
import { calculate, getMarketOverview, searchSkins } from "./api";
import type { Fees, MarketOverview, ProfitResult, SkinSearchResult } from "./types";

const formatMoney = (cents: number) => `$${(cents / 100).toFixed(2)}`;

export default function App() {
  const [overview, setOverview] = useState<MarketOverview>();
  const [fees, setFees] = useState<Fees>();
  const [result, setResult] = useState<ProfitResult>();
  const [useDepositFee, setUseDepositFee] = useState(true);
  const [error, setError] = useState("");
  const [searchQuery, setSearchQuery] = useState("Redline");
  const [searchResults, setSearchResults] = useState<SkinSearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);

  useEffect(() => {
    getMarketOverview()
      .then((data) => {
        setOverview(data);
        setFees(data.default_fees);
      })
      .catch((reason: Error) => setError(reason.message));
  }, []);

  useEffect(() => {
    if (!overview || !fees) return;
    calculate(overview.prices[0].price_cents, overview.prices[1].price_cents, fees, useDepositFee)
      .then(setResult)
      .catch((reason: Error) => setError(reason.message));
  }, [overview, fees, useDepositFee]);

  const updateFee = (name: keyof Fees, value: string) => {
    setFees((current) => current && { ...current, [name]: Number(value) || 0 });
  };

  const submitSearch = async (event: React.FormEvent) => {
    event.preventDefault();
    if (searchQuery.trim().length < 2) return;

    setIsSearching(true);
    setError("");
    try {
      setSearchResults(await searchSkins(searchQuery));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось выполнить поиск");
    } finally {
      setIsSearching(false);
    }
  };

  if (error) return <main><p className="error">{error}</p></main>;
  if (!overview || !fees || !result) return <main><p>Загрузка данных…</p></main>;

  return (
    <main>
      <h1>Skin Market Tracker</h1>

      <section>
        <h2>Поиск скина</h2>
        <form onSubmit={submitSearch}>
          <input
            aria-label="Название скина"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder="Например, Redline"
          />
          <button type="submit" disabled={isSearching}>{isSearching ? "Ищем…" : "Найти"}</button>
        </form>
        {searchResults.map((item) => (
          <p key={item.market_hash_name}>
            <span>{item.market_hash_name}</span>
            {item.csfloat_price ? (
              <a href={item.csfloat_price.item_url} target="_blank" rel="noreferrer">
                CSFloat: {formatMoney(item.csfloat_price.price_cents)}
              </a>
            ) : item.csfloat_error ? (
              <span className="error">{item.csfloat_error}</span>
            ) : <span>Нет активного лота на CSFloat</span>}
          </p>
        ))}
      </section>

      <h2>{overview.item_name}</h2>

      <section>
        <h3>Цены</h3>
        {overview.prices.map((price) => (
          <p key={price.marketplace}>
            <a href={price.item_url} target="_blank" rel="noreferrer">{price.marketplace}</a>
            <span>{formatMoney(price.price_cents)}</span>
          </p>
        ))}
      </section>

      <section>
        <h3>Комиссии</h3>
        <label>
          <input type="checkbox" checked={useDepositFee} onChange={(event) => setUseDepositFee(event.target.checked)} />
          Учитывать депозит (выключите, если баланс уже есть)
        </label>
        <FeeInput label="Депозит, %" value={fees.deposit_fee_percent} disabled={!useDepositFee} onChange={(value) => updateFee("deposit_fee_percent", value)} />
        <FeeInput label="Продажа, %" value={fees.sell_fee_percent} onChange={(value) => updateFee("sell_fee_percent", value)} />
        <FeeInput label="Вывод, %" value={fees.withdraw_fee_percent} onChange={(value) => updateFee("withdraw_fee_percent", value)} />
      </section>

      <section className={result.profit_cents >= 0 ? "profit" : "loss"}>
        <h3>Результат</h3>
        <p>Комиссия депозита: {formatMoney(result.deposit_fee_cents)}</p>
        <p>Комиссия продажи: {formatMoney(result.sell_fee_cents)}</p>
        <p>Комиссия вывода: {formatMoney(result.withdraw_fee_cents)}</p>
        <strong>Прибыль: {formatMoney(result.profit_cents)}</strong>
        <strong>ROI: {result.roi_percent}%</strong>
      </section>
    </main>
  );
}

function FeeInput({ label, value, disabled = false, onChange }: { label: string; value: number; disabled?: boolean; onChange: (value: string) => void }) {
  return <label>{label}<input type="number" min="0" step="0.1" value={value} disabled={disabled} onChange={(event) => onChange(event.target.value)} /></label>;
}
