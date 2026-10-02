import { useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { api, type CsMoneyTextSearch as Search } from "@/shared/api";
import { formatUsd } from "@/shared/lib/format";
import styles from "./market.module.css";

export function CsMoneyTextSearch({ query }: { query: string }) {
  const { t } = useTranslation();
  const [request, setRequest] = useState<Search | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const submitting = useRef(false);
  const statusQuery = useQuery({
    queryKey: ["csmoney-text-search", request?.request_id],
    queryFn: ({ signal }) => api.csMoneySearchStatus(request!.request_id, signal),
    enabled: Boolean(request),
    refetchInterval: (queryState) => ["queued", "running"].includes(queryState.state.data?.status ?? request?.status ?? "") ? 1500 : false,
    retry: 1,
  });
  const current = statusQuery.data ?? request;
  const status = current?.status;

  async function startSearch() {
    if (submitting.current || (request && status !== "expired" && status !== "error")) return;
    submitting.current = true;
    setSubmitError(null);
    try {
      setRequest(await api.createCsMoneySearch(query));
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : t("csmoneySearch.error"));
    } finally {
      submitting.current = false;
    }
  }

  return <section className={styles.textSearch} aria-live="polite">
    <div className={styles.textSearchHead}>
      <div><small>CS.MONEY</small><strong>{t("csmoneySearch.title")}</strong><span>{t("csmoneySearch.note")}</span></div>
      <button type="button" onClick={startSearch} disabled={submitting.current || Boolean(request && status !== "expired" && status !== "error")}>{t("csmoneySearch.action")}</button>
    </div>
    <CsMoneySearchResult current={current} submitError={submitError} statusError={statusQuery.isError} />
  </section>;
}

export function CsMoneySearchResult({ current, submitError = null, statusError = false }: {
  current: Search | null; submitError?: string | null; statusError?: boolean;
}) {
  const { t, i18n } = useTranslation();
  const locale = i18n.resolvedLanguage === "ru" ? "ru-RU" : "en-US";
  return <>
    {current?.status && <p role="status" className={styles.textSearchStatus}>{t(`csmoneySearch.${current.status}`)}{current.error ? `: ${current.error}` : ""}</p>}
    {(submitError || statusError) && <p role="alert" className={styles.textSearchError}>{submitError ?? t("csmoneySearch.error")}</p>}
    {current?.result?.is_partial && <p className={styles.textSearchStatus}>{t("csmoneySearch.firstPage")}</p>}
    {current?.result?.listings && <div className={styles.textSearchListings}>
      {current.result.listings.map((listing) => <a key={listing.listing_id} href={listing.item_url} target="_blank" rel="noopener noreferrer" className={styles.textSearchListing}>
        {listing.image_url && <img src={listing.image_url} alt="" loading="lazy" width="64" height="52" />}
        <span><strong>{listing.item_name}</strong><small>#{listing.listing_id}{listing.float_value != null ? ` · Float ${listing.float_value}` : ""}{listing.paint_seed != null ? ` · Seed ${listing.paint_seed}` : ""}{listing.phase ? ` · ${listing.phase}` : ""}</small></span>
        <b>{formatUsd(listing.price_cents, locale)}</b>
      </a>)}
    </div>}
  </>;
}
