/** Only offer a marketplace request for a settled, unfiltered local miss. */
export function shouldOfferCsMoneySearch({ query, searchedQuery, hasFilters, searchComplete, matches, selected }:
  { query: string; searchedQuery: string; hasFilters: boolean; searchComplete: boolean; matches: number; selected: boolean }) {
  return searchedQuery.length >= 2 && query.trim() === searchedQuery && !hasFilters
    && searchComplete && matches === 0 && !selected;
}
