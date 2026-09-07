import { describe, expect, it } from "vitest";

import type { ListingFilters, MarketplaceOption } from "@/shared/api";
import {
  attachmentTooltip,
  filtersForMarketplace,
  isPaintIndexUnavailable,
  unsupportedAttachmentFilters,
} from "./ListingDialog";

function marketplace(overrides: Partial<MarketplaceOption["capabilities"]> = {}): MarketplaceOption {
  return {
    id: "test-market",
    display_name: "Test Market",
    currency: "USD",
    can_buy: true,
    can_sell: true,
    supports_fast_buy: false,
    capabilities: {
      can_buy: true,
      can_sell: true,
      supports_listings: true,
      supports_sales_history: false,
      supports_quick_sell: false,
      supports_float: false,
      supports_stickers: false,
      supports_charms: false,
      supports_best_deal_sort: false,
      ...overrides,
    },
    deposit_methods: ["crypto"],
    withdraw_methods: ["crypto"],
    fees: { deposit: {}, sell: null, withdraw: {} },
    fee_configuration_version: "test",
  };
}

describe("listing marketplace helpers", () => {
  it("keeps all-market requests compatible with each provider", () => {
    const filters: ListingFilters = { sort_by: "best_deal", has_stickers: true, has_charm: true };
    const basicMarket = marketplace({ supports_stickers: true });

    expect(filtersForMarketplace(filters, basicMarket).sort_by).toBe("lowest_price");
    expect(unsupportedAttachmentFilters(filters, basicMarket)).toEqual(["charms"]);
  });

  it("shows an attachment price in the hover text when the provider supplies it", () => {
    expect(attachmentTooltip("Sticker | Test", 256, "en-US", "Reference price", "Unavailable"))
      .toContain("$2.56");
    expect(attachmentTooltip("Charm | Test", null, "en-US", "Reference price", "Unavailable"))
      .toBe("Charm | Test · Unavailable");
  });

  it("recognizes both English and Russian legacy paint-index errors", () => {
    expect(isPaintIndexUnavailable("This item has no paint index")).toBe(true);
    expect(isPaintIndexUnavailable("Для скина отсутствует индекс покраски")).toBe(true);
  });
});
