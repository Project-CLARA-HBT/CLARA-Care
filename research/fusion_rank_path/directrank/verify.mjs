import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';

const executable = process.argv[2];
let fixtures = 0;
let fullSorts = 0;
function verify(left, right, k, expectedSequence) {
  const ids = left.map((_, index) => index);
  const input = ['fixture case ' + ids.length, ...ids.map(i => [left[i], right[i], 1].join(' '))].join('\n');
  const run = spawnSync(executable, [String(k)], {input, encoding: 'utf8'});
  assert.equal(run.status, 0, run.stderr);
  const expected = ids.map(() => []);
  const sequence = [];
  for (let w = 0; w <= 65535; ++w) {
    const scores = ids.map(i => (65535-w)*left[i] + w*right[i]);
    const ordered = [...ids].sort((a,b) => scores[b]-scores[a] || a-b);
    for (let i = 0; i < ordered.length; ++i) {
      const rank = Math.min(i+1, k+1);
      const curve = expected[ordered[i]];
      if (!curve.length || curve.at(-1)[1] !== rank) curve.push([w,rank]);
    }
    if (expectedSequence) {
      const top = ordered.slice(0,k).map(id => id+1).join('');
      if (top !== sequence.at(-1)) sequence.push(top);
    }
  }
  fullSorts += 65536;
  assert.equal(run.stdout, expected.map((curve,id) =>
    ['fixture','case',id,...curve.map(change => change.join(':'))].join('\t')+'\n').join(''));
  if (expectedSequence) assert.deepEqual(sequence,expectedSequence);
  ++fixtures;
}
// The authors tabulate the sequence without numeric coefficients. These lines
// independently realize the same top-three order on both sides of each event.
verify([722,677,574,532,324], [191,393,337,315,745], 3,
       ['123','213','215','251','521','523']);
verify([914,760,664,339,102], [134,618,505,913,773], 3,
       ['123','213','231','234','243','423','425','452']);
verify([5,5,5,5],[7,7,7,7],10);
verify([65535,0,65535,0,1], [0,65535,0,65535,1],1);
verify([11,10,9,8,7,6,5,4,3,2,1,0], [0,2,4,6,8,10,12,14,16,18,20,22], 10);
let seed = 786267945;
function random() {
  seed = (Math.imul(1664525, seed) + 1013904223) >>> 0;
  return seed;
}
for (let trial = 0; trial < 20; ++trial) {
  const n = 2 + (random() % 16);
  const max = trial % 2 ? 65536 : 7;
  verify(Array.from({length:n}, () => random() % max),
         Array.from({length:n}, () => random() % max), 1 + random() % n);
}
console.log(JSON.stringify({fixtures, fullSorts, paperTablesMatched: 2}));
