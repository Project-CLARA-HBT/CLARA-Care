import assert from 'node:assert/strict';
import fs from 'node:fs';

const [input, manifestFile] = process.argv.slice(2);
const manifest = JSON.parse(fs.readFileSync(manifestFile));
const [header, ...lines] = fs.readFileSync(input, 'utf8').trimEnd().split('\n');
const methods = header.split(',').slice(5);
const rows = lines.map(line => line.split(','));
assert.equal(rows.length, 6000);
const keys = new Set();
const queryTruth = new Map();
const scores = Object.fromEntries(methods.map(name => [name, {}]));
for (const row of rows) {
  const [seed, workload, ordinal, width, truth, ...predictions] = row;
  const token = [seed, workload, ordinal].join('/');
  assert(!keys.has(token));
  keys.add(token);
  assert(['joint', 'independent'].includes(workload));
  assert(+seed >= 11 && +seed <= 15 && +ordinal >= 0 && +ordinal < 600);
  assert.equal(+width, 3 + (+ordinal % 3));
  assert(+truth >= 0 && +truth <= manifest.source_rows);
  const identity = [workload, ordinal].join('/');
  if (queryTruth.has(identity)) assert.equal(queryTruth.get(identity), truth);
  queryTruth.set(identity, truth);
  assert.equal(predictions.length, methods.length);
  for (const [j, name] of methods.entries()) {
    const pred = +predictions[j];
    assert(Number.isFinite(pred) && pred >= 0 && pred <= manifest.source_rows + 1e-8);
    const loss = Math.abs(Math.log1p(pred) - Math.log1p(+truth));
    for (const group of ['macro', workload, +truth ? 'positive' : 'zero']) {
      const entry = scores[name][group] ??= {sum: 0, cases: 0};
      entry.sum += loss;
      entry.cases++;
    }
  }
}
for (const seed of Object.values(manifest.seeds)) {
  assert(seed.compressed_bytes <= manifest.cap);
  assert(seed.hybrid_tree_rows * 6 + manifest.tree_bytes <= manifest.cap);
  assert(seed.hybrid_independence_rows * 6 + seed.independence_bytes <= manifest.cap);
}
const result = Object.fromEntries(Object.entries(scores).map(([name, groups]) =>
  [name, Object.fromEntries(Object.entries(groups).map(([key, v]) =>
    [key, {mean: v.sum / v.cases, cases: v.cases}]))]));
console.log(JSON.stringify(result, null, 2));
