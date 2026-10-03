import { useLayoutEffect, useRef } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import type { UIEvent } from "react";

export type BrowsePatch = Record<string, string | null>;
export const detailParams: BrowsePatch = { detail_variant: null, listing: null, analytics_market: null, tab: null };
export const wearParams: BrowsePatch = { ...detailParams, wear: null, listing_market: null, sort: null,
  kind: null, min_float: null, max_float: null, min_price: null, max_price: null, stickers: null, charm: null, period: null,
  compare_buy: null, compare_sell: null };

export function useBrowseHistory() {
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  function update(patch: BrowsePatch, replace = false, state: Record<string, unknown> = {}) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(patch)) {
      if (value) next.set(key, value); else next.delete(key);
    }
    setParams(next, { replace, state: { ...location.state,
      ...(replace ? {} : { browseParent: location.key }), ...state } });
  }
  function back(fallback: BrowsePatch) {
    if (location.state?.browseParent) navigate(-1);
    else update(fallback, true);
  }
  return { params, location, update, back };
}

const scrollPositions = new Map<string, number>();

/** Restore the independently scrolling list when returning from detail or calculator. */
export function useBrowseScroll() {
  const { key } = useLocation();
  const ref = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    if (ref.current) ref.current.scrollTop = scrollPositions.get(key) ?? 0;
  }, [key]);
  function onScroll(event: UIEvent<HTMLDivElement>) {
    scrollPositions.set(key, event.currentTarget.scrollTop);
    if (scrollPositions.size > 100) scrollPositions.delete(scrollPositions.keys().next().value!);
  }
  return { ref, onScroll };
}
