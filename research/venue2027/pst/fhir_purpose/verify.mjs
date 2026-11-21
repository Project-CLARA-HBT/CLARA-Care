// Independent readback directly from HL7 JSON. No Python study imports.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {join} from 'node:path';
const [scratch, manifest, evidence] = process.argv.slice(2);
const json = path => JSON.parse(readFileSync(path, 'utf8'));
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const refs = json(manifest);
const measured = json(evidence);
const official = refs.filter(r => /-example[^/]*\.json$/.test(r.url)).map(r => r.url.split('/').pop()).sort();
assert.equal(official.length,13);
assert.deepEqual(measured.rows.map(r=>r.source),official);
for (const ref of refs) assert.equal(hash(readFileSync(join(scratch, ref.url.split('/').pop()))), ref.sha256);
const terms = json(join(scratch,'CodeSystem-v3-ActReason.json'));
const parents = new Map(terms.concept.map(c=>[c.code,(c.property||[]).filter(p=>p.code==='subsumedBy').map(p=>p.valueCode)]));
function member(code, seen=new Set()) {
  if (seen.has(code)) throw Error('cycle');
  return (parents.get(code)||[]).some(p => p==='PurposeOfUse' || member(p,new Set([...seen,code])));
}
assert.equal([...parents.keys()].filter(c=>member(c)).length, measured.purpose_codes_in_terminology);
const groups = {};
for (const row of measured.rows) {
  const resource = json(join(scratch,row.source));
  const counts = {};
  const flags = {agent:false,event:false};
  function read(obj, scope) {
    if (!Object.hasOwn(obj,'authorization')) return null;
    counts[scope+'_declarations']=(counts[scope+'_declarations']||0)+obj.authorization.length;
    return obj.authorization.map(concept=>{
      if (!Object.hasOwn(concept,'coding')) return null;
      return concept.coding.map(c=>{
        const valid = c.system===terms.url && (c.version===undefined || c.version===terms.version) && member(c.code);
        const name=scope+(valid?'_purpose_codings':'_unclassified_codings');
        counts[name]=(counts[name]||0)+1;
        if (valid) flags[scope]=true;
        return [c.system??null,c.version??null,c.code??null];
      });
    });
  }
  const result=[read(resource,'event'), resource.agent.map(agent=>read(agent,'agent'))];
  const group=flags.event ? (flags.agent?'both':'event_only') : (flags.agent?'agent_only':'neither');
  assert.deepEqual(row,{source:row.source,scope_group:group,
    projection_sha256:hash(JSON.stringify(result)),...counts});
  groups[group]=(groups[group]||0)+1;
}
assert.deepEqual(groups,measured.scope_counts);
console.log('Verified 13 complete scoped answers, terminology memberships, per-scope counts and 17 source digests.');
