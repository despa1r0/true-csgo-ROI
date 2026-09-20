import type { FlipRiskLevel, SellMode } from "@/shared/api";

export function flipRiskLevel(
  profitCents: number | null | undefined,
  sellMode: SellMode,
  liquidityScore: number | null | undefined,
): FlipRiskLevel | null {
  if (profitCents == null || profitCents <= 0 || sellMode !== "listing") return null;
  if (liquidityScore == null) return "unknown";
  if (liquidityScore < 35) return "critical";
  if (liquidityScore < 60) return "high";
  if (liquidityScore < 75) return "caution";
  return null;
}
