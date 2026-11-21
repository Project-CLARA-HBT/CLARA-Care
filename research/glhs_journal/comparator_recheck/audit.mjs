// Read only the archived experiment and its pinned runner; never import the SUT.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../../../', import.meta.url));
const bundle = join(root, 'research/glhs_journal/q4_r4/evidence/E16_five_way_comparator');
const read = name => readFileSync(join(bundle, name));
const load = name => JSON.parse(read(name));
const sha = data => createHash('sha256').update(data).digest('hex');
const seal = load('seal.json');
for (const [name, hash] of Object.entries(seal.artifact_inventory)) {
  assert.equal(sha(read(name)), hash, name);
}
const sourceRev = load('code_manifest.json').parent_harness_sha;
const runner = execFileSync('git', ['show', sourceRev + ':evaluation/glhs_r4_eval/run_e16.py'],
                            {cwd:root,encoding:'utf8'});
const rubric = runner.split('def compute_objective_reconstructability_score')[1].split('\ndef ')[0];
assert.match(rubric, /\(arm_id: str\) -> float:/);
assert.match(rubric, /return scores\.get\(arm_id, 0\.0\)/);
assert.match(runner, /"forensic_score": compute_objective_reconstructability_score\(arm_id\)/);
const assignedScores = Object.fromEntries([...rubric.matchAll(/"(C\d)": (\d+)\.0/g)].map(m=>[m[1], Number(m[2])]));
const expectedArms = ['C0', 'C1', 'C2', 'C3', 'C4'];
const rows = read('raw/runs.jsonl').toString().trimEnd().split('\n').map(JSON.parse);
const schedules = new Map();
for (const r of rows) {
  assert.equal(typeof r.admitted, 'boolean');
  assert.equal(typeof r.is_valid_schedule, 'boolean');
  const s = schedules.get(r.schedule_id) ?? new Map();
  assert.ok(!s.has(r.arm_id), 'duplicate arm in schedule ' + r.schedule_id);
  s.set(r.arm_id, r);
  schedules.set(r.schedule_id, s);
}
const groups = new Map();
const armTotals = Object.fromEntries(expectedArms.map(a=>[a,{false_admissions:0,false_rejections:0}]));
for (const [id, arms] of schedules) {
  assert.deepEqual([...arms.keys()].sort(), expectedArms, id);
  const r3 = arms.get('C3'), r4 = arms.get('C4');
  const type = r3.schedule_type;
  const g = groups.get(type) ?? {ids:0, valid: r3.is_valid_schedule,
    c4_only_correct:0, c3_only_correct:0, both_correct:0, both_wrong:0,
    c4_wall_time_lower:0, c4_wall_time_equal:0, c4_wall_time_higher:0};
  groups.set(type, g);
  assert.equal(g.valid, type === 'CLEAN_VALID');
  for (const r of arms.values()) {
    assert.equal(r.schedule_type, type);
    assert.equal(r.is_valid_schedule, g.valid);
    if (!g.valid && r.admitted) armTotals[r.arm_id].false_admissions++;
    if (g.valid && !r.admitted) armTotals[r.arm_id].false_rejections++;
    assert.ok(Number.isFinite(r.cpu_latency_us) && r.cpu_latency_us > 0);
  }
  g.ids++;
  const c3 = r3.admitted === g.valid, c4 = r4.admitted === g.valid;
  if (c3 === c4) g[c3 ? 'both_correct' : 'both_wrong']++;
  else g[c3 ? 'c3_only_correct' : 'c4_only_correct']++;
  if (r4.cpu_latency_us < r3.cpu_latency_us) g.c4_wall_time_lower++;
  else if (r4.cpu_latency_us > r3.cpu_latency_us) g.c4_wall_time_higher++;
  else g.c4_wall_time_equal++;
}
const published = load('derived/summary.json');
for (const a of expectedArms) {
  assert.equal(published.arms[a].forensic_lineage_reconstructability_score, assignedScores[a]);
}
const fields = [...new Set(rows.flatMap(Object.keys))].sort();
const witnessed = {
  source_revision: sourceRev, seal_sha256: sha(read('seal.json')),
  sealed_files_checked: Object.keys(seal.artifact_inventory).length, rows: rows.length,
  ids: schedules.size, templates: groups.size,
  required_backend: load('protocol.json').backend_requirement,
  observed_endpoint: load('backend_attestation.json').endpoint,
  by_template: Object.fromEntries(groups), by_arm: armTotals, source_assigned_scores: assignedScores,
  available_raw_fields: fields,
};
console.log(JSON.stringify(witnessed, null, 2));
