import { lazy, Suspense } from "react";
import { useTranslation } from "react-i18next";
import { RouterProvider, createBrowserRouter } from "react-router-dom";

import { AppShell } from "@/app/shell/AppShell";
import { RouteErrorPage } from "@/pages/RouteErrorPage";

const CatalogPage = lazy(() => import("@/features/catalog/CatalogPage").then((module) => ({ default: module.CatalogPage })));
const CalculatorPage = lazy(() => import("@/features/calculator/CalculatorPage").then((module) => ({ default: module.CalculatorPage })));

function LoadingFallback() {
  const { t } = useTranslation();
  return <div style={{ minHeight: "50vh", display: "grid", placeItems: "center", color: "var(--color-text-muted)" }}>{t("common.loading")}</div>;
}

const loading = <LoadingFallback />;

const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    errorElement: <RouteErrorPage />,
    children: [
      {
        index: true,
        element: <Suspense fallback={loading}><CatalogPage /></Suspense>,
      },
      {
        path: "calculator",
        element: <Suspense fallback={loading}><CalculatorPage /></Suspense>,
      },
    ],
  },
]);

export function AppRouter() {
  return <RouterProvider router={router} />;
}
