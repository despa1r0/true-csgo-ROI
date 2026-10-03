import { lazy, Suspense } from "react";
import { useTranslation } from "react-i18next";
import { RouterProvider, createBrowserRouter } from "react-router-dom";

import { AppShell } from "@/app/shell/AppShell";
import { RouteErrorPage } from "@/pages/RouteErrorPage";

const CatalogPage = lazy(() => import("@/features/catalog/CatalogPage").then((module) => ({ default: module.CatalogPage })));
const CalculatorPage = lazy(() => import("@/features/calculator/CalculatorPage").then((module) => ({ default: module.CalculatorPage })));
// Vite removes this route and its lazy import from every production build.
const DebugPage = __TRUE_ROI_DIAGNOSTICS__ ? lazy(() => import("@/features/debug/DebugPage").then((module) => ({ default: module.DebugPage }))) : null;

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
      ...(DebugPage ? [{ path: "debug", element: <Suspense fallback={loading}><DebugPage /></Suspense> }] : []),
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
