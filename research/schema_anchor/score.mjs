/** Score the frozen predictions without importing the matcher. */
import fs from "node:fs";
import assert from "node:assert/strict";

const {records} = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const cells = [];
for (const {pair, gold, predictions} of records) {
  const goldKeys = new Set(gold.map(key => JSON.stringify(key)));
  for (const [arm, links] of Object.entries(predictions)) {
    const keys = new Set(links.map(key => JSON.stringify(key)));
    assert.equal(links.length, keys.size);
    const tp = [...keys].filter(key => goldKeys.has(key)).length;
    const fp = keys.size - tp;
    const fn = goldKeys.size - tp;
    cells.push({group: pair.split("/")[1], pair, arm, tp, fp, fn, f1: 2*tp/(2*tp+fp+fn)});
  }
}
const summaries = {};
for (const group of ["Magellan", "Wikidata"]) {
  summaries[group] = {};
  for (const arm of Object.keys(records[0].predictions)) {
    const scores = cells.filter(c => c.group === group && c.arm === arm);
    assert.equal(scores.length, group === "Magellan" ? 7 : 4);
    summaries[group][arm] = scores.reduce((s, c) => s + c.f1, 0) / scores.length;
  }
}
console.log(JSON.stringify({summaries, cells}, null, 2));
