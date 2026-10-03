// @vitest-environment jsdom
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, expect, it } from "vitest";
import i18n from "@/shared/i18n";
import { FlipRiskNotice } from "./FlipRiskNotice";

afterEach(async () => { await i18n.changeLanguage("en"); });

it.each(["en", "ru"])("explains missing CS.MONEY liquidity signals in %s", async (language) => {
  await i18n.changeLanguage(language);
  const html = renderToStaticMarkup(<FlipRiskNotice level="unknown" sellMarketplace="csmoney" />);
  expect(html).toContain(i18n.t("flipRisk.csMoneyUnavailableBody"));
  expect(html).not.toContain(i18n.t("flipRisk.unknownBody"));
  const other = renderToStaticMarkup(<FlipRiskNotice level="unknown" sellMarketplace="csfloat" />);
  expect(other).toContain(i18n.t("flipRisk.unknownBody"));
});

it.each(["missing_ask", "missing_orders", "missing_sales"])("names the missing liquidity input: %s", (dataStatus) => {
  const html = renderToStaticMarkup(<FlipRiskNotice level="unknown" sellMarketplace="csfloat" dataStatus={dataStatus} />);
  expect(html).toContain(i18n.t(`flipRisk.${dataStatus}`));
  expect(html).not.toContain(i18n.t("flipRisk.unknownBody"));
});
