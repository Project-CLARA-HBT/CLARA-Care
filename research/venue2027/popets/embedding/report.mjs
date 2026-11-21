import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const dir = process.argv[2];
const read = name => JSON.parse(fs.readFileSync(path.join(dir,name)));
const {arms,totals,complete_byte_equality:equality} = read('verified.json');
assert.equal(equality,true);
const rows=read('histories.json');
assert.equal(rows.length,512);
const seen=new Map();
const report=arms.map((arm,index)=>{
  const runs=rows.filter(r=>r.arm===arm);
  assert.equal(runs.length,128);
  const counts={forwards:0,hits:0,cancelled:0,elapsed:0};
  for(const r of runs){
    const key=JSON.stringify([r.dialogue,arm]);
    assert.ok(!seen.has(key) && Number.isInteger(r.dialogue) && r.dialogue>=0 && r.dialogue<128);
    assert.ok(r.elapsed_ns>0);
    seen.set(key,r);
    counts.forwards+=r.build;counts.hits+=r.hit;counts.cancelled+=r.deny;
    counts.elapsed+=r.elapsed_ns;
  }
  assert.equal(counts.forwards,totals[index].builds);
  assert.equal(counts.hits,totals[index].hits);
  assert.equal(counts.cancelled,totals[index].cancelled);
  assert.equal(counts.forwards+counts.hits+counts.cancelled,5177);
  assert.equal(totals[index].authorized_bytes,(counts.forwards+counts.hits)*1536);
  return {arm,forwards:counts.forwards,hits:counts.hits,cancelled:counts.cancelled,
    authorized_bytes:totals[index].authorized_bytes,total_seconds:counts.elapsed/1e9};
});
const contrasts=Object.fromEntries(arms.slice(0,3).map(arm=>{
  const count={fewer:0,equal:0,more:0};
  for(let i=0;i<128;i++){
    const diff=seen.get(JSON.stringify([i,'B4'])).build-seen.get(JSON.stringify([i,arm])).build;
    count[diff===0?'equal':diff>0?'more':'fewer']++;
  }
  return [arm,count];
}));
console.log(JSON.stringify({report,b4_forwards_per_dialogue:contrasts},null,2));
