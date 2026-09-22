import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { api } from "@/shared/api";
import { Button } from "@/shared/ui";
import styles from "./AppShell.module.css";

type Theme = "light" | "dark";

function initialTheme(): Theme {
  const saved = window.localStorage.getItem("trueroi-theme");
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function AppShell() {
  const { i18n, t } = useTranslation();
  const location = useLocation();
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const nextLanguage = i18n.resolvedLanguage === "ru" ? "en" : "ru";
  const health = useQuery({ queryKey: ["health"], queryFn: ({ signal }) => api.health(signal), refetchInterval: 60_000 });

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", theme === "dark" ? "#090c0c" : "#f3f7f6");
    window.localStorage.setItem("trueroi-theme", theme);
  }, [theme]);

  return (
    <div className={styles.shell}>
      <a className={styles.skipLink} href="#main-content">{t("app.skipToContent")}</a>
      <header className={styles.header}>
        <NavLink className={styles.brand} to="/" aria-label={t("app.homeLabel")} translate="no">
          <span className={styles.brandMark}>TR</span>
          <span className={styles.brandName}>true<span>ROI</span></span>
        </NavLink>

        <nav className={styles.navigation} aria-label={t("app.navigationLabel")}>
          <NavLink className={({ isActive }) => (isActive ? styles.activeLink : styles.link)} end to="/" viewTransition>
            <MarketIcon />
            {t("navigation.catalog")}
          </NavLink>
          <NavLink className={({ isActive }) => (isActive ? styles.activeLink : styles.link)} to="/calculator" viewTransition>
            <CalculatorIcon />
            {t("navigation.calculator")}
          </NavLink>
        </nav>

        <div className={styles.headerTools}>
          <span className={health.isError ? styles.offline : styles.online} aria-live="polite">
            <i />
            {health.data ? t("app.skins", { count: health.data.catalogue.skins }) : health.isError ? t("app.offline") : t("common.loading")}
          </span>
          <Button className={styles.iconButton} aria-label={t(theme === "dark" ? "theme.useLight" : "theme.useDark")} onClick={() => setTheme(theme === "dark" ? "light" : "dark")} size="small" variant="ghost">
            {theme === "dark" ? <SunIcon /> : <MoonIcon />}
          </Button>
          <Button className={styles.languageButton} aria-label={t("language.switchLabel", { language: nextLanguage.toUpperCase() })} onClick={() => void i18n.changeLanguage(nextLanguage)} size="small" variant="ghost">
            {nextLanguage.toUpperCase()}
          </Button>
        </div>
      </header>

      <main className={styles.main} id="main-content" tabIndex={-1}>
        <div className={styles.routeTransition} key={location.pathname}>
          <Outlet />
        </div>
      </main>
      <footer className={styles.footer}><span translate="no">trueROI</span><span>{t("app.footer")}</span></footer>
    </div>
  );
}

function MarketIcon() { return <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M4 19V9m5 10V5m6 14v-7m5 7V3" /></svg>; }
function CalculatorIcon() { return <svg aria-hidden="true" viewBox="0 0 24 24"><rect x="4" y="3" width="16" height="18" rx="3" /><path d="M8 7h8M8 12h2m4 0h2m-8 4h2m4 0h2" /></svg>; }
function SunIcon() { return <svg aria-hidden="true" viewBox="0 0 24 24"><circle cx="12" cy="12" r="4" /><path d="M12 2v2m0 16v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42" /></svg>; }
function MoonIcon() { return <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M20 15.5A8.5 8.5 0 1 1 8.5 4 7 7 0 0 0 20 15.5Z" /></svg>; }
