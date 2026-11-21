import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const read = path => JSON.parse(readFileSync(path, "utf8"));
const nbest = read("nbest.json");
const large = read("large.json");
const catalog = read("catalog.json");
assert.deepEqual(large.catalog, catalog);
assert.deepEqual(nbest.catalog, catalog);
assert.equal(nbest.model, large.model);
assert.equal(nbest.rows.length, catalog.selected_rows);
assert.equal(large.rows.length, catalog.selected_rows);
const firstMinimum = numbers => numbers.indexOf(Math.min(...numbers));
const rescuedSpeakers = new Set();
const rescuedRecordings = new Set();
const summary = { clips: 0, failures: 0, ref_tokens: 0, rank1: 0, medoid: 0, oracle: 0,
  rank1_exact: 0, medoid_exact: 0, oracle_exact: 0, any_improvement: 0, unique_histogram: {} };
for (const [i, row] of nbest.rows.entries()) {
  assert.equal(row.ordinal, i);
  for (const key of ["ordinal", "recording", "speaker", "ref_tokens"])
    assert.equal(row[key], large.rows[i][key]);
  if (row.failure_class) {
    ++summary.failures;
    continue;
  }
  const errors = row.errors_by_rank;
  const costs = row.within_list_edit_sums;
  for (const sequence of [errors, costs]) {
    assert.equal(sequence.length, 5);
    assert.ok(sequence.every(i => Number.isSafeInteger(i) && i >= 0));
  }
  assert.ok(row.unique_sequences >= 1 && row.unique_sequences <= 5);
  const values = {rank1: errors[0], medoid: errors[firstMinimum(costs)], oracle: Math.min(...errors)};
  for (const [key, value] of Object.entries(values)) {
    summary[key] += value;
    summary[key + "_exact"] += Number(value === 0);
  }
  if (values.rank1 > values.oracle) {
    ++summary.any_improvement;
    rescuedSpeakers.add(row.speaker);
    rescuedRecordings.add(row.recording);
  }
  ++summary.clips;
  summary.ref_tokens += row.ref_tokens;
  const n = row.unique_sequences;
  summary.unique_histogram[n] = (summary.unique_histogram[n] ?? 0) + 1;
}
summary.speakers_with_oracle_gain = rescuedSpeakers.size;
summary.recordings_with_oracle_gain = rescuedRecordings.size;
if (summary.failures === 0) {
  assert.equal(summary.ref_tokens, catalog.selected_ref_tokens);
  summary.oracle_pass_15pct = [summary.rank1, summary.medoid].every(
    baseline => summary.oracle <= 0.85 * baseline);
}
console.log(JSON.stringify(summary, null, 2));
