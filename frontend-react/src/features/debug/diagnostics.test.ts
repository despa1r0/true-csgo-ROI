import { afterEach, expect, it } from "vitest";
import { dataDiagnostics, safeDiagnosticText } from "./diagnostics";
import { clearRequests, recordRequest, requestSnapshot, subscribeRequests } from "./requestLog";

afterEach(clearRequests);

it("shows independent backend sources and failures without exposing other payload fields", () => {
  const rows = dataDiagnostics({ marketplace: "CS.MONEY", cached: true, secret: "do-not-show",
    components: { sales: { status: "unavailable", fetched_at: "2026-10-03", error: "api_key=private-value HTTP 429" } },
    variants: [{ listing: { source: "wiki_market_summary", price_cents: 1000 }, errors: { csmoney: "Refresh failed" } }],
    credentials: { status: "do-not-show" } });
  const shown = JSON.stringify(rows);
  expect(shown).toContain("wiki_market_summary");
  expect(shown).toContain("Refresh failed");
  expect(shown).toContain("HTTP 429");
  expect(shown).toContain("2026-10-03");
  expect(shown).not.toContain("do-not-show");
  expect(shown).not.toContain("private-value");
  expect(shown).not.toContain("price_cents");
});

it("redacts credentials and URL queries from error text", () => {
  const shown = safeDiagnosticText('Authorization: Bearer auth-value; token="token-value" password=pass-value https://user:pass@host.test/api?api_key=url-value');
  for (const secret of ["auth-value", "token-value", "pass-value", "url-value", "user:pass"]) expect(shown).not.toContain(secret);
  expect(shown).toContain("https://host.test/api");
  expect(shown).toContain("[redacted]");
});

it("bounds request history and never stores request query strings", () => {
  let changes = 0;
  const unsubscribe = subscribeRequests(() => changes++);
  for (let i = 0; i < 105; i++) recordRequest({ at: i, method: "GET", path: "/api/skins/test?token=query-value", status: 503, duration: 4, error: "secret=error-value" });
  expect(requestSnapshot()).toHaveLength(100);
  expect(changes).toBe(105);
  expect(JSON.stringify(requestSnapshot())).not.toContain("query-value");
  expect(JSON.stringify(requestSnapshot())).not.toContain("error-value");
  unsubscribe();
  clearRequests();
  expect(changes).toBe(105);
  expect(requestSnapshot()).toHaveLength(0);
});
