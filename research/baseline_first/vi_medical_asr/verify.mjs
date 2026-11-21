import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const read = path => JSON.parse(readFileSync(path, "utf8"));
const catalog = read("catalog.json");
const models = process.argv.slice(2).map(path => read(path));
assert.ok(models.length > 0);
assert.equal(catalog.selected_rows, 168);
assert.equal(catalog.selected_speakers, 21);
assert.equal(catalog.selected_recordings, 10);
const sum = (rows, field) => rows.reduce((n, row) => n + (row[field] ?? 0), 0);
function groups(rows, key) {
  const grouped = new Map();
  for (const row of rows) {
    if (!grouped.has(row[key])) grouped.set(row[key], []);
    grouped.get(row[key]).push(row);
  }
  return [...grouped.values()];
}
const summaries = [];
for (const model of models) {
  assert.deepEqual(model.catalog, catalog);
  const { rows } = model;
  assert.equal(rows.length, catalog.selected_rows);
  assert.equal(sum(rows, "ref_tokens"), catalog.selected_ref_tokens);
  const uniqueSpeakers = groups(rows, "speaker");
  assert.equal(uniqueSpeakers.length, catalog.selected_speakers);
  assert.ok(uniqueSpeakers.every(group => group.length === 8));
  assert.equal(groups(rows, "recording").length, catalog.selected_recordings);
  for (const [i, row] of rows.entries()) {
    assert.equal(row.ordinal, i);
    for (const key of ["speaker", "recording", "ref_tokens"])
      assert.equal(row[key], models[0].rows[i][key]);
    if (!row.success) {
      assert.ok(row.failure_class);
      continue;
    }
    for (const [k, v] of Object.entries(row))
      if (k !== "success") assert.ok(Number.isSafeInteger(v) && v >= 0);
    assert.equal(row.clips, 1);
    assert.equal(row.errors, sum([row], "sub") + sum([row], "del") + sum([row], "ins"));
    assert.ok(row.folded_errors <= row.errors);
    assert.ok(sum([row], "sub_rare") <= sum([row], "sub"));
    assert.ok(sum([row], "del_rare") <= sum([row], "del"));
  }
  const success = rows.filter(x => x.success);
  const result = {model: model.model, success: success.length, failed: rows.length-success.length};
  if (result.failed === 0) {
    for (const key of ["ref_tokens","errors","sub","del","ins","sub_fold_equal","folded_errors","sub_rare","del_rare"])
      result[key] = sum(rows,key);
    result.accent_oracle_edits_saved = result.errors - result.folded_errors;
    result.accent_only_promising = result.accent_oracle_edits_saved >= 0.2 * result.errors;
    for (const key of ["speaker","recording"]) {
      result[key] = groups(rows,key).map(group => ({
        group: group[0][key],
        clips: group.length,
        ref_tokens: sum(group,"ref_tokens"),
        errors: sum(group,"errors"),
      }));
    }
  }
  summaries.push(result);
}
console.log(JSON.stringify(summaries, null, 2));
