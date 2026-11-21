// Independently reconstruct hash, confidence and disagreement deferrals by prompt fold.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const root = process.argv[2];
for (const tag of ['pho-model', 'model']) {
  const rows = readFileSync(join(root, tag + '.jsonl'), 'utf8').trim().split('\n').map(JSON.parse);
  const summary = JSON.parse(readFileSync(join(root, tag + '.json'), 'utf8'));
  const folds = Array.from({ length: 5 }, () => []);
  for (const row of rows) {
    const digest = createHash('sha256').update(String(row.prompt)).digest();
    folds[Number(digest.readBigUInt64BE() % 5n)].push(row);
  }
  assert.equal(rows.length, 361);
  assert.equal(new Set(rows.map(r => r.key)).size, 361);
  assert.equal(new Set(rows.map(r => r.prompt)).size, 149);
  assert.equal(summary.total_beam_errors, rows.reduce((n, r) => n + r.beam_errors, 0));
  // A failed decoder receives its reference token length in errors by protocol.
  for (const mode of ['greedy', 'beam']) {
    const failed = rows.filter(r => mode + '_failure' in r);
    assert.equal(summary[mode + '_exceptions'], failed.length);
    for (const row of failed) assert.equal(row[mode + '_errors'], row.ref);
  }
  for (const [control, score] of Object.entries({
    hash_control: () => 0,
    confidence: row => -(row.confidence ?? -10),
    disagreement: row => row.disagreement ?? 1
  })) {
    const accepted = folds.flatMap(group => [...group].sort((a, b) =>
      score(a) - score(b) || (a.key < b.key ? -1 : 1)).slice(0, group.length - Math.floor(group.length / 5)));
    const outcome = summary.methods[control];
    assert.equal(accepted.length, outcome.accepted);
    assert.equal(accepted.reduce((n, r) => n + r.ref, 0), outcome.reference_tokens);
    assert.equal(accepted.reduce((n, r) => n + r.beam_errors, 0), outcome.errors);
  }
  for (const policy of Object.values(summary.methods)) {
    assert.equal(policy.accepted, summary.methods.hash_control.accepted);
    assert.equal(policy.fold_wer_pct.length, 5);
  }
  console.log(tag, 'verified 361 recordings, five prompt folds, and three reconstructed controls');
}
