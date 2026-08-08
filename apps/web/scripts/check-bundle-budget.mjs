import { readFile, stat } from "node:fs/promises";
import { join } from "node:path";

const root = new URL("..", import.meta.url).pathname;
const baselinePath = join(root, "scripts", "bundle-budget-baseline.json");
const artifactPath = join(root, ".next", "static");

async function directoryBytes(path) {
  const entry = await stat(path);
  if (entry.isFile()) return entry.size;
  const { readdir } = await import("node:fs/promises");
  const children = await readdir(path);
  let total = 0;
  for (const child of children) total += await directoryBytes(join(path, child));
  return total;
}

const baseline = JSON.parse(await readFile(baselinePath, "utf8"));
const actual = await directoryBytes(artifactPath);
const limit = Math.ceil(baseline.bytes * (1 + baseline.tolerance));
const result = {
  artifact: baseline.artifact,
  baselineBytes: baseline.bytes,
  actualBytes: actual,
  limitBytes: limit,
  deltaPercent: Number((((actual - baseline.bytes) / baseline.bytes) * 100).toFixed(2)),
};
console.log(JSON.stringify(result, null, 2));
if (actual > limit) {
  console.error(`Bundle budget exceeded: ${actual} > ${limit} bytes (baseline + ${baseline.tolerance * 100}%).`);
  process.exitCode = 1;
}
