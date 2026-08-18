export type MarketPrice = {
  marketplace: string;
  price_cents: number;
  item_url: string;
};

export type Fees = {
  deposit_fee_percent: number;
  sell_fee_percent: number;
  withdraw_fee_percent: number;
};

export type MarketOverview = {
  item_name: string;
  prices: MarketPrice[];
  default_fees: Fees;
};

export type ProfitResult = {
  buy_price_cents: number;
  deposit_fee_cents: number;
  sell_price_cents: number;
  sell_fee_cents: number;
  withdraw_fee_cents: number;
  profit_cents: number;
  roi_percent: number;
};

export type SkinSearchResult = {
  market_hash_name: string;
  csfloat_price: MarketPrice | null;
  csfloat_error: string | null;
};
