// Generate the release decision from two complete out-of-fold score files.
import { readFileSync } from 'node:fs';

const models = ['PhoWhisper-base', 'Whisper-base'];
const inputs = process.argv.slice(2);
if (inputs.length !== models.length) {
  throw new Error('Expected PhoWhisper and Whisper summary JSON paths');
}
console.log('# Prompt-held-out lexical error at matched deferral\n');
const tables = [];
let passes = true;
for (const [index, name] of models.entries()) {
  const data = JSON.parse(readFileSync(inputs[index], 'utf8'));
  if (data.recordings !== 361 || data.prompts !== 149) {
    throw new Error('Incomplete development coverage');
  }
  const ours = data.methods.fractional;
  const full = 100 * data.total_beam_errors / data.ref_tokens;
  tables.push(`## ${name}\n\nAll 361 recordings gave a beam-five token error rate of ${full.toFixed(2)}% (${data.total_beam_errors}/${data.ref_tokens}). Decoder exceptions were ${data.beam_exceptions} with beam five and ${data.greedy_exceptions} with greedy decoding. Each policy accepted ${ours.accepted} recordings.\n`);
  tables.push('| Policy | Errors / accepted reference tokens | Error rate | Fractional minus policy, pp (conditional 95% interval) |','|---|---:|---:|---:|');
  for (const [method, row] of Object.entries(data.methods)) {
    if (row.accepted !== ours.accepted) throw new Error('Inconsistent budget');
    const delta = ours.accepted_wer_pct - row.accepted_wer_pct;
    const [lo, hi] = row.fractional_minus_baseline_pp_interval;
    if (method !== 'fractional' && (delta >= 0 || hi >= 0)) passes = false;
    tables.push(`| ${method} | ${row.errors} / ${row.reference_tokens} | ${row.accepted_wer_pct.toFixed(2)}% | ${method === 'fractional' ? 'reference' : delta.toFixed(2) + ' (' + lo.toFixed(2) + ', ' + hi.toFixed(2) + ')'} |`);
  }
  tables.push('');
}
console.log(passes ? 'Development contrasts support further independent validation.\n' :
  'The candidate fails the all-baselines criterion. Retire the present superiority claim.\n');
console.log(tables.join('\n'));
console.log('All deltas use percentage points. Negative values favor fractional selection. Intervals resample prompt clusters and keep fitted models and allocations fixed. These development intervals do not establish external superiority.\n');
console.log('[Protocol and endpoint](PROTOCOL.md) · [Data sources, related work, and limitations](README.md)');
