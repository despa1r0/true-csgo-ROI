export function formatUsd(cents: number | null | undefined, locale = "en-US") {
  if (cents == null || !Number.isFinite(cents)) return "—";
  return new Intl.NumberFormat(locale, { style: "currency", currency: "USD" }).format(cents / 100);
}

export function formatNumber(value: number | null | undefined, locale = "en-US", digits = 2) {
  if (value == null || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat(locale, { maximumFractionDigits: digits }).format(value);
}

export function formatDate(value: string | null | undefined, locale = "en-US") {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat(locale, { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }).format(date);
}

export function parseMoneyToCents(value: string) {
  const normalized = value.trim().replace(/\s/g, "").replace(",", ".");
  if (!normalized) return null;
  if (!/^\d+(?:\.\d{0,2})?$/.test(normalized)) return null;
  const amount = Number(normalized);
  if (!Number.isFinite(amount) || amount < 0 || amount > 10_000_000) return null;
  return Math.round(amount * 100);
}

export function feeLabel(rule?: { percent: number; fixed_cents: number } | null) {
  if (!rule) return "—";
  const parts = [];
  if (rule.percent) parts.push(`${rule.percent}%`);
  if (rule.fixed_cents) parts.push(formatUsd(rule.fixed_cents));
  return parts.length ? parts.join(" + ") : "0%";
}
