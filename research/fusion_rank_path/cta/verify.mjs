// Full stable sort at every integer weight, independent of skyline and cell bounds.
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';

let seed = 4709;
function random(n) {
  seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
  return seed % n;
}
const cases = [];
function add(rows, ids, k, last) { cases.push({rows, ids, k, last}); }
add([[3, 8], [9, 4], [8, 3], [4, 3], [5, 5]], [4], 3, 65535);
add(Array.from({length: 42}, (_, i) => [i % 7, 6 - (i % 7)]),
    [0, 1, 5, 6, 7, 8, 40], 10, 65535);
add([[0, 0]], [0], 10, 3);
add([[0, 0]], [], 1, 3);
for (let trial = 0; trial < 64; ++trial) {
  const n = [17, 100, 300, 513][trial % 4];
  const rows = Array.from({length: n}, () => [random(27), random(23)]);
  add(rows, [...new Set(Array.from({length: 12}, () => random(n)))],
      [1, 3, 10, n + 1][trial % 4], 93);
}
const input = cases.flatMap(({rows, ids, k, last}) =>
  [`${rows.length} ${ids.length} ${k} ${last}`, ...rows.map(r => r.join(' ')), ids.join(' ')]).join('\n');
const run = spawnSync(process.argv[2], [], {input, encoding: 'utf8'});
assert.equal(run.status, 0, run.stderr);
const outputs = run.stdout.trim().split('\n');
assert.equal(outputs[0].trim(), '0:3 26214:4 39322:3 52429:2');
let count = 0;
let cellWeights = 0;
for (const {rows, ids, k, last} of cases) {
  const curves = ids.map(() => []);
  const order = rows.map((_, i) => i);
  const ranks = new Array(rows.length), scores = new Array(rows.length);
  for (let w = 0; w <= last; ++w) {
    for (let i = 0; i < rows.length; ++i) scores[i] = (last - w) * rows[i][0] + w * rows[i][1];
    order.sort((i, j) => scores[j] - scores[i] || i - j);
    for (let i = 0; i < order.length; ++i) ranks[order[i]] = Math.min(i + 1, k + 1);
    ids.forEach((id, i) => {
      const rank = ranks[id];
      if (!curves[i].length || curves[i].at(-1)[1] !== rank) curves[i].push([w, rank]);
    });
  }
  cellWeights += (last + 1) * ids.length;
  for (const curve of curves)
    assert.equal(outputs[count++].trim(), curve.map(change => change.join(':')).join(' '));
}
assert.equal(count, outputs.length);
console.log(JSON.stringify({queries: cases.length, curves: count, integer_ranks: cellWeights}));
