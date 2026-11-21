// Evaluate only constant-rank segments and the sampled weights.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const [archive, directory] = process.argv.slice(2);
const lines = p => fs.readFileSync(p, 'utf8').trimEnd().split(/\r?\n/);
const csv = file => {
  const [head, ...records] = lines(path.join(directory, file + '.csv'));
  return records.map(record => {
    assert(!record.includes('"'));
    const values = record.split(',');
    const keys = head.split(',');
    assert.equal(values.length, keys.length);
    return Object.fromEntries(keys.map((key, i) => [key, values[i]]));
  });
};
const queries = new Map();
for (const line of lines(archive)) {
  const [source, query, doc, ...raw] = line.split('\t');
  const key = JSON.stringify([source, query]);
  if (!queries.has(key)) queries.set(key, new Map());
  assert(!queries.get(key).has(doc));
  queries.get(key).set(doc, raw.map(s => s.split(':').map(Number)));
}
function grid(m) {
  return Array.from({length: m + 1}, (_, i) => {
    const numerator = 65535 * i;
    const lower = Math.floor(numerator / m);
    const remainder = numerator % m;
    return lower + Number(2 * remainder > m || (2 * remainder === m && lower % 2 === 1));
  });
}
const at = (events, w) => events.findLast(([start]) => start <= w)[1];
const ndcg = (docs, w) => {
  const discount = r => 1 / Math.log2(r + 1);
  const ranks = [...docs.values()].map(e => at(e, w)).filter(r => r <= 10);
  const ideal = Array.from({length: Math.min(docs.size, 10)}, (_, i) => discount(i + 1));
  return ranks.reduce((n, r) => n + discount(r), 0) / ideal.reduce((n, v) => n + v, 0);
};
function best(weights, score) {
  const values = weights.map(score);
  const max = Math.max(...values);
  return [weights[values.findIndex(v => max - v < 1e-12)], max];
}
const starts = docs => [...new Set([...docs.values()].flatMap(events => events.map(e => e[0])))].sort((a,b) => a-b);
const close = (a, b) => assert(Math.abs(Number(a) - Number(b)) < 1e-11, a + ' vs ' + b);
const summaries = csv('summary');
const queryRows = csv('queries');
const expectedMisses = new Set(csv('missed_intervals').map(r => {
  assert.equal(Number(r.width), Number(r.hi) - Number(r.lo) + 1);
  return JSON.stringify([r.source, r.qid, +r.points, r.doc, +r.lo, +r.hi]);
}));
assert.equal(queryRows.length, 450);
assert.equal(queries.size, 150);
assert.equal([...queries.values()].reduce((s, m) => s + m.size, 0), 417);
assert.equal(summaries.length, 9);
const finished = new Set();
for (const s of summaries) {
  const group = queryRows.filter(r => r.source === s.source && r.points === s.points);
  assert.equal(group.length, 50);
  const weights = grid(Number(s.points) - 1);
  const sharedStarts = new Set();
  const members = [];
  const gaps = [], widths = [];
  const totals = {judged: 0, seen: 0, missed_docs: 0, intervals: 0, missed_intervals: 0,
    queries_missing_intervals: 0, queries_missing_docs: 0};
  for (const r of group) {
    const rowkey = JSON.stringify([r.source, r.qid, r.points]);
    assert(!finished.has(rowkey));
    finished.add(rowkey);
    const docs = queries.get(JSON.stringify([r.source, r.qid]));
    members.push(docs);
    const changes = starts(docs);
    for (const w of changes) sharedStarts.add(w);
    const [exactW, exact] = best(changes, w => ndcg(docs, w));
    const [gridW, sampled] = best(weights, w => ndcg(docs, w));
    for (const [value, original] of [[exactW,r.exact_w],[exact,r.exact],[gridW,r.grid_w],[sampled,r.grid],[exact-sampled,r.gap]]) close(value, original);
    gaps.push(exact-sampled);
    const counts = {judged: docs.size, seen: 0, missed_docs: 0, intervals: 0, missed_intervals: 0};
    for (const [id, events] of docs) {
      let lo;
      let visible = false;
      for (const [w, rank] of [...events, [65536, 11]]) {
        if (rank <= 10) {
          visible = true;
          lo ??= w;
        } else if (lo !== undefined) {
          counts.intervals++;
          if (!weights.some(x => lo <= x && x < w)) {
            assert(expectedMisses.delete(JSON.stringify([r.source, r.qid, +r.points, id, lo, w-1])));
            widths.push(w-lo);
            counts.missed_intervals++;
          }
          lo = undefined;
        }
      }
      counts.seen += Number(visible);
      counts.missed_docs += Number(visible && weights.every(w => at(events, w) > 10));
    }
    for (const [key, value] of Object.entries(counts)) {
      assert.equal(value, Number(r[key]));
      totals[key] += value;
    }
    totals.queries_missing_docs += Number(counts.missed_docs > 0);
    totals.queries_missing_intervals += Number(counts.missed_intervals > 0);
  }
  const mean = w => members.reduce((sum, docs) => sum + ndcg(docs, w), 0) / members.length;
  const [ew, exact] = best([...sharedStarts].sort((a,b) => a-b), mean);
  const [gw, sampled] = best(weights, mean);
  for (const [key, val] of Object.entries({...totals, exact_w: ew, grid_w: gw, exact,
    grid: sampled, shared_gap: exact - sampled, query_mean_gap: gaps.reduce((a,b) => a+b,0)/gaps.length,
    query_gaps: gaps.filter(x => x > 1e-12).length, query_max_gap: Math.max(...gaps)})) close(s[key], val);
  widths.sort((a,b) => a-b);
  if (widths.length) {
    const mid = (widths[Math.floor(widths.length/2)] + widths[Math.floor((widths.length-1)/2)])/2;
    close(s.width_min, widths[0]); close(s.width_max, widths.at(-1)); close(s.width_median, mid);
  } else assert([s.width_min, s.width_median, s.width_max].every(v => v === ''));
}
assert.equal(expectedMisses.size, 0);
console.log('Verified 150 queries, 417 judgments, all 450 query/grid rows, every missed interval and all nine source summaries.');
