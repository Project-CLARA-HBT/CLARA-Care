// Reconstruct time to first successful completion independently using prefix sums.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {join} from 'node:path';

const [sealed, out] = process.argv.slice(2);
const raw = JSON.parse(readFileSync(sealed));
const methods = ['M0_regression','M1_stateless_property','M2_state_machine','M3_combined'];
const portfolio = 'regression_then_alternate';
const csv = name => {
  const [header, ...lines] = readFileSync(join(out, name), 'utf8').trimEnd().split('\n');
  return lines.map(line => Object.fromEntries(line.split(',').map((x,i) => [header.split(',')[i],x])));
};
const summary = csv('summary.csv');
const detail = csv('mutants.csv');
assert.equal(detail.length, 900);
const unique = new Set();
for (const r of detail) {
  unique.add([r.budget_us,r.mutant,r.method].join('/'));
  const trials = raw.executions.filter(x => x.result.mutant_id === r.mutant);
  const ordered = r.method === portfolio
    ? trials.filter(x => x.method !== methods[3]).sort((a,b) =>
        (a.hypothesis_seed ?? -1) - (b.hypothesis_seed ?? -1) || methods.indexOf(a.method) - methods.indexOf(b.method))
    : trials.filter(x => x.method === r.method).sort((a,b) => a.hypothesis_seed - b.hypothesis_seed);
  let t = 0;
  const prefix = ordered.map(x => ({finish: t += Math.round(x.result.runtime_ms * 1000),
    kill: x.result.returncode === 1}));
  const eligible = prefix.filter(x => x.finish <= +r.budget_us);
  const first = eligible.findIndex(x => x.kill);
  const status = first >= 0 ? 'detected' : eligible.length === prefix.length ? 'exhausted' : 'capped';
  assert.equal(r.exit, status);
  assert.equal(+r.detected, Number(first >= 0));
  assert.equal(+r.completed, first >= 0 ? first + 1 : eligible.length);
  assert.equal(+r.charged_us, first >= 0 ? eligible[first].finish : Math.min(t,+r.budget_us));
}
assert.equal(unique.size, 900);
assert.equal(summary.length, 20);
for (const s of summary) {
  const rows = detail.filter(r => r.budget_us === s.budget_us && r.method === s.method);
  assert.equal(rows.length,45);
  const positives = m => new Set(detail.filter(r => r.budget_us === s.budget_us && r.method === m && +r.detected).map(r => r.mutant));
  const m3 = positives(methods[3]), other = positives(s.method);
  assert.equal(other.size, +s.kills);
  assert.equal(rows.filter(r => r.exit === 'capped').length,+s.capped);
  assert.equal(rows.reduce((a,r)=>a+(+r.charged_us),0),+s.charged_us);
  assert.equal([...m3].filter(i => !other.has(i)).length,+s.m3_only);
  assert.equal([...other].filter(i => !m3.has(i)).length,+s.other_only);
}
console.log('Verified 900 distinct paired timing outcomes and 20 summary rows from the sealed source.');
