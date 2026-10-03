import { safeDiagnosticText } from "./diagnostics";

export type RequestEntry = { at: number; method: string; path: string; status: number | null; duration: number; error?: string };
let entries: RequestEntry[] = [];
const listeners = new Set<() => void>();

export function recordRequest(entry: RequestEntry) {
  entries = [{ ...entry, path: entry.path.split("?")[0] ?? "", error: entry.error ? safeDiagnosticText(entry.error) : undefined }, ...entries].slice(0, 100);
  listeners.forEach((listener) => listener());
}
export function requestSnapshot() { return entries; }
export function subscribeRequests(listener: () => void) {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}
export function clearRequests() { entries = []; listeners.forEach((listener) => listener()); }
