"""Check all published sales totals against the local rolling forecast replay."""

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


def verify(folder):
    result = json.loads((folder / "summary.json").read_text())
    with (folder / "errors.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 4096
    assert len({(r["sku"], r["month"]) for r in rows}) == len(rows)
    scored = [r for r in rows if int(r["month"]) >= 44]
    observed = [r for r in scored if r["observed"] == "1"]
    assert len(observed) == result["observed"]
    assert len(scored) - len(observed) == result["missing"]
    assert len({r["sku"] for r in observed}) == result["valid_series"]
    for month, scores in result["eval_months"].items():
        for arm, expected in scores.items():
            total = sum(float(r[arm]) for r in observed if r["month"] == month)
            assert math.isclose(total, expected, rel_tol=1e-12)
    for arm, expected in result["eval"].items():
        assert math.isclose(sum(float(r[arm]) for r in observed), expected, rel_tol=1e-12)
    for group, chosen in result["tuned"].items():
        candidates = [a for a in rows[0] if a.startswith(group + "_")]
        tune = [r for r in rows if int(r["month"]) < 44 and r["observed"] == "1"]
        losses = {a: sum(float(r[a]) for r in tune) for a in candidates}
        assert losses[f"{group}_{chosen}"] == min(losses.values())
    output = {}
    for field in ("freq_bin", "age_bin"):
        margins = defaultdict(Counter)
        for r in scored:
            cell = margins[r[field]]
            if r["observed"] == "0":
                cell["missing"] += 1
            else:
                cell["scored"] += 1
                for arm in ("zero", "age_raw", "shrink_4"):
                    cell[arm] += int(float(r[arm]))
        output[field] = margins
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("folder", type=Path)
    verify(p.parse_args().folder)
