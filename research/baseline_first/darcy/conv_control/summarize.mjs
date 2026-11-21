import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';

function readRows(name) {
  const text = readFileSync(new URL(name, import.meta.url), 'utf8');
  return text.trim().split('\n').slice(1).map(line => line.split(','));
}

for (const arm of ['pressure', 'material']) {
  const curve = readRows('convergence.csv').filter(row => row[0] === arm);
  const rows = readRows('fields.csv').filter(row => row[1] === arm);
  assert.equal(curve.length, 35);
  assert.equal(rows.length, 128);
  rows.forEach(([index, , ...metrics], i) => {
    assert.equal(Number(index), 512 + i);
    assert(metrics.every(v => Number.isFinite(Number(v)) && Number(v) > 0));
  });
  const best = curve.reduce((a, b) => Number(a[2]) <= Number(b[2]) ? a : b);
  const means = [2, 3, 4].map(k => rows.reduce((sum, row) => sum + Number(row[k]), 0) / rows.length);
  console.log(arm, { first: curve[0], best, last: curve.at(-1), means });
}
