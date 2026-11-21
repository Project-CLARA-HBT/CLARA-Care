import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

for (const filename of ['run1', 'tallied1', 'tallied2', 'tallied3']) {
  const evidence = JSON.parse(fs.readFileSync(path.join(process.argv[2], filename + '.json')));
  assert.equal(evidence.rules.length, 14);
  assert.equal(evidence.reference.length, 27);
  for (const [, published, original] of evidence.reference) assert.equal(original, published);
  const outputs = new Map(evidence.generated.map(([id, observed, derived]) => {
    assert.equal(observed, derived);
    return [id, observed];
  }));
  assert.equal(outputs.size, 25);
  assert.equal(evidence.byte_distinct, 25);
  assert.equal(evidence.attribute_map_distinct, 25);
  const independentlyScored = new Map([...outputs.keys()].map(id => [id, 'Deny']));
  for (const rule of evidence.rules) {
    const rows = rule.truths_by_request;
    const active = [...independentlyScored].filter(([, score]) => score !== 'Permit');
    assert.deepEqual(Object.keys(rows).sort(), active.map(([id]) => id).sort());
    const observable = new Set(Object.values(rows).map(JSON.stringify));
    for (const point of [[true,true], [true,false], [false,true]])
      assert(observable.has(JSON.stringify(point)));
    const errors = [];
    for (const [id, bits] of Object.entries(rows)) {
      if (bits.every(b => b === true)) independentlyScored.set(id, 'Permit');
      else if (bits.includes(null) && !bits.includes(false)) {
        errors.push(id);
        independentlyScored.set(id, 'IDP');
      }
    }
    assert(errors.length > 0);
    assert.deepEqual(errors, rule.error_witnesses);
  }
  assert.deepEqual(outputs, independentlyScored);
  assert.deepEqual(evidence.solver_calls, {'smt.string_solver=z3str3 -smt2 ./Z3_input': 25});
  if (filename !== 'run1') assert.deepEqual(evidence.method_entries,
    {generation_TargetEvaluate: 217, reference_evaluate: 27, replay_evaluate: 25});
  console.log(filename, 'verified 27 reference decisions, 25 generated decisions, 28 MC/DC and 14 error obligations');
}
