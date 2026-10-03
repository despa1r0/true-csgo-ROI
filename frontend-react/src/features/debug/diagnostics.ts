const privateField = /((?:authorization|api[_-]?key|token|password|secret|cookie)\s*[:=]\s*)(?:"[^"]*"|'[^']*'|[^\s,;]+)/gi;

export function safeDiagnosticText(value: unknown): string {
  return String(value ?? "")
    .replace(/https?:\/\/[^\s"'<>]+/g, (url) => {
      try { const parsed = new URL(url); return parsed.origin + parsed.pathname; }
      catch { return "[URL]"; }
    })
    .replace(/Bearer\s+[^\s,;]+/gi, "Bearer [redacted]")
    .replace(privateField, "$1[redacted]")
    .slice(0, 500);
}

export type DiagnosticRow = { field: string; value: string };
const fields = new Set(["marketplace", "marketplace_id", "source", "quote_source", "source_state",
  "fetched_at", "latest_at", "cached", "stale", "is_stale", "is_partial", "refresh_queued",
  "cache_ttl_seconds", "status", "error", "sales_error", "data_status", "liquidity_data_status",
  "buy_quote_source", "sell_quote_source", "sell_price_source"]);
const containers = new Set(["variants", "variant_states", "components", "markets", "listing",
  "stats", "liquidity", "sell_liquidity", "opportunities", "result"]);

/** Only display known diagnostic fields, never whole API payloads or credentials. */
export function dataDiagnostics(data: unknown): DiagnosticRow[] {
  const rows: DiagnosticRow[] = [];
  function visit(value: unknown, prefix: string, depth: number) {
    if (!value || typeof value !== "object" || depth > 6 || rows.length >= 120) return;
    if (Array.isArray(value)) {
      value.slice(0, 10).forEach((item, index) => visit(item, `${prefix}[${index}]`, depth + 1));
      return;
    }
    for (const [key, item] of Object.entries(value)) {
      if (rows.length >= 120) break;
      const field = `${prefix}.${key}`;
      if (fields.has(key) && item != null && typeof item !== "object") {
        rows.push({ field, value: safeDiagnosticText(item) });
      } else if (key === "errors" && item && typeof item === "object") {
        for (const [provider, error] of Object.entries(item)) {
          if (typeof error === "string") rows.push({ field: `${field}.${safeDiagnosticText(provider)}`, value: safeDiagnosticText(error) });
        }
      } else if (containers.has(key)) {
        if (["components", "markets"].includes(key) && item && typeof item === "object") {
          Object.entries(item).forEach(([name, entry]) => visit(entry, `${field}.${safeDiagnosticText(name)}`, depth + 1));
        } else visit(item, field, depth + 1);
      }
    }
  }
  visit(data, "data", 0);
  return rows.slice(0, 120);
}
