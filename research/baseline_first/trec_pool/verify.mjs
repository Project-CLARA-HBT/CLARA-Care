// Independent checks on published aggregates, qrel provenance and pair direction.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

const [cache, output] = process.argv.slice(2);
const summary = JSON.parse(fs.readFileSync(path.join(output, 'summary.json')));
const hash = file => createHash('sha256').update(fs.readFileSync(file)).digest('hex');
for (const [key, expected] of Object.entries(summary.sources)) {
  assert.equal(hash(path.join(cache, key)), expected);
}
const [columns, ...lines] = fs.readFileSync(path.join(output, 'runs.csv'), 'utf8').trimEnd().split('\n');
const header = columns.split(',');
const runs = lines.map(line => Object.fromEntries(line.split(',').map((v, i) => [header[i], v])));
assert.equal(runs.length, 143);
assert.equal(new Set(runs.map(r => r.file)).size, runs.length);
for (const run of runs) assert.equal(hash(path.join(cache, run.file)), run.sha256);

// NIST's original PDF score sheet for BBGhelani1, not fitted to these outputs.
const authorControl = runs.find(row => row.file === 'archive/round1/BBGhelani1');
assert.equal(authorControl.early_ndcg_cut_10, '0.6689');
assert.equal(authorControl.early_P_5, '0.8200');
for (const [metric, report] of Object.entries(summary.comparisons)) {
  const counts = { reversed: 0, preserved: 0, tie_early_only: 0, tie_late_only: 0, tie_both: 0 };
  for (const [i, a] of runs.entries()) {
    for (const b of runs.slice(i + 1)) {
      const sign = stage => Math.sign(Number(a[stage + metric]) - Number(b[stage + metric]));
      const e = sign('early_'), l = sign('late_');
      if (e === 0 && l === 0) counts.tie_both++;
      else if (e === 0) counts.tie_early_only++;
      else if (l === 0) counts.tie_late_only++;
      else if (e === l) counts.preserved++;
      else counts.reversed++;
    }
  }
  for (const [field, value] of Object.entries(counts)) assert.equal(report[field] ?? 0, value);
  assert.equal(report.pairs, runs.length * (runs.length - 1) / 2);
}
console.log('Checked all 143 run digests, input hashes, two NIST score controls and both pair tables.');
