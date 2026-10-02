import { expect, it } from "vitest";
import { shouldOfferCsMoneySearch } from "./shouldOfferCsMoneySearch";

it("offers manual search only after a settled unfiltered local miss", () => {
  const state = { query: "missing", searchedQuery: "missing", hasFilters: false,
    searchComplete: true, matches: 0, selected: false };
  expect(shouldOfferCsMoneySearch(state)).toBe(true);
  expect(shouldOfferCsMoneySearch({ ...state, query: "missing more" })).toBe(false);
  expect(shouldOfferCsMoneySearch({ ...state, searchComplete: false })).toBe(false);
  expect(shouldOfferCsMoneySearch({ ...state, matches: 1 })).toBe(false);
  expect(shouldOfferCsMoneySearch({ ...state, hasFilters: true })).toBe(false);
});
