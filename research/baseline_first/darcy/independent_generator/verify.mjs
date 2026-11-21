import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const summary = JSON.parse(readFileSync(new URL('./summary.json', import.meta.url)));
const rows = readFileSync(new URL('./fields.csv', import.meta.url), 'utf8').trim().split('\n').slice(1);
assert.equal(rows.length, 128 * 6);
for (const [arm, result] of Object.entries(summary)) {
  const values = rows.filter(row => row.split(',')[1] === arm).map(row => row.split(','));
  assert.deepEqual(values.map(row => Number(row[0])), Array.from({length: 128}, (_, i) => i + 512));
  for (let i = 0; i < 3; i++) {
    const mean = values.reduce((sum, row) => sum + Number(row[i + 2]), 0) / values.length;
    assert.ok(Math.abs(mean - result.means[i]) < 1e-12);
  }
}
