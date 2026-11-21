// Check the published primary comparison independently from the Python summary.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const [newLosses, kernelLosses, comparison] = process.argv.slice(2);
function readTable(path) {
  const [header, ...lines] = readFileSync(path, "utf8").trimEnd().split(/\r?\n/);
  const names = header.split(",");
  return lines.map(line => Object.fromEntries(line.split(",").map((v, i) => [names[i], v])));
}
function series(path, name) {
  const data = readTable(path).filter(r => r.method === name);
  const result = new Map(data.map(r => [[r.station, r.week, r.start, r.hours].join("/"), Number(r.mae)]));
  assert.equal(data.length, 174);
  assert.equal(result.size, data.length);
  return result;
}
const selected = series(newLosses, "validation_selected");
const ar = series(newLosses, "autoregressive");
const kernel = series(kernelLosses, "temperature_kernel");
assert.deepEqual(ar, selected);
let wins = 0, losses = 0, kernelTotal = 0, selectedTotal = 0;
for (const [key, value] of selected) {
  const baseline = kernel.get(key);
  assert.ok(Number.isFinite(baseline));
  wins += Number(value < baseline);
  losses += Number(value > baseline);
  kernelTotal += baseline;
  selectedTotal += value;
}
const table = readTable(comparison);
const primary = table.find(row => row.method === "temperature_kernel");
const candidate = table.find(row => row.method === "validation_selected");
assert.equal(wins, Number(primary.selected_wins));
assert.equal(losses, Number(primary.selected_losses));
assert.ok(Math.abs(Number(primary.macro_mae) - kernelTotal / kernel.size) < 1e-8);
assert.ok(Math.abs(Number(candidate.macro_mae) - selectedTotal / selected.size) < 1e-8);
assert.ok(Math.abs(Number(primary.relative_reduction_vs_method) - (1 - selectedTotal / kernelTotal)) < 1e-8);
console.log(`Verified ${wins} wins and ${losses} losses relative to the temperature kernel.`);
