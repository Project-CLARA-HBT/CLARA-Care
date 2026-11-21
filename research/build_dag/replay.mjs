import fs from "node:fs";
import assert from "node:assert/strict";

const input = (path) => JSON.parse(fs.readFileSync(path, "utf8"));
const sum = (values) => values.reduce((a, b) => a + b, 0);

// The scheduler receives only a priority list and the completed jobs. The
// simulator keeps realized service times private until each completion.
function simulate(jobs, priority, slots) {
  const pending = new Set(priority), done = new Map(), active = new Map();
  assert.equal(pending.size, Object.keys(jobs).length);
  let now = 0;
  const starts = {};
  while (pending.size || active.size) {
    for (const [key, end] of active) {
      if (end === now) {
        active.delete(key);
        done.set(key, now);
      }
    }
    for (const key of priority) {
      if (active.size === slots) break;
      if (pending.has(key) && jobs[key].parents.every((p) => done.has(p))) {
        pending.delete(key);
        starts[key] = now;
        active.set(key, now + jobs[key].finish - jobs[key].start);
      }
    }
    if (active.size) now = Math.min(...active.values());
    else assert.equal(pending.size, 0, "precedence cycle");
  }
  return { makespan: now, starts };
}

function ranks(jobs) {
  const memo = {}, children = {};
  for (const key of Object.keys(jobs)) children[key] = [];
  for (const [key, row] of Object.entries(jobs))
    for (const peer of row.parents) children[peer].push(key);
  function rank(key) {
    return memo[key] ??= jobs[key].finish - jobs[key].start + Math.max(0, ...children[key].map(rank));
  }
  for (const key of Object.keys(jobs)) rank(key);
  return memo;
}

function choose(jobs, slots, cp) {
  const keys = Object.keys(jobs).sort(), rank = ranks(jobs);
  const length = (key) => jobs[key].finish - jobs[key].start;
  const priorities = {
    lexical: keys, longest: [...keys].sort((a, b) => length(b) - length(a)),
    critical: [...keys].sort((a, b) => rank[b] - rank[a]),
  };
  let best = keys, time = Infinity;
  for (const order of Object.values(priorities)) {
    const t = simulate(jobs, order, slots).makespan;
    if (t < time) { time = t; best = order; }
  }
  priorities.portfolio = best;
  const incumbent = best;
  for (let a = 0; a < keys.length; ++a) {
    for (let b = a + 1; b < keys.length; ++b) {
      const order = [...incumbent];
      [order[a], order[b]] = [order[b], order[a]];
      const t = simulate(jobs, order, slots).makespan;
      if (t < time) { time = t; best = order; }
    }
  }
  priorities.swap = best;
  priorities.constraint = cp.priority;
  return priorities;
}

function evaluate(dir) {
  const history = input(dir + "/history.json").tasks;
  const next = input(dir + "/next.json").tasks;
  const cp = input(dir + "/cp.json");
  assert.deepEqual(Object.keys(history), Object.keys(next));
  for (const key of Object.keys(history)) {
    assert.deepEqual(history[key].parents, next[key].parents);
    assert.deepEqual(history[key].outputs, next[key].outputs);
  }
  const result = [];
  for (const slots of [2, 4, 8]) {
    const orders = choose(history, slots, cp[slots]);
    const lower = Math.max(...Object.values(ranks(next)),
      Math.ceil(sum(Object.values(next).map(t => t.finish - t.start)) / slots));
    for (const [method, order] of Object.entries(orders)) {
      assert.equal(new Set(order).size, Object.keys(next).length);
      const run = simulate(next, order, slots);
      assert(run.makespan >= lower);
      for (const [key, row] of Object.entries(next))
        for (const parent of row.parents)
          assert(run.starts[key] >= run.starts[parent] + next[parent].finish - next[parent].start);
      result.push({ slots, method, makespan: run.makespan, lower, historical: simulate(history, order, slots).makespan, starts: run.starts });
    }
  }
  return result;
}

console.log(JSON.stringify(evaluate(process.argv[2]), null, 2));
