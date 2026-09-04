// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "./endpoints";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("listing attachment filters", () => {
  it("sends sticker and charm presence filters to the selected marketplace", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ listings: [] }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }));

    await api.skinListings("skin/one", "white market", {
      has_stickers: true,
      has_charm: true,
      limit: 30,
    });

    const requestedUrl = String(fetchMock.mock.calls[0]?.[0]);
    expect(requestedUrl).toContain("/api/skins/skin%2Fone/market/white%20market/listings?");
    expect(requestedUrl).toContain("has_stickers=true");
    expect(requestedUrl).toContain("has_charm=true");
  });

  it("does not invent parameters for a sticker or charm name search", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ listings: [] }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }));

    await api.skinListings("skin-1", "csfloat", { has_stickers: true });

    const requestedUrl = new URL(String(fetchMock.mock.calls[0]?.[0]), window.location.origin);
    expect([...requestedUrl.searchParams.keys()]).toEqual(["has_stickers"]);
    expect(requestedUrl.searchParams.has("sticker_name")).toBe(false);
    expect(requestedUrl.searchParams.has("charm_name")).toBe(false);
  });
});

describe("complete item catalogue", () => {
  it("searches the item endpoint and forwards the item type", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("[]", {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }));

    await api.searchSkins({ q: "copenhagen", item_type: "sticker", limit: 8 });

    const requestedUrl = new URL(String(fetchMock.mock.calls[0]?.[0]), window.location.origin);
    expect(requestedUrl.pathname).toBe("/api/items/search");
    expect(requestedUrl.searchParams.get("item_type")).toBe("sticker");
    expect(requestedUrl.searchParams.get("q")).toBe("copenhagen");
  });
});
