// Reconstruct external source bytes independently and reconcile every observed frame.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync, writeFileSync} from 'node:fs';
import {join} from 'node:path';

const [source, frames, output] = process.argv.slice(2);
const raw = readFileSync(source);
const sha = createHash('sha256').update(raw).digest('hex');
assert.equal(sha, '5ce28a6e656bc88c1da29c983d243d5a81eb37de92698da3864d1cf02894ca24');
const dialogues = JSON.parse(raw);
function encode(value) {
  if (Array.isArray(value)) return '[' + value.map(encode).join(',') + ']';
  if (value !== null && typeof value === 'object')
    return '{' + Object.keys(value).sort().map(k => JSON.stringify(k) + ':' + encode(value[k])).join(',') + '}';
  return JSON.stringify(value);
}
function parse(stream) {
  const records = new Map();
  let offset = 0;
  while (offset < stream.length) {
    const d = stream.readUInt32BE(offset);
    const t = stream.readUInt32BE(offset + 4);
    const len = stream.readUInt32BE(offset + 8);
    const key = d + '/' + t;
    offset += 12;
    assert(!records.has(key));
    assert(len === 0xffffffff || offset + len <= stream.length);
    records.set(key, len === 0xffffffff ? null : stream.subarray(offset, offset + len));
    if (len !== 0xffffffff) offset += len;
  }
  return records;
}
const summaries = [];
const detail = ['stage,dialogue,turn,expected_status,source_bytes,glhs_status,glhs_bytes,signed_status,signed_bytes'];
for (const stage of ['retained','partial','expired']) {
  const observed = ['glhs','signed'].map(arm=>parse(readFileSync(join(frames, arm+'-'+stage+'.bin'))));
  const counts = observed.map(()=>({exact:0, omitted:0, missing:0, wrong:0, forbidden:0, bytes:0}));
  let wins = 0, losses = 0, ties = 0;
  for (const [d, dialog] of dialogues.entries()) {
    for (const [t, turn] of dialog.turns.entries()) {
      if (turn.speaker !== 'USER') continue;
      const key = d+'/'+t, sourceBytes = Buffer.from(encode({frames:turn.frames}));
      const allowed = stage === 'retained' || (stage === 'partial' && d % 3 !== 0);
      const fields = [];
      const ok = observed.map((arm,i)=>{
        assert(arm.has(key));
        const data = arm.get(key);
        arm.delete(key);
        const status = allowed
          ? data === null ? 'missing' : data.equals(sourceBytes) ? 'exact' : 'wrong'
          : data === null ? 'omitted' : 'forbidden';
        counts[i][status]++;
        counts[i].bytes += data?.length ?? 0;
        fields.push(status,data?.length ?? 0);
        return status === 'exact' || status === 'omitted';
      });
      if (ok[0] === ok[1]) ties++;
      else if (ok[0]) wins++;
      else losses++;
      detail.push([stage,d,t,allowed?'payload':'omitted',sourceBytes.length,...fields].join(','));
    }
  }
  for (const records of observed) assert.equal(records.size,0);
  summaries.push({stage,glhs:counts[0],signed:counts[1],glhs_wins:wins,ties,glhs_losses:losses});
}
writeFileSync(join(output,'queries.csv'),detail.join('\n')+'\n');
writeFileSync(join(output,'verified.json'),JSON.stringify({source_sha256:sha,dialogues:dialogues.length,stages:summaries},null,2)+'\n');
