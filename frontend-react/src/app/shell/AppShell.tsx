import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { NavLink, Outlet } from "react-router-dom";

import { Button } from "@/shared/ui";
import { api } from "@/shared/api";
import styles from "./AppShell.module.css";

export function AppShell() {
  const { i18n, t } = useTranslation();
  const nextLanguage = i18n.resolvedLanguage === "ru" ? "en" : "ru";
  const health = useQuery({ queryKey: ["health"], queryFn: ({ signal }) => api.health(signal), refetchInterval: 60_000 });

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <NavLink className={styles.brand} to="/" aria-label={t("app.homeLabel")}>
          true<span>ROI</span>
        </NavLink>

        <nav className={styles.navigation} aria-label={t("app.navigationLabel")}>
          <NavLink className={({ isActive }) => (isActive ? styles.activeLink : styles.link)} end to="/">
            {t("navigation.catalog")}
          </NavLink>
          <NavLink className={({ isActive }) => (isActive ? styles.activeLink : styles.link)} to="/calculator">
            {t("navigation.calculator")}
          </NavLink>
        </nav>

        <div className={styles.headerTools}>
          <span className={health.isError ? styles.offline : styles.online}>
            <i />
            {health.data ? t("app.skins", { count: health.data.catalogue.skins }) : health.isError ? t("app.offline") : t("common.loading")}
          </span>
          <Button
            aria-label={t("language.switchLabel", { language: nextLanguage.toUpperCase() })}
            onClick={() => void i18n.changeLanguage(nextLanguage)}
            size="small"
            variant="ghost"
          >
            {nextLanguage.toUpperCase()}
          </Button>
        </div>
      </header>

      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  );
}
