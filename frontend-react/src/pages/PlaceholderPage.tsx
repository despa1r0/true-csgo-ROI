import { useTranslation } from "react-i18next";

import { Card } from "@/shared/ui";
import styles from "./PlaceholderPage.module.css";

type PlaceholderPageProps = {
  translationKey: "pages.catalog" | "pages.calculator" | "pages.skinAnalytics";
};

export function PlaceholderPage({ translationKey }: PlaceholderPageProps) {
  const { t } = useTranslation();

  return (
    <Card className={styles.placeholder}>
      <span className={styles.eyebrow}>{t("app.name")}</span>
      <h1>{t(`${translationKey}.title`)}</h1>
      <p>{t(`${translationKey}.description`)}</p>
    </Card>
  );
}
