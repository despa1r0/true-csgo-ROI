export type MarketplaceId = string;
export type ProfitMode = "raw" | "smart" | "enhanced" | "quick_flip" | "custom";
export type PaymentMethod = "card" | "crypto";
export type SellMode = "listing" | "fast_buy";
export type WearId =
  | "factory-new"
  | "minimal-wear"
  | "field-tested"
  | "well-worn"
  | "battle-scarred";
export type VariantKind = "any" | "normal" | "stattrak" | "souvenir";
export type ListingSort = "best_deal" | "lowest_price";

export type ApiErrorBody = {
  detail?: string | Array<{ loc?: Array<string | number>; msg?: string; type?: string }>;
  code?: string;
};

export type HealthResponse = {
  status: "ok" | string;
  catalogue: { skins: number; variants: number };
};

export type CatalogueFilter = { id: string; name: string; count: number; color?: string | null };
export type CatalogueFilters = {
  weapons: CatalogueFilter[];
  rarities: CatalogueFilter[];
  collections: CatalogueFilter[];
  item_types: CatalogueFilter[];
};

export type CatalogueSearchResult = {
  id: string;
  name: string;
  item_type: string;
  image_url: string | null;
  weapon_id: string | null;
  weapon_name: string | null;
  rarity_id: string | null;
  rarity_name: string | null;
  rarity_color: string | null;
  min_float: number | null;
  max_float: number | null;
  has_stattrak: boolean;
  has_souvenir: boolean;
  variant_count: number;
};

export type SkinVariant = {
  id: string;
  name: string;
  market_hash_name: string;
  wear_id: string | null;
  wear_name: string | null;
  stattrak: boolean;
  souvenir: boolean;
  image_url: string | null;
};

export type SkinQuality = { wear: string; variants: SkinVariant[] };
export type SkinDetails = CatalogueSearchResult & {
  description?: string | null;
  paint_index?: number | null;
  collections: Array<{ id: string; name: string; image_url?: string | null }>;
  qualities: SkinQuality[];
};

export type FeeRule = { percent: number; fixed_cents: number };
export type MarketplaceCapabilities = {
  can_buy: boolean;
  can_sell: boolean;
  supports_listings: boolean;
  supports_sales_history: boolean;
  supports_quick_sell: boolean;
  supports_float: boolean;
  supports_stickers: boolean;
  supports_charms: boolean;
  supports_best_deal_sort: boolean;
};
export type MarketplaceOption = {
  id: MarketplaceId;
  display_name: string;
  currency: string;
  can_buy: boolean;
  can_sell: boolean;
  supports_fast_buy: boolean;
  capabilities: MarketplaceCapabilities;
  deposit_methods: PaymentMethod[];
  withdraw_methods: PaymentMethod[];
  fees: {
    deposit: Partial<Record<PaymentMethod, FeeRule | null>>;
    sell: FeeRule | null;
    withdraw: Partial<Record<PaymentMethod, FeeRule | null>>;
  };
  fee_configuration_version: string;
};

export type Attachment = {
  name?: string | null;
  icon_url?: string | null;
  csfloat_price_cents?: number | null;
  csfloat_quantity?: number | null;
};

export type Listing = {
  listing_id?: string | null;
  variant_id?: string | null;
  market_hash_name: string;
  marketplace_id?: MarketplaceId;
  price_cents: number;
  predicted_price_cents?: number | null;
  item_url?: string | null;
  image_url?: string | null;
  float_value?: number | null;
  paint_seed?: number | null;
  paint_index?: number | null;
  wear_name?: string | null;
  stattrak?: boolean;
  souvenir?: boolean;
  deal_percent?: number;
  stickers?: Attachment[];
  charms?: Attachment[];
};

export type ListingsResponse = {
  marketplace?: string;
  listings: Listing[];
  error?: string | null;
  cached?: boolean;
  stale?: boolean;
  fetched_at?: string | null;
};

export type MarketPrice = {
  marketplace: MarketplaceId;
  price_cents: number;
  item_url: string;
  listing_id: string | null;
  float_value: number | null;
  quantity: number | null;
  fetched_at: string | null;
  stale: boolean;
};

export type ProfitOpportunity = ProfitResult & {
  variant_id?: string;
  market_hash_name?: string;
  profit_mode?: Exclude<ProfitMode, "custom">;
  buy_marketplace: MarketplaceId;
  sell_marketplace: MarketplaceId;
  buy_price_source?: "lowest_ask";
  sell_price_source?: "lowest_ask" | "best_bid";
  sell_mode: SellMode;
};
export type VariantComparison = {
  variant_id: string;
  market_hash_name: string;
  markets: Record<MarketplaceId, MarketPrice | null>;
  errors: Record<MarketplaceId, string>;
  cheapest_marketplace: MarketplaceId | null;
  cheapest_price_cents: number | null;
  gross_spread_cents: number | null;
  opportunities: ProfitOpportunity[];
};
export type MarketComparisonResponse = {
  skin_id: string;
  marketplaces: Array<{ id: string; name: string; error?: string | null }>;
  variants: VariantComparison[];
};

export type Sale = { sold_at: string; price_cents: number; float_value?: number | null };
export type BuyOrder = {
  price_cents: number;
  quantity: number;
  min_float?: number | null;
  max_float?: number | null;
};
export type MarketplaceDetails = {
  marketplace: MarketplaceId;
  variant_id: string;
  market_hash_name: string;
  overview: { price_cents?: number | null; active_listings?: number | null; item_url?: string | null };
  stats?: {
    sales_count?: number | null;
    sales_scope?: string | null;
    sales_per_day?: number | null;
    liquidity_score?: number | null;
    liquidity_label?: string | null;
    near_bid_depth?: number | null;
    sales_float_note?: string | null;
  };
  quick_sell?: {
    best_price_cents?: number | null;
    discount_percent?: number | null;
    near_bid_depth?: number | null;
    orders?: BuyOrder[];
    error?: string | null;
    note?: string | null;
  };
  listings?: Listing[];
  sales?: Sale[];
  listings_error?: string | null;
  sales_error?: string | null;
  fetched_at?: string | null;
  cached?: boolean;
  stale?: boolean;
};

export type AppliedFee = {
  enabled: boolean;
  amount_cents: number;
  percent: number;
  fixed_cents: number;
  method?: PaymentMethod | null;
};
export type CalculationRequest = {
  buy_price_cents: number;
  sell_price_cents: number;
  buy_marketplace: MarketplaceId;
  sell_marketplace: MarketplaceId;
  profit_mode: ProfitMode;
  deposit_method: PaymentMethod;
  withdraw_method: PaymentMethod;
  sell_mode: SellMode;
  use_deposit_fee: boolean;
  use_sell_fee: boolean;
  use_withdraw_fee: boolean;
};

export type ProfitResult = {
  buy_price_cents: number;
  deposit_fee_cents: number;
  sell_price_cents: number;
  sell_fee_cents: number;
  withdraw_fee_cents: number;
  gross_profit_cents: number;
  market_profit_cents: number;
  profit_cents: number;
  gross_roi_percent: number;
  market_roi_percent: number;
  cash_roi_percent: number;
  roi_percent: number;
  effective_buy_cents: number;
  effective_payout_cents: number;
  break_even_sell_price_cents: number;
  applied_fees?: { deposit: AppliedFee; sell: AppliedFee; withdraw: AppliedFee } | null;
  fee_configuration_version?: string | null;
};

export type SearchSkinsParams = {
  q?: string;
  weapon?: string;
  rarity?: string;
  collection?: string;
  item_type?: string;
  limit?: number;
};

export type ListingFilters = {
  sort_by?: ListingSort;
  wear?: WearId;
  variant?: VariantKind;
  min_float?: number;
  max_float?: number;
  min_price_cents?: number;
  max_price_cents?: number;
  has_stickers?: boolean;
  has_charm?: boolean;
  limit?: number;
};
