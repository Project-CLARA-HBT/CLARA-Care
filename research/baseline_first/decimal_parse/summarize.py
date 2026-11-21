"""Summarize balanced per-day WSL CPU timings against every comparator."""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median

grouped = defaultdict(lambda: defaultdict(dict))
with Path(sys.argv[1]).open() as source:
    for row in csv.DictReader(source):
        day, arm, round_id = row["day"], row["arm"], int(row["round"])
        assert round_id not in grouped[day][arm]
        grouped[day][arm][round_id] = int(row["elapsed_ns"]) / int(row["passes"])
assert len(grouped) == 14
by_day = {}
for day, arms in sorted(grouped.items()):
    assert set(arms) == {"paired", "scalar", "fast_float", "std", "scan"}
    assert all(set(rounds) == set(range(10)) for rounds in arms.values())
    by_day[day] = {arm: median(rounds.values()) for arm, rounds in arms.items()}
by_arm = {}
for arm in ["fast_float", "std", "scalar", "scan"]:
    savings = [1 - costs["paired"] / costs[arm] for costs in by_day.values()]
    by_arm[arm] = {
        "median_paired_saving": median(savings),
        "worst_day_saving": min(savings),
        "best_day_saving": max(savings),
        "days_faster": sum(s > 0 for s in savings),
        "days_at_or_above_20_percent": sum(s >= 0.2 for s in savings),
    }
print(json.dumps({"days": by_day, "comparison": by_arm}, indent=2))
