import { describe, expect, it } from "vitest";

import { feeLabel, parseMoneyToCents } from "./format";

describe("parseMoneyToCents", () => {
  it("accepts English and Russian decimal separators", () => {
    expect(parseMoneyToCents("100.25")).toBe(10_025);
    expect(parseMoneyToCents("100,25")).toBe(10_025);
  });

  it("rejects negative, malformed, and over-precise values", () => {
    expect(parseMoneyToCents("-1")).toBeNull();
    expect(parseMoneyToCents("ten")).toBeNull();
    expect(parseMoneyToCents("1.001")).toBeNull();
  });
});

describe("feeLabel", () => {
  it("shows percentage and fixed server-owned fee parts", () => {
    expect(feeLabel({ percent: 2.8, fixed_cents: 30 })).toContain("2.8%");
    expect(feeLabel({ percent: 2.8, fixed_cents: 30 })).toContain("$0.30");
  });
});
