"""Score the existing material-pattern code on the external training-file cohort."""
import argparse
import csv
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "material_patterns"))
from study import run


def score(cache, output):
    scores = run(cache, split=128, end=192)
    assert all(v.shape == (64, 3) for v in scores.values())
    output.mkdir(parents=True, exist_ok=True)
    with (output / "fields.csv").open("w") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["index", "arm", "all", "interior", "exterior"])
        for arm, values in scores.items():
            writer.writerows((i, arm, *v) for i, v in enumerate(values, 128))
    rng = np.random.default_rng(412)
    rs = rng.integers(64, size=(10000, 64))
    candidate = scores["pattern"][:, 0]
    summary = {}
    for arm, values in scores.items():
        base = values[:, 0]
        paired = 100 * (1 - candidate[rs].mean(axis=1)/base[rs].mean(axis=1))
        summary[arm] = dict(mean_all=base.mean(), mean_interior=values[:,1].mean(),
                            mean_exterior=values[:,2].mean(),
                            gain_pct=100*(1-candidate.mean()/base.mean()),
                            interval_pct=np.percentile(paired, [2.5,97.5]).tolist(),
                            wins=int((candidate < base).sum()), losses=int((candidate > base).sum()))
    (output / "summary.json").write_text(json.dumps(summary, indent=2)+"\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache",type=Path)
    parser.add_argument("output",type=Path)
    args = parser.parse_args()
    score(args.cache, args.output)
