import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const evidence = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const {decisions, targets} = evidence;
assert.equal(decisions.length, 27);
assert.equal(new Set(decisions.map(r => r.request)).size, decisions.length);
assert.equal(targets.length, 14);

for (const row of decisions) {
  const reached = targets.filter(t => Object.hasOwn(t.rows, row.request));
  assert.deepEqual(reached, targets.slice(0, reached.length));
  let expected = 'Deny';
  for (const [i, t] of reached.entries()) {
    const bits = t.rows[row.request];
    assert.equal(bits.length, 2);
    assert(bits.every(b => b === false || b === true || b === null));
    if (bits.every(b => b === true)) {
      expected = 'Permit';
      assert.equal(i + 1, reached.length);
    } else if (!bits.includes(false)) {
      expected = 'IDP';
    }
  }
  if (expected !== 'Permit') assert.equal(reached.length, 14);
  assert.equal(expected, row.published);
  assert.equal(expected, row.replay);
}

for (const target of targets) {
  const observed = new Set(Object.values(target.rows).map(JSON.stringify));
  for (const point of [[true,true], [false,true], [true,false]]) {
    assert(observed.has(JSON.stringify(point)));
  }
  assert.deepEqual(Object.keys(target.witnesses), ['0','1']);
  for (const [index, requests] of Object.entries(target.witnesses)) {
    const [a,b] = requests.map(name => target.rows[name]);
    assert(!a.includes(null) && !b.includes(null));
    assert.notEqual(a[Number(index)],b[Number(index)]);
    assert.equal(a[1-Number(index)],true);
    assert.equal(b[1-Number(index)],true);
  }
  const errors = Object.entries(target.rows)
    .filter(([,bits]) => bits.includes(null) && !bits.includes(false))
    .map(([name]) => name);
  assert.deepEqual(errors,target.errors);
  assert.equal(errors.length,1);
}
console.log('Verified 27 labels, 28 condition-independence obligations and 14 reachable target error obligations.');
