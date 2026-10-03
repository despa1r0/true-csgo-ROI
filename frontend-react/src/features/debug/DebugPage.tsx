import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, useSyncExternalStore } from "react";
import { useTranslation } from "react-i18next";
import { dataDiagnostics, safeDiagnosticText } from "./diagnostics";
import { clearRequests, requestSnapshot, subscribeRequests } from "./requestLog";
import styles from "./debug.module.css";

const copy = {
  en: { title: "Data diagnostics", note: "Development only. Browser query state and API responses from this session; server logs are not fetched.",
    queries: "Queries", requests: "API requests", empty: "Open the catalogue or calculator first, then return here.",
    updated: "Browser cache updated", finished: "Request finished", fetching: "Network state", source: "Browser query cache", error: "Error", clear: "Clear request history",
    method: "Method", path: "API path", status: "HTTP", duration: "Time", snapshot: "Source / backend cache", mutation: "Calculation / action" },
  ru: { title: "Диагностика данных", note: "Только разработка. Состояние запросов браузера и ответы API за эту сессию; серверные логи не загружаются.",
    queries: "Запросы", requests: "Обращения к API", empty: "Откройте каталог или калькулятор, затем вернитесь сюда.",
    updated: "Обновление кэша браузера", finished: "Запрос завершён", fetching: "Состояние сети", source: "Кэш запросов браузера", error: "Ошибка", clear: "Очистить журнал запросов",
    method: "Метод", path: "Путь API", status: "HTTP", duration: "Время", snapshot: "Источник / кэш backend", mutation: "Расчёт / действие" },
};

export function DebugPage() {
  const { i18n } = useTranslation();
  const text = copy[i18n.resolvedLanguage === "ru" ? "ru" : "en"];
  const client = useQueryClient();
  const [, update] = useState(0);
  const requests = useSyncExternalStore(subscribeRequests, requestSnapshot);
  useEffect(() => {
    const changed = () => update((value) => value + 1);
    const unsubscribeQueries = client.getQueryCache().subscribe(changed);
    const unsubscribeMutations = client.getMutationCache().subscribe(changed);
    return () => { unsubscribeQueries(); unsubscribeMutations(); };
  }, [client]);
  const queries = client.getQueryCache().getAll();
  const mutations = client.getMutationCache().getAll();
  const date = (value: number) => value ? new Intl.DateTimeFormat(i18n.resolvedLanguage, { dateStyle: "short", timeStyle: "medium" }).format(value) : "—";

  return <section className={styles.page} data-testid="TRUEROI_DEV_DIAGNOSTICS">
    <header><span className={styles.badge}>DEV</span><h1>{text.title}</h1><p>{text.note}</p></header>
    <section><h2>{text.requests} · {requests.length}</h2>
      <button type="button" disabled={!requests.length} onClick={clearRequests}>{text.clear}</button>
      <div className={styles.table}><table><thead><tr>{[text.finished, text.method, text.path, text.status, text.duration, text.error].map((label) => <th scope="col" key={label}>{label}</th>)}</tr></thead>
        <tbody>{requests.map((entry, index) => <tr key={`${entry.at}:${index}`}><td>{date(entry.at)}</td><td>{entry.method}</td><td>{entry.path}</td><td>{entry.status ?? "—"}</td><td>{Math.round(entry.duration)} ms</td><td>{entry.error ?? "—"}</td></tr>)}</tbody></table></div>
    </section>
    <section><h2>{text.queries} · {queries.length}</h2>
      {!queries.length && <p>{text.empty}</p>}
      {queries.map((query) => {
        const rows = dataDiagnostics(query.state.data);
        return <details key={query.queryHash} className={styles.query}>
          <summary>{safeDiagnosticText(query.queryKey[0])} · {query.state.status} · {query.state.fetchStatus}</summary>
          <dl><dt>{text.source}</dt><dd>{safeDiagnosticText(query.queryKey.slice(0, 3).filter((value) => typeof value === "string").join(" · "))}</dd>
            <dt>{text.updated}</dt><dd>{date(query.state.dataUpdatedAt)}</dd>
            <dt>{text.fetching}</dt><dd>{query.state.fetchStatus}</dd>
            {query.state.error && <><dt>{text.error}</dt><dd>{safeDiagnosticText(query.state.error.message)}</dd></>}
          </dl>
          {rows.length > 0 && <><h3>{text.snapshot}</h3><dl>{rows.map((row) => <div key={row.field}><dt>{row.field}</dt><dd>{row.value}</dd></div>)}</dl></>}
        </details>;
      })}
      {mutations.map((mutation) => <details key={mutation.mutationId} className={styles.query}><summary>{text.mutation} · {mutation.state.status}</summary>
        {mutation.state.error && <p>{safeDiagnosticText(mutation.state.error.message)}</p>}
        <dl>{dataDiagnostics(mutation.state.data).map((row) => <div key={row.field}><dt>{row.field}</dt><dd>{row.value}</dd></div>)}</dl>
      </details>)}
    </section>
  </section>;
}
