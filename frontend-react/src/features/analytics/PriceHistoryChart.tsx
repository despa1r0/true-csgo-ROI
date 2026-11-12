import { LineChart } from "echarts/charts";
import { DataZoomComponent, GridComponent, TooltipComponent } from "echarts/components";
import { init, use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";

import type { WikiPriceHistory } from "@/shared/api/types";
import { formatDate, formatUsd } from "@/shared/lib/format";
import styles from "../catalog/market.module.css";
import { chartTheme } from "./chartTheme";

use([LineChart, GridComponent, TooltipComponent, DataZoomComponent, CanvasRenderer]);

export function PriceHistoryChart({ points }: { points: WikiPriceHistory["points"] }) {
  const node = useRef<HTMLDivElement>(null);
  const { i18n, t } = useTranslation();
  const locale = i18n.resolvedLanguage === "ru" ? "ru-RU" : "en-US";

  useEffect(() => {
    if (!node.current || points.length === 0) return;
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
      series: [{ type: "line", data: points.map((point) => [new Date(point.at).getTime(), point.price_cents]), showSymbol: points.length < 25, symbolSize: 5, connectNulls: false, lineStyle: { color: theme.line, width: 1.5 }, itemStyle: { color: theme.line } }],
    });
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(node.current);
    return () => { observer.disconnect(); chart.dispose(); };
  }, [points, locale]);

  return <div ref={node} className={styles.salesChart} role="img" aria-label={t("analytics.wikiTradePriceHistory")} />;
}
