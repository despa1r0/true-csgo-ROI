import { useTranslation } from "react-i18next";

import type { FlipRiskLevel } from "@/shared/api";
import styles from "./market.module.css";

export function FlipRiskNotice({ level, score, cashRoiPercent, compact = false }: {
  level: FlipRiskLevel | null | undefined;
  score?: number | null;
  cashRoiPercent?: number | null;
  compact?: boolean;
}) {
  const { t } = useTranslation();
  if (!level) return null;
  const className = level === "critical" ? styles.riskCritical
    : level === "high" ? styles.riskHigh : styles.riskCaution;
  return <p className={`${styles.flipRisk} ${className} ${compact ? styles.flipRiskCompact : ""}`} role="status">
    <strong>{t(`flipRisk.${level}Title`)}</strong>{" "}
    {score != null && t("flipRisk.score", { score })}{score != null && " · "}
    {t(`flipRisk.${level}Body`)}
    {cashRoiPercent != null && " "}{cashRoiPercent != null && t("flipRisk.askAssumption", { roi: cashRoiPercent })}
  </p>;
}
