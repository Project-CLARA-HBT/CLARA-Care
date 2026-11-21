"""Paired chronological replay using recorded, first-attempt ABB verdicts."""

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean, median

from sklearn.ensemble import HistGradientBoostingClassifier
from threadpoolctl import threadpool_limits

PROJECTS = {
    "iofrol": "70e18e1525445f2b1193a9e2ec793365c13e61e7e44a67ce54d8fa03ea3d7022",
    "paintcontrol": "7b2aa489f944177b8d0ac3c461dfa10846fad5465d66e1ffa0ab3c9fd88157b0",
}
ALPHAS = (0.2, 0.5, 0.8)
STRENGTHS = (2, 8, 32)
FAMILIES = {
    m: [m]
    for m in (
        "shortest",
        "mostfail",
        "latestfail",
        "latesttrans",
        "mostfail_cost",
        "latestfail_cost",
        "latesttrans_cost",
        "greedy",
        "tree",
    )
}
FAMILIES["ewma"] = [f"ewma_{a}" for a in ALPHAS]
for family in ("frequency", "verdict", "candidate"):
    FAMILIES[family] = [f"{family}_{k}" for k in STRENGTHS]


def load(path, digest):
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError("unexpected input")
    cycles = defaultdict(dict)
    with path.open() as f:
        for row in csv.DictReader(f, delimiter=";"):
            cycle, test, idx, duration, verdict = (
                int(row[k]) for k in ("Cycle", "Name", "Id", "Duration", "Verdict")
            )
            if duration <= 0 or verdict not in (0, 1):
                raise ValueError("unsupported observation")
            tests = cycles[cycle]
            if test not in tests or idx < tests[test][0]:
                tests[test] = idx, duration, verdict
    return sorted(cycles.items())


@dataclass
class History:
    n: int = 0
    failures: int = 0
    last: int = -1
    duration: int = 0
    failure_at: int | None = None
    transition_at: int | None = None
    ewma: list = field(default_factory=lambda: [0.5] * len(ALPHAS))
    failed_mask: int = 0
    counts: dict = field(default_factory=lambda: defaultdict(lambda: [0, 0]))

    def update(self, ordinal, duration, y):
        if self.n and y != self.last:
            self.transition_at = ordinal
        if y:
            self.failure_at = ordinal
            self.failed_mask |= 1 << ordinal
        self.ewma = [
            a * y + (1 - a) * v if self.n else y for a, v in zip(ALPHAS, self.ewma, strict=True)
        ]
        self.n += 1
        self.failures += y
        self.last = y
        self.duration = duration


def rate(count):
    failures, n = count
    return (1 + failures) / (2 + n)


def cover(ids, scores, masks, durations):
    remaining = set(ids)
    covered = 0
    while remaining:
        test = max(
            remaining,
            key=lambda i: ((masks[i] & ~covered).bit_count() / durations[i], scores[i], -i),
        )
        yield test
        covered |= masks[test]
        remaining.remove(test)


def project(name, cycles, stage, selection):
    train = len(cycles) * 3 // 5
    valid = len(cycles) * 4 // 5
    history = {}
    totals = defaultdict(lambda: [0, 0])
    burden = 0.0
    rows = []
    x_train, y_train = [], []
    tree = HistGradientBoostingClassifier(
        max_depth=3, max_iter=80, learning_rate=0.1, early_stopping=False, random_state=0
    )
    active = {m for methods in FAMILIES.values() for m in methods}
    if stage == "test":
        active = set(selection["methods"].values())
    for t, (cycle, observed) in enumerate(cycles):
        if stage == "validation" and t == valid:
            break
        if t == train:
            tree.fit(x_train, y_train)
        score_cycle = t >= (train if stage == "validation" else valid)
        default_duration = median(h.duration for h in history.values()) if history else 1
        bin_id = int(burden >= 0.1) + int(burden >= 0.5)
        ids = sorted(observed)
        scores = defaultdict(dict)
        durations, masks, contexts = {}, {}, {}
        features = []
        for i in ids:
            h = history.setdefault(i, History())
            cost = durations[i] = h.duration or default_duration
            fail_age = t - h.failure_at if h.failure_at is not None else math.inf
            trans_age = t - h.transition_at if h.transition_at is not None else math.inf
            marginal = rate(totals["all"])
            keys = contexts[i] = (("last", h.last), ("context", h.last, bin_id))
            features.append(
                [
                    math.log(cost),
                    math.log1p(h.n),
                    math.log1p(h.failures),
                    (h.failures + 8 * marginal) / (h.n + 8),
                    h.last,
                    fail_age if math.isfinite(fail_age) else math.nan,
                    trans_age if math.isfinite(trans_age) else math.nan,
                    burden,
                    *h.ewma,
                ]
            )
            if not score_cycle:
                continue
            for method, value in {
                "shortest": -cost,
                "mostfail": h.failures,
                "latestfail": -fail_age,
                "latesttrans": -trans_age,
                "mostfail_cost": h.failures / cost,
                "latestfail_cost": -fail_age * cost,
                "latesttrans_cost": -trans_age * cost,
            }.items():
                scores[method][i] = value
            for a, v in zip(ALPHAS, h.ewma, strict=True):
                scores[f"ewma_{a}"][i] = v / cost
            for strength in STRENGTHS:
                scores[f"frequency_{strength}"][i] = (
                    (h.failures + strength * marginal) / (h.n + strength) / cost
                )
                for group, key in zip(("verdict", "candidate"), keys, strict=True):
                    f, n = h.counts[key]
                    backoff = rate(totals[key]) if totals[key][1] else marginal
                    scores[f"{group}_{strength}"][i] = (
                        (f + strength * backoff) / (n + strength) / cost
                    )
            masks[i] = h.failed_mask & (((1 << min(t, 32)) - 1) << max(0, t - 32))
        if t < train:
            x_train.extend(features)
            y_train.extend(observed[i][2] for i in ids)
        if score_cycle:
            scores["tree"] = {
                i: float(v) / durations[i]
                for i, v in zip(ids, tree.predict_proba(features)[:, 1], strict=True)
            }
            budget = sum(durations.values()) / 4
            failures = sum(r[2] for r in observed.values())
            for method in sorted(active):
                order = (
                    cover(ids, scores["frequency_8"], masks, durations)
                    if method == "greedy"
                    else sorted(ids, key=lambda i: (-scores[method][i], i))
                )
                found = runtime = completed = 0
                for i in order:
                    _, duration, y = observed[i]
                    if runtime + duration > budget:
                        break
                    found += y
                    runtime += duration
                    completed += 1
                rows.append(
                    dict(
                        project=name,
                        cycle=cycle,
                        method=method,
                        found=found,
                        failures=failures,
                        prefix=completed,
                        tests=len(ids),
                        budget=budget,
                        prefix_cost=runtime,
                    )
                )
        for i in ids:
            _, duration, y = observed[i]
            h = history[i]
            for key in contexts[i]:
                for pair in (h.counts[key], totals[key]):
                    pair[0] += y
                    pair[1] += 1
            totals["all"][0] += y
            totals["all"][1] += 1
            h.update(t, duration, y)
        burden = sum(r[2] for r in observed.values()) / len(ids)
    return rows


def summarize(rows):
    by_method = defaultdict(lambda: defaultdict(list))
    for row in rows:
        by_method[row["method"]][row["project"]].append(row)
    summary = {}
    for method, projects in by_method.items():
        metrics = {}
        for project, cases in projects.items():
            bearing = [r for r in cases if r["failures"]]
            metrics[project] = dict(
                cycles=len(cases),
                zero_failure=len(cases) - len(bearing),
                recall=mean(r["found"] / r["failures"] for r in bearing),
                any_failure=mean(r["found"] > 0 for r in bearing),
            )
        summary[method] = dict(projects=metrics, macro=mean(m["recall"] for m in metrics.values()))
    return summary


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("data", type=Path)
    parser.add_argument("stage", choices=["validation", "test"])
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=True, parents=True)
    selection_file = args.output / "selection.json"
    selection = json.loads(selection_file.read_bytes()) if args.stage == "test" else {}
    rows = []
    for name, digest in PROJECTS.items():
        rows.extend(project(name, load(args.data / f"{name}.csv", digest), args.stage, selection))
    score = summarize(rows)
    with (args.output / f"{args.stage}_cycles.csv").open("w") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    write(args.output / f"{args.stage}_summary.json", score)
    if args.stage == "validation":
        methods = {
            family: max(opts, key=lambda m: score[m]["macro"]) for family, opts in FAMILIES.items()
        }
        known = [m for f, m in methods.items() if f not in ("verdict", "candidate")]
        write(
            selection_file,
            dict(methods=methods, primary_comparator=max(known, key=lambda m: score[m]["macro"])),
        )


if __name__ == "__main__":
    with threadpool_limits(limits=1):
        main()
