// Check complete paired rounds against the locked 20% margin.
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const dir = process.argv[2];
if (!dir) throw new Error("Usage: node report.mjs RESULT_DIRECTORY");
const read = name => fs.readFileSync(path.join(dir, name), "utf8").trimEnd();
const ingest = JSON.parse(read("materialized.json"));
const oracle = JSON.parse(read("verification.json"));
const sources = ["SciFact", "NFCorpus"];
const totalQueries = sources.reduce((n, s) => n + ingest.sources[s].queries, 0);
const totalPositives = sources.reduce((n, s) => n + ingest.sources[s].retained_positive_pairs, 0);
assert.equal(totalQueries, 623);
assert.equal(oracle.external.queries, totalQueries);
assert.equal(oracle.external.positives, totalPositives);
assert.equal(oracle.external.ranks, totalPositives * 65536);
assert.equal(oracle.external.full_sorts, 9 * totalQueries);
assert.equal(ingest.overlap.length, 2 * 3 * 3 * 3);
const roundData = new Map(sources.map(s => [s, new Map()]));
const [header, ...lines] = read("timings.csv").split("\n");
assert.equal(lines.length, 240);
assert.equal(header, "source,round,position,method,ns");
for (const line of lines) {
  const [name, ...cols] = line.split(",");
  const [round, position, method, ns] = cols.map(Number);
  assert.ok(Number.isInteger(round) && round >= 1 && round <= 12);
  assert.ok(Number.isInteger(ns) && ns > 0);
  assert.ok([position, method].every(i => Number.isInteger(i) && i >= 0 && i < 10));
  const rounds = roundData.get(name);
  if (!rounds.has(round)) rounds.set(round, { time: new Map(), order: new Set() });
  const data = rounds.get(round);
  assert.ok(!data.time.has(method) && !data.order.has(position));
  data.time.set(method, ns);
  data.order.add(position);
}
console.log("source,method,median_saving_pct,order2_pct,order11_pct,faster,equal,slower");
for (const [source, rounds] of roundData) {
  assert.equal(rounds.size, 12);
  assert.ok([...rounds.values()].every(r => r.time.size === 10 && r.order.size === 10));
  for (let method = 0; method < 10; method++) {
    if (method === 7) continue;
    const savings = [...rounds.values()].map(({time}) => 100 * (1 - time.get(7) / time.get(method)));
    savings.sort((a, b) => a - b);
    const values = [(savings[5] + savings[6]) / 2, savings[1], savings[10]];
    const signs = [1, 0, -1].map(sign => savings.filter(d => Math.sign(d) === sign).length);
    console.log([source, method, ...values.map(d => d.toFixed(3)), ...signs].join(","));
  }
}
