// Report paired descriptive changes on the same FLEURS development recordings.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const [cpuDir, cudaDir] = process.argv.slice(2);
if (!cpuDir || !cudaDir) throw new Error('Expected CPU study and CUDA results directories');
const rows = file => readFileSync(file, 'utf8').trim().split('\n').map(JSON.parse);
const summary = file => JSON.parse(readFileSync(file, 'utf8'));
console.log('# Paired backend comparison on FLEURS vi_vn development\n');
console.log('Each row compares CPU int8 with CUDA float16 on the same 361 recordings. The sign of the change refers to errors on a single clip under beam-five decoding.\n');
console.log('| Recognizer | Fewer errors on CUDA | Equal | More | Full CPU token error | Full CUDA token error | Fractional policy CPU | Fractional policy CUDA |');
console.log('|---|---:|---:|---:|---:|---:|---:|---:|');
for (const [name, cpu, gpu] of [['PhoWhisper-base', 'pho', 'pho-model'], ['Whisper-base', 'dev', 'model']]) {
  const a = rows(join(cpuDir, cpu + '_counts.jsonl'));
  const b = rows(join(cudaDir, gpu + '.jsonl'));
  const byKey = new Map(b.map(x => [x.key, x]));
  assert.equal(a.length, 361);
  assert.equal(new Set(a.map(x => x.key)).size, a.length);
  assert.equal(b.length, a.length);
  assert.equal(byKey.size, a.length);
  const counts = [0, 0, 0];
  for (const row of a) {
    const paired = byKey.get(row.key);
    for (const field of ['prompt', 'samples', 'ref']) assert.equal(paired[field], row[field]);
    counts[1 + Math.sign(paired.beam_errors - row.beam_errors)]++;
  }
  const summaries = [summary(join(cpuDir, cpu + '_summary.json')), summary(join(cudaDir, gpu + '.json'))];
  const full = summaries.map((s, i) => {
    const observations = i ? b : a;
    assert.equal(s.total_beam_errors, observations.reduce((n, x) => n + x.beam_errors, 0));
    assert.equal(s.ref_tokens, observations.reduce((n, x) => n + x.ref, 0));
    return (100 * s.total_beam_errors / s.ref_tokens).toFixed(2) + '%';
  });
  const policy = summaries.map(s => {
    const p = s.methods.fractional;
    assert.equal(p.accepted, 291);
    return (100 * p.errors / p.reference_tokens).toFixed(2) + '%';
  });
  console.log('| ' + [name, ...counts, ...full, ...policy].join(' | ') + ' |');
}
console.log('\nThe precision and device changed together. Equal error counts can come from different hypotheses. Each selector was refit on its backend-specific features with the same prompt fold assignments. The within-backend paired contrasts are in [the CUDA results](RESULTS.md) and [the CPU results](../scribe_vi/RESULTS.md).');
