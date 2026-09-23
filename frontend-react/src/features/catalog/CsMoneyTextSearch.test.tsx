// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api, type CsMoneyTextSearch as Search } from "@/shared/api";
import "@/shared/i18n";
import { CsMoneySearchResult, CsMoneyTextSearch } from "./CsMoneyTextSearch";

afterEach(() => vi.restoreAllMocks());

describe("CS.MONEY text search UI", () => {
  it.each(["queued", "running", "complete", "empty", "blocked", "error", "expired"] as const)(
    "shows %s status", (status) => {
      const html = renderToStaticMarkup(<CsMoneySearchResult current={{ request_id: "1", status }} />);
      expect(html).toContain("role=\"status\"");
      expect(html).not.toContain("csmoneySearch.");
    },
  );

  it("shows an empty result and a separate failure without fabricated listings", () => {
    const empty = renderToStaticMarkup(<CsMoneySearchResult current={{ request_id: "1", status: "empty", result: {
      source_url: "https://cs.money/", page_items: 0, is_partial: false, listings: [],
    } }} />);
    expect(empty).toContain("No listings found");
    expect(empty).not.toContain("href=");
    const failure = renderToStaticMarkup(<CsMoneySearchResult current={{ request_id: "1", status: "error", error: "Failed to read page" }} />);
    expect(failure).toContain("Failed to read page");
  });

  it("renders actual listing name, price and marketplace link", () => {
    const current: Search = { request_id: "1", status: "complete", result: {
      source_url: "https://cs.money/", page_items: 1, is_partial: false, listings: [{
        listing_id: "42", item_name: "Actual | Name", price_cents: 1235,
        item_url: "https://cs.money/pl/market/buy/?search=Actual", float_value: 0.12,
        paint_seed: 7, image_url: null, phase: null,
      }],
    } };
    const html = renderToStaticMarkup(<CsMoneySearchResult current={current} />);
    expect(html).toContain("Actual | Name");
    expect(html).toContain("12.35");
    expect(html).toContain("https://cs.money/pl/market/buy/");
  });

  it("coalesces repeated clicks while a request is pending", async () => {
    (globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    let resolve!: (value: Search) => void;
    const pending = new Promise<Search>((done) => { resolve = done; });
    const create = vi.spyOn(api, "createCsMoneySearch").mockReturnValue(pending);
    vi.spyOn(api, "csMoneySearchStatus").mockResolvedValue({ request_id: "1", status: "queued" });
    const container = document.createElement("div");
    const root = createRoot(container);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    await act(async () => root.render(<QueryClientProvider client={client}><CsMoneyTextSearch query="missing" /></QueryClientProvider>));
    const button = container.querySelector("button")!;
    await act(async () => { button.click(); button.click(); });
    expect(create).toHaveBeenCalledTimes(1);
    await act(async () => resolve({ request_id: "1", status: "queued" }));
    await act(async () => root.unmount());
    client.clear();
  });
});
