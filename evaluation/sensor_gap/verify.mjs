// Independently recompute both interpolation controls from the original hourly series.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createHash } from "node:crypto";

const [input, losses] = process.argv.slice(2);
const identities = {
  ETTh1: "f18de3ad269cef59bb07b5438d79bb3042d3be49bdeecf01c1cd6d29695ee066",
  ETTh2: "a3dc2c597b9218c7ce1cd55eb77b283fd459a1d09d753063f944967dd6b9218b",
};
const stations = new Map();
for (const [name, hash] of Object.entries(identities)) {
  const bytes = readFileSync(join(input, name + ".csv"));
  assert.equal(createHash("sha256").update(bytes).digest("hex"), hash);
  const lines = bytes.toString().trimEnd().split(/\r?\n/).slice(1);
  const starts = new Map();
  const temperature = lines.map((line, i) => {
    const fields = line.split(",");
    starts.set(fields[0], i);
    return Number(fields.at(-1));
  });
  stations.set(name, { starts, temperature });
}
const groups = new Map();
const rows = readFileSync(losses, "utf8").trimEnd().split(/\r?\n/).slice(1);
for (const line of rows) {
  const [name, week, date, duration, method, maeText, squaredText] = line.split(",");
  const { starts, temperature } = stations.get(name);
  const i = starts.get(date);
  const length = Number(duration);
  assert.ok([6, 24, 72].includes(length));
  assert.equal(Math.floor(i / 168), Number(week));
  assert.ok(Number(week) >= 73 && Number(week) <= 101);
  assert.equal(Math.floor((i + length - 1) / 168), Number(week));
  const key = [name, week, duration].join("/");
  if (!groups.has(key)) groups.set(key, { date, methods: new Set() });
  const group = groups.get(key);
  assert.equal(group.date, date);
  assert.ok(!group.methods.has(method));
  group.methods.add(method);
  const mae = Number(maeText), squared = Number(squaredText);
  assert.ok(mae >= 0 && squared >= 0 && Number.isFinite(mae + squared));
  if (method !== "linear" && method !== "seasonal") continue;
  let sum = 0, sumSquares = 0;
  const shift = Math.ceil(length / 24) * 24;
  for (let k = 0; k < length; k++) {
    const a = temperature[i - 1], b = temperature[i + length];
    const pred = method === "linear" ? a + (b - a) * (k + 1) / (length + 1)
      : (temperature[i + k - shift] + temperature[i + k + shift]) / 2;
    const err = pred - temperature[i + k];
    sum += Math.abs(err);
    sumSquares += err * err;
  }
  assert.ok(Math.abs(sum / length - mae) < 1e-9);
  assert.ok(Math.abs(sumSquares - squared) < 1e-8);
}
assert.equal(groups.size, 29 * 2 * 3);
for (const {methods} of groups.values())
  assert.deepEqual(methods, new Set(["linear", "seasonal", "direct", "residual"]));
console.log(`Verified both control predictions and all four arms over ${groups.size} outages.`);
