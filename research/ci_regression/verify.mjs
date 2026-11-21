// Independently reconstruct first-attempt denominators, deadlines and aggregate metrics.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const [source, results] = process.argv.slice(2);
function rows(file, separator) {
  const [header, ...lines] = fs.readFileSync(file, 'utf8').trimEnd().split(/\r?\n/);
  const fields = header.split(separator);
  return lines.map(line => Object.fromEntries(line.split(separator).map((value,i) => [fields[i],value])));
}

function median(values) {
  values.sort((a,b) => a-b);
  const i = Math.floor(values.length/2);
  return values.length % 2 ? values[i] : (values[i-1] + values[i])/2;
}

for (const stage of ['validation','test']) {
  const summary = JSON.parse(fs.readFileSync(path.join(results, stage+'_summary.json')));
  const scores = rows(path.join(results, stage+'_cycles.csv'), ',');
  for (const project of ['iofrol','paintcontrol']) {
    const cycles = new Map();
    for (const row of rows(path.join(source, project+'.csv'), ';')) {
      const id = Number(row.Cycle);
      if (!cycles.has(id)) cycles.set(id, new Map());
      const tests = cycles.get(id);
      if (!tests.has(row.Name) || Number(tests.get(row.Name).Id) > Number(row.Id)) tests.set(row.Name,row);
    }
    const history = new Map(), expected = new Map();
    const cycleOrder = [...cycles.keys()].sort((a,b) => a-b);
    cycleOrder.forEach((cycle, ordinal) => {
      const cases = [...cycles.get(cycle).values()];
      const middle = history.size ? median([...history.values()]) : 1;
      const budget = cases.reduce((acc,row) => acc + (history.get(row.Name) ?? middle), 0)/4;
      const failures = cases.reduce((acc,row) => acc+Number(row.Verdict),0);
      const size = cycleOrder.length;
      const split = ordinal < Math.floor(size*0.6) ? 'train' : ordinal < Math.floor(size*0.8) ? 'validation' : 'test';
      if (stage === split) expected.set(cycle,{budget,failures,count:cases.length});
      for (const row of cases) history.set(row.Name,Number(row.Duration));
    });
    for (const [method, metrics] of Object.entries(summary)) {
      const group = scores.filter(r => r.project === project && r.method === method);
      assert.equal(new Set(group.map(r=>Number(r.cycle))).size,expected.size);
      assert.equal(group.length,expected.size);
      let total=0, any=0, n=0;
      for (const row of group) {
        const {budget, failures, count} = expected.get(Number(row.cycle));
        assert.equal(Number(row.budget),budget);
        assert.equal(Number(row.failures),failures);
        assert.equal(Number(row.tests),count);
        assert.ok(Number(row.prefix_cost)<=budget && Number(row.prefix)<=count);
        assert.ok(Number(row.found)<=Math.min(failures, Number(row.prefix)));
        if (!failures) continue;
        n++;
        total+=Number(row.found)/failures;
        any+=Number(row.found)>0;
      }
      const claim=metrics.projects[project];
      assert.equal(claim.zero_failure,group.length-n);
      assert.ok(Math.abs(total/n-claim.recall)<1e-12 && Math.abs(any/n-claim.any_failure)<1e-12);
    }
  }
  for (const m of Object.values(summary)) assert.ok(Math.abs((m.projects.iofrol.recall+m.projects.paintcontrol.recall)/2-m.macro)<1e-12);
  console.log(stage,'verified',scores.length,'arm-cycle observations');
}
