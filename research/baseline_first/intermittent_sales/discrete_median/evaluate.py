"""Run with the parent screen dependencies and the registered Monash archive."""
import json
import sys
from collections import Counter
from pathlib import Path

from sklearn.isotonic import IsotonicRegression

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from screen import distributions, features, history, load, lower_median


def forecast(key, pooled, cells, models, global_counts):
    frequency, age = key
    cell = cells[key]
    base = cell or pooled[frequency] or global_counts
    raw = 1 - base[0] / base.total()
    probability = (models[age].predict([frequency])[0] if age in models
                   else 1 - global_counts[0] / global_counts.total())
    for counts in (cell, pooled[frequency], global_counts):
        positive = Counter({v: n for v, n in counts.items() if v > 0})
        if positive:
            break

    def decision(p):
        if p <= 0.5:
            return 0
        target = positive.total() * (1 - 0.5 / p)
        cumulative = 0
        for value in sorted(positive):
            cumulative += positive[value]
            if cumulative + 1e-12 >= target:
                return value

    return decision(probability), decision(raw), lower_median(positive) if probability > .5 else 0


def main(archive):
    ids, y = load(archive)
    prior = json.loads(Path(__file__).resolve().parents[1].joinpath("summary.json").read_text())
    months = {}
    for t in range(43, 51):
        pooled, cells, _, _ = distributions(y, t)
        models = {}
        for age in {a for _, a in cells}:
            bins = sorted(f for f, a in cells if a == age)
            counts = [cells[f, age] for f in bins]
            models[age] = IsotonicRegression(out_of_bounds="clip").fit(
                bins, [1 - c[0] / c.total() for c in counts], sample_weight=[c.total() for c in counts])
        global_counts = sum(pooled.values(), Counter())
        totals = Counter()
        zero_error = 0
        for series in y:
            truth = series[t]
            if truth != truth:
                continue
            h = history(series[:t])
            preds = forecast(features(h)[1], pooled, cells, models, global_counts) if len(h) else (0, 0, 0)
            for name, pred in zip(("hurdle", "raw", "gated"), preds):
                totals[name] += abs(int(truth) - int(pred))
            zero_error += int(truth)
        assert zero_error == prior["eval_months"][str(t+1)]["zero"]
        months[t+1] = dict(totals)
    print(json.dumps({"months": months, "total": dict(sum(map(Counter, months.values()), Counter())),
                      "registered": prior["eval"]}, indent=2))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
