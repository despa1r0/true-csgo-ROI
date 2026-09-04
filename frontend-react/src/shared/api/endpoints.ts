import { apiClient } from "./client";
import type {
  CalculationRequest,
  CatalogueFilters,
  CatalogueSearchResult,
  HealthResponse,
  BuyOrder,
  ListingFilters,
  ListingsResponse,
  MarketComparisonResponse,
  MarketplaceDetails,
  MarketplaceOption,
  ProfitResult,
  SearchSkinsParams,
  SkinDetails,
} from "./types";

export const api = {
  health: (signal?: AbortSignal) => apiClient.get<HealthResponse>("/api/health", { signal }),
  catalogFilters: (signal?: AbortSignal) =>
    apiClient.get<CatalogueFilters>("/api/catalog/filters", { signal }),
  searchSkins: (params: SearchSkinsParams, signal?: AbortSignal) =>
    apiClient.get<CatalogueSearchResult[]>("/api/items/search", { query: { ...params }, signal }),
  skinDetails: (skinId: string, signal?: AbortSignal) =>
    apiClient.get<SkinDetails>(`/api/skins/${encodeURIComponent(skinId)}`, { signal }),
  marketplaces: (signal?: AbortSignal) =>
    apiClient.get<MarketplaceOption[]>("/api/marketplaces", { signal }),
  marketComparison: (
    skinId: string,
    params: { profit_mode: Exclude<CalculationRequest["profit_mode"], "custom">; deposit_method: string; withdraw_method: string; use_deposit_fee: boolean },
    signal?: AbortSignal,
  ) => apiClient.get<MarketComparisonResponse>(`/api/skins/${encodeURIComponent(skinId)}/markets/compare`, { query: params, signal }),
  calculate: (request: CalculationRequest, signal?: AbortSignal) =>
    apiClient.post<ProfitResult, CalculationRequest>("/api/calculate", request, { signal }),
  skinListings: (skinId: string, marketplaceId: string, filters: ListingFilters, signal?: AbortSignal) =>
    apiClient.get<ListingsResponse>(
      `/api/skins/${encodeURIComponent(skinId)}/market/${encodeURIComponent(marketplaceId)}/listings`,
      { query: { ...filters }, signal },
    ),
  variantDetails: (variantId: string, marketplaceId: string, signal?: AbortSignal) =>
    apiClient.get<MarketplaceDetails>(
      `/api/variants/${encodeURIComponent(variantId)}/market/${encodeURIComponent(marketplaceId)}`,
      { signal },
    ),
  listingQuickSell: (listingId: string, signal?: AbortSignal) =>
    apiClient.get<{ best_price_cents?: number | null; best_price_quantity?: number; discount_percent?: number | null; near_bid_depth?: number; orders?: BuyOrder[]; error?: string | null; note?: string | null }>(
      `/api/listings/${encodeURIComponent(listingId)}/market/csfloat/quick-sell`,
      { signal },
    ),
};
