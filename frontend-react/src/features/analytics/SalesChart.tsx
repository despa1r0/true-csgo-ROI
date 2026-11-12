import { LineChart } from "echarts/charts";
import { DataZoomComponent, GridComponent, TooltipComponent } from "echarts/components";
import { init, use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { useEffect, useMemo, useRef } from "react";
import { useTranslation } from "react-i18next";

import type { Sale } from "@/shared/api";
import { formatDate, formatUsd } from "@/shared/lib/format";
import styles from "../catalog/market.module.css";
import { chartTheme } from "./chartTheme";

use([LineChart, GridComponent, TooltipComponent, DataZoomComponent, CanvasRenderer]);

export type HistoryPeriod = "24h" | "7d" | "14d" | "all";

type Props = { sales: Sale[]; period: HistoryPeriod };

export function SalesChart({ sales, period }: Props) {
  const node = useRef<HTMLDivElement>(null);
  const { i18n, t } = useTranslation();
  const locale = i18n.resolvedLanguage === "ru" ? "ru-RU" : "en-US";
  const filtered = useMemo(() => {
    const hours = period === "24h" ? 24 : period === "7d" ? 168 : period === "14d" ? 336 : null;
    const threshold = hours == null ? 0 : Date.now() - hours * 3_600_000;
    return sales
      .filter((sale) => Number.isFinite(sale.price_cents) && !Number.isNaN(new Date(sale.sold_at).getTime()) && new Date(sale.sold_at).getTime() >= threshold)
      .sort((a, b) => new Date(a.sold_at).getTime() - new Date(b.sold_at).getTime());
  }, [period, sales]);

  useEffect(() => {
    if (!node.current || filtered.length === 0) return;
    const chart = init(node.current, undefined, { renderer: "canvas" });
    const theme = chartTheme();
    chart.setOption({
      animationDuration: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 420,
      backgroundColor: "transparent",
      grid: { left: 62, right: 20, top: 24, bottom: 52 },
      tooltip: {
        trigger: "axis",
        backgroundColor: theme.surface,
        borderColor: theme.border,
        textStyle: { color: theme.text },
        formatter: (params: unknown) => {
          const first = Array.isArray(params) ? params[0] as { value: [number, number] } : null;
          return first ? `${formatDate(new Date(first.value[0]).toISOString(), locale)}<br/><strong>${formatUsd(first.value[1], locale)}</strong>` : "";
        },
      },
      xAxis: { type: "time", axisLabel: { color: theme.axis }, axisLine: { lineStyle: { color: theme.grid } }, splitLine: { show: false } },
      yAxis: { type: "value", scale: true, axisLabel: { color: theme.axis, formatter: (value: number) => `$${Math.round(value / 100)}` }, splitLine: { lineStyle: { color: theme.grid } } },
      dataZoom: [{ type: "inside" }, { type: "slider", height: 16, bottom: 8, borderColor: "transparent", fillerColor: theme.grid, handleStyle: { color: theme.axis }, textStyle: { color: theme.axis } }],
      series: [{ type: "line", data: filtered.map((sale) => [new Date(sale.sold_at).getTime(), sale.price_cents]), showSymbol: true, symbolSize: 6, connectNulls: false, lineStyle: { color: theme.line, width: 1.5 }, itemStyle: { color: theme.line, borderColor: theme.surface, borderWidth: 2 } }],
    });
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(node.current);
    return () => { observer.disconnect(); chart.dispose(); };
  }, [filtered, locale]);

  if (filtered.length === 0) return <div className={styles.emptyState}>{t("analytics.historyEmpty")}</div>;
  return <div ref={node} className={styles.salesChart} role="img" aria-label={t("analytics.history")} />;
}
