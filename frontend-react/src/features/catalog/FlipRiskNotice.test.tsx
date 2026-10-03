// @vitest-environment jsdom
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, expect, it } from "vitest";
import i18n from "@/shared/i18n";
import { FlipRiskNotice } from "./FlipRiskNotice";

afterEach(async () => { await i18n.changeLanguage("en"); });

it.each(["en", "ru"])("keeps unrated liquidity neutral and concise in %s", async (language) => {
  await i18n.changeLanguage(language);
  const html = renderToStaticMarkup(<FlipRiskNotice level="unknown" score={90} compact />);
  expect(html).toContain(i18n.t("flipRisk.unknownTitle"));
  expect(html).not.toContain("90");
  expect(html).not.toMatch(/riskHigh|riskCritical|riskCaution/);
  expect(html).not.toContain(i18n.t("flipRisk.unknownBody"));
  expect(html).toMatch(/^<span/);
});

it.each(["high", "critical"] as const)("preserves a measured %s liquidity warning", (level) => {
  const html = renderToStaticMarkup(<FlipRiskNotice level={level} score={30} />);
  expect(html).toContain(i18n.t(`flipRisk.${level}Title`));
  expect(html).toContain("30/100");
  expect(html).not.toContain(i18n.t(`flipRisk.${level}Body`));
});

it("does not show a warning when the risk calculation is absent", () => {
  expect(renderToStaticMarkup(<FlipRiskNotice level={null} />)).toBe("");
});
