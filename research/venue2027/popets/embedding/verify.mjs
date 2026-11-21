import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createHash} from 'node:crypto';

const [source, trace] = process.argv.slice(2);
const raw = fs.readFileSync(source);
assert.equal(createHash('sha256').update(raw).digest('hex'), '5ce28a6e656bc88c1da29c983d243d5a81eb37de92698da3864d1cf02894ca24');
const frames = fs.readFileSync(trace);
const totals = Array.from({length:4}, () => ({requests:0, builds:0, hits:0, cancelled:0, authorized_bytes:0}));
let pos = 0;
for (const [i, dialogue] of JSON.parse(raw).entries()) {
  const visits = dialogue.turns.filter(t => t.speaker === 'USER').map(t => t.frames.flatMap(f =>
    Object.keys(f.state.slot_values).sort().map(s => JSON.stringify([f.service, s]))));
  const midpoint = Math.floor(visits.length / 2);
  const withdrawn = visits.slice(0,midpoint).flat()[0];
  const allows = visits.flatMap((v, j) => v.map(tag => j < midpoint || tag !== withdrawn));
  const payloads = Array.from({length:4}, () => []);
  for (let offset=0; offset<4; offset++) {
    const arm = (i+offset)%4;
    for (const [seq, allowed] of allows.entries()) {
      assert.equal(frames.readUInt16LE(pos),i);
      assert.equal(frames.readUInt16LE(pos+2),seq);
      assert.equal(frames[pos+4],arm);
      const op=frames[pos+5], len=frames.readUInt16LE(pos+6);
      assert.equal(len,allowed?1536:0);
      assert.ok(allowed ? op===1 || (arm!==1 && op===2) : op===0);
      const data=frames.subarray(pos+8,pos+8+len);
      assert.equal(data.length,len);
      if (allowed) {
        let norm=0;
        for(let k=0;k<384;k++) norm+=data.readFloatLE(k*4)**2;
        assert.ok(Math.abs(norm-1)<1e-4);
      }
      payloads[arm].push(data);
      totals[arm].requests++;
      totals[arm][['cancelled','builds','hits'][op]]++;
      totals[arm].authorized_bytes+=len;
      pos+=8+len;
    }
  }
  for (const arm of [0,2,3]) for (const [seq, data] of payloads[arm].entries()) assert.ok(data.equals(payloads[1][seq]));
}
assert.equal(pos,frames.length);
console.log(JSON.stringify({arms:['B1','B2','lazy','B4'],totals,complete_byte_equality:true},null,2));
