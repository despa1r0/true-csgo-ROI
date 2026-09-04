import { isRouteErrorResponse, useRouteError } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { Button, Card } from "@/shared/ui";

export function RouteErrorPage() {
  const error = useRouteError();
  const { t } = useTranslation();
  const status = isRouteErrorResponse(error) ? error.status : 500;

  return (
    <main className="route-error">
      <Card>
        <p className="route-error__status">{status}</p>
        <h1>{t("errors.route.title")}</h1>
        <p>{t("errors.route.description")}</p>
        <Button onClick={() => window.location.assign("/")}>{t("actions.returnHome")}</Button>
      </Card>
    </main>
  );
}
