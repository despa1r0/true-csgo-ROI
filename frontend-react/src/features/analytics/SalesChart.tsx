import { LineChart } from "echarts/charts";
import { DataZoomComponent, GridComponent, TooltipComponent } from "echarts/components";
import { init, use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { useEffect, useMemo, useRef } from "react";
import { useTranslation } from "react-i18next";

import type { Sale } from "@/shared/api";
import { formatDate, formatUsd } from "@/shared/lib/format";
import styles from "../catalog/market.module.css";

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
    chart.setOption({
      animationDuration: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 420,
      backgroundColor: "transparent",
      grid: { left: 62, right: 20, top: 24, bottom: 52 },
      tooltip: {
        trigger: "axis",
        backgroundColor: "#11131a",
        borderColor: "#3a3e50",
        textStyle: { color: "#f7f7fb" },
        formatter: (params: unknown) => {
          const first = Array.isArray(params) ? params[0] as { value: [number, number] } : null;
          return first ? `${formatDate(new Date(first.value[0]).toISOString(), locale)}<br/><strong>${formatUsd(first.value[1], locale)}</strong>` : "";
        },
      },
      xAxis: { type: "time", axisLabel: { color: "#747789" }, axisLine: { lineStyle: { color: "#272a38" } }, splitLine: { show: false } },
      yAxis: { type: "value", scale: true, axisLabel: { color: "#747789", formatter: (value: number) => `$${Math.round(value / 100)}` }, splitLine: { lineStyle: { color: "#20232f" } } },
      dataZoom: [{ type: "inside" }, { type: "slider", height: 16, bottom: 8, borderColor: "transparent", fillerColor: "rgba(139,92,246,.18)", handleStyle: { color: "#8b5cf6" }, textStyle: { color: "#747789" } }],
      series: [{ type: "line", data: filtered.map((sale) => [new Date(sale.sold_at).getTime(), sale.price_cents]), showSymbol: true, symbolSize: 6, connectNulls: false, lineStyle: { color: "#22d3ee", width: 2 }, itemStyle: { color: "#a78bfa", borderColor: "#11131a", borderWidth: 2 }, areaStyle: { color: "rgba(34,211,238,.045)" } }],
    });
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(node.current);
    return () => { observer.disconnect(); chart.dispose(); };
  }, [filtered, locale]);

  if (filtered.length === 0) return <div className={styles.emptyState}>{t("analytics.historyEmpty")}</div>;
  return <div ref={node} className={styles.salesChart} role="img" aria-label={t("analytics.history")} />;
}
