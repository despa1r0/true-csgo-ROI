import { useTranslation } from "react-i18next";

import type { FlipRiskLevel } from "@/shared/api";
import styles from "./market.module.css";

export function FlipRiskNotice({ level, score, cashRoiPercent, sellMarketplace, dataStatus, compact = false }: {
  level: FlipRiskLevel | null | undefined;
  score?: number | null;
  cashRoiPercent?: number | null;
  sellMarketplace?: string;
  dataStatus?: string;
  compact?: boolean;
}) {
  const { t } = useTranslation();
  if (!level) return null;
  const className = level === "critical" ? styles.riskCritical
    : level === "high" ? styles.riskHigh : styles.riskCaution;
  const reason = level === "unknown" && sellMarketplace === "csmoney" ? "flipRisk.csMoneyUnavailableBody"
    : level === "unknown" && ["missing_ask", "missing_orders", "missing_sales"].includes(dataStatus ?? "")
      ? `flipRisk.${dataStatus}` : `flipRisk.${level}Body`;
  return <p className={`${styles.flipRisk} ${className} ${compact ? styles.flipRiskCompact : ""}`} role="status">
    <strong>{t(`flipRisk.${level}Title`)}</strong>{" "}
    {score != null && t("flipRisk.score", { score })}{score != null && " · "}
    {t(reason)}
    {cashRoiPercent != null && " "}{cashRoiPercent != null && t("flipRisk.askAssumption", { roi: cashRoiPercent })}
  </p>;
}
