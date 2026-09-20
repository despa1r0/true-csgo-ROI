import { describe, expect, it } from "vitest";

import { flipRiskLevel } from "./flipRisk";

describe("flipRiskLevel", () => {
  it("uses graded sell-side liquidity for profitable listing exits", () => {
    expect(flipRiskLevel(100, "listing", 30)).toBe("critical");
    expect(flipRiskLevel(100, "listing", 45)).toBe("high");
    expect(flipRiskLevel(100, "listing", 68)).toBe("caution");
    expect(flipRiskLevel(100, "listing", 80)).toBeNull();
    expect(flipRiskLevel(100, "listing", null)).toBe("unknown");
  });

  it("does not apply ask-sale warnings to a loss or an immediate bid sale", () => {
    expect(flipRiskLevel(-10, "listing", 30)).toBeNull();
    expect(flipRiskLevel(100, "fast_buy", 30)).toBeNull();
  });
});
