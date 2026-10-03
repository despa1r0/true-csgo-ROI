// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { api, type CatalogueSearchResult } from "@/shared/api";
import "@/shared/i18n";
import { CatalogPage } from "./CatalogPage";

afterEach(() => vi.restoreAllMocks());

it.each(["csmoney", "csfloat"])("renders cached %s prices while another provider holds the live comparison", async (market) => {
  (globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  const skin: CatalogueSearchResult = { id: "skin-1", name: "Redline", item_type: "skin", image_url: null,
    weapon_id: null, weapon_name: null, rarity_id: null, rarity_name: null, rarity_color: null,
    min_float: null, max_float: null, has_stattrak: false, has_souvenir: false, variant_count: 1 };
  vi.spyOn(api, "marketplaces").mockResolvedValue([]);
  vi.spyOn(api, "catalogFilters").mockResolvedValue({ item_types: [], weapons: [], rarities: [], collections: [] });
  vi.spyOn(api, "searchSkins").mockResolvedValue([skin]);
  vi.spyOn(api, "skinDetails").mockResolvedValue({ ...skin, collections: [], qualities: [{ wear: "Field-Tested",
    variants: [{ id: "variant-1", name: "Redline", market_hash_name: "Redline (Field-Tested)", wear_id: "ft",
      wear_name: "Field-Tested", stattrak: false, souvenir: false, image_url: null }] }] });
  const price = { marketplace: market, price_cents: 1234, item_url: "https://example.test/", listing_id: "1",
    float_value: null, quantity: 1, fetched_at: "2026-10-03T08:00:00Z", stale: false };
  const combined = vi.spyOn(api, "marketComparison").mockImplementation((_id, params) => params.cached_only
    ? Promise.resolve({ skin_id: "skin-1", marketplaces: [], variants: [{ variant_id: "variant-1",
      market_hash_name: "Redline (Field-Tested)", markets: { csfloat: market === "csfloat" ? price : null }, errors: {},
      cheapest_marketplace: market, cheapest_price_cents: 1234, gross_spread_cents: null, opportunities: [] }] })
    : new Promise(() => {}));
  const cached = vi.spyOn(api, "csMoneyPrices").mockResolvedValue({ marketplace: "csmoney", cache_ttl_seconds: 1800,
    refresh_queued: false, variants: [{ variant_id: "variant-1", market_hash_name: "Redline (Field-Tested)",
      listing: market === "csmoney" ? { ...price, source: "storefront" } : null }] });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const container = document.createElement("div");
  const root = createRoot(container);
  try {
    await act(async () => root.render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/?q=Redline"]}>
      <CatalogPage />
    </MemoryRouter></QueryClientProvider>));
    await vi.waitFor(async () => {
      await act(async () => { await new Promise((done) => setTimeout(done, 10)); });
      expect(container.querySelector("#skin-search-suggestions button")).not.toBeNull();
    });
    await act(async () => (container.querySelector("#skin-search-suggestions button") as HTMLButtonElement).click());
    await vi.waitFor(async () => {
      await act(async () => { await new Promise((done) => setTimeout(done, 10)); });
      expect(container.textContent).toContain("12.34");
    });
    expect(combined).toHaveBeenCalledTimes(2);
    expect(cached).toHaveBeenCalledTimes(1);
    expect(container.textContent).not.toContain("No quote");
  } finally {
    await act(async () => root.unmount());
    client.clear();
  }
});
