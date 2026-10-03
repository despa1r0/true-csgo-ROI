import { readdir, readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = process.argv[2] ? path.resolve(process.argv[2]) : fileURLToPath(new URL("../../frontend-react/dist/", import.meta.url));
const forbidden = /TRUEROI_DEV_DIAGNOSTICS|Data diagnostics|Диагностика данных|Browser query cache|\[redacted\]/;
async function check(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) await check(file);
    else if (/\.(js|css|html|map)$/.test(entry.name)) {
      if (/DebugPage|debug\.module|requestLog/.test(entry.name) || forbidden.test(await readFile(file, "utf8"))) {
        throw new Error(`Development diagnostics leaked into production: ${path.relative(root, file)}`);
      }
    }
  }
}
await check(root);
console.log("Production bundle: no development diagnostics, routes, request log or debug assets");
