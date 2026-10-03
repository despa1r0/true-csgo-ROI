import { useTranslation } from "react-i18next";

import type { FlipRiskLevel } from "@/shared/api";
import styles from "./market.module.css";

export function FlipRiskNotice({ level, score, compact = false }: {
  level: FlipRiskLevel | null | undefined;
  score?: number | null;
  compact?: boolean;
}) {
  const { t } = useTranslation();
  if (!level) return null;
  const className = level === "critical" ? styles.riskCritical
    : level === "high" ? styles.riskHigh : styles.riskNeutral;
  const Tag = compact ? "span" : "p";
  return <Tag className={`${styles.flipRisk} ${className} ${compact ? styles.flipRiskCompact : ""}`} role="status">
    {t(`flipRisk.${level}Title`)}
    {level !== "unknown" && score != null && <> · {t("flipRisk.score", { score })}</>}
  </Tag>;
}
