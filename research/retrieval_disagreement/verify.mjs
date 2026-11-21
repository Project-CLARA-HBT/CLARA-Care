import assert from "node:assert/strict";
import {readFileSync} from "node:fs";

const load = name => JSON.parse(readFileSync(new URL("results/" + name + ".json", import.meta.url)));
const grid = load("query_grid");
const result = load("summary");
const mean = a => a.reduce((s,n) => s+n, 0) / a.length;
function choice(sources, group) {
    const withRows = sources.map(rows => rows.filter(group)).filter(rows => rows.length);
    if (!withRows.length) return choice(sources, () => true);
    const weights = Array.from({length:11}, (_,j) => j);
    const scores = weights.map(j => mean(withRows.map(rows => mean(rows.map(r => r.convex[j])))));
    weights.sort((a,b) => scores[b]-scores[a] || Math.abs(a-5)-Math.abs(b-5) || a-b);
    return weights[0];
}
let total = 0;
for (const [name, rows] of Object.entries(grid)) {
    const train = Object.keys(grid).filter(n => n!==name).map(n => grid[n]);
    const baseline = choice(train, () => true);
    const low = choice(train, r => r.overlap<=2);
    const high = choice(train, r => r.overlap>2);
    const record = result.sources[name];
    assert.equal(baseline / 10, record.global_weight);
    assert.deepEqual([low / 10, high / 10], record.overlap_weights);
    assert.equal(rows.length, new Set(rows.map(r=>r.qid)).size);
    for (const r of rows) {
        assert.equal(r.relevant, r.reachable);
        assert.ok(r.relevant>0 && r.convex.every(s=>s>=0 && s<=1.0000000001));
    }
    const value = mean(rows.map(r=>r.convex[r.overlap<=2 ? low : high]));
    assert.ok(Math.abs(value-record.means.overlap_split)<1e-12);
    assert.ok(Math.abs(mean(rows.map(r=>r.convex[baseline]))-record.means.convex_trained)<1e-12);
    total += rows.length;
}
assert.equal(total,150);
console.log("Verified three held-out-source fits, 150 query grids and paired candidate/baseline means.");
