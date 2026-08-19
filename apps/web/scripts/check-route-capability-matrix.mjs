import { readdir, readFile } from "node:fs/promises";
import { join, relative } from "node:path";

const appRoot = new URL("../app/", import.meta.url).pathname;
const matrixPath = new URL("../../../docs/ui-modernization/route-capability-matrix.md", import.meta.url).pathname;

async function pageRoutes(directory) {
  const routes = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const full = join(directory, entry.name);
    if (entry.isDirectory()) routes.push(...(await pageRoutes(full)));
    else if (entry.name === "page.tsx") {
      const route = relative(appRoot, full)
        .replaceAll("\\", "/")
        .replace(/(?:^|\/)\([^)]+\)/g, "")
        .replace(/(?:^|\/)page\.tsx$/, "")
        .replace(/^\/+/, "");
      routes.push(route ? `/${route}` : "/");
    }
  }
  return routes.sort();
}

const source = await pageRoutes(appRoot);
const markdown = await readFile(matrixPath, "utf8");
const listed = [...markdown.matchAll(/\| `([^`]+)` \|/g)].map((match) => match[1]).sort();
const missing = source.filter((route) => !listed.includes(route));
const extra = listed.filter((route) => !source.includes(route));
if (missing.length || extra.length || new Set(listed).size !== listed.length) {
  console.error(JSON.stringify({ missing, extra, duplicateCount: listed.length - new Set(listed).size }, null, 2));
  process.exit(1);
}
console.log(`Route capability matrix matches ${source.length} page routes.`);
