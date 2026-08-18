import type { Fees, MarketOverview, ProfitResult, SkinSearchResult } from "./types";

const API_URL = "http://127.0.0.1:8000";

export async function getMarketOverview(): Promise<MarketOverview> {
  const response = await fetch(`${API_URL}/api/market-overview`);
  if (!response.ok) throw new Error("Не удалось загрузить данные рынка");
  return response.json();
}

export async function searchSkins(query: string): Promise<SkinSearchResult[]> {
  const response = await fetch(`${API_URL}/api/search?q=${encodeURIComponent(query)}`);
  if (!response.ok) throw new Error("Не удалось выполнить поиск");
  return response.json();
}

export async function calculate(
  buyPrice: number,
  sellPrice: number,
  fees: Fees,
  useDepositFee: boolean,
): Promise<ProfitResult> {
  const response = await fetch(`${API_URL}/api/calculate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      buy_price_cents: buyPrice,
      sell_price_cents: sellPrice,
      use_deposit_fee: useDepositFee,
      ...fees,
    }),
  });
  if (!response.ok) throw new Error("Не удалось рассчитать прибыль");
  return response.json();
}
