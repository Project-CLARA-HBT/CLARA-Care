"""Independently recompute every manuscript table cell from counts and wall time."""

import json
from collections import defaultdict
from statistics import median

import pytest

from .pg_development_results import ARTIFACTS, SECTION, index_campaigns, render


def test_tables_against_raw_campaigns():
    section = SECTION.read_text()
    assert section == render()
    tables = {}
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        cells = [s.strip() for s in line.strip("|").split("|")]
        if cells[0] == "Round":
            kind = cells[3]
        elif cells[0] != "---":
            key = (kind, *cells[:4])
            assert key not in tables
            tables[key] = cells[4:]

    files = sorted(ARTIFACTS.glob("compsac_pg_scope_dev_v*.json"))
    assert len(files) == 4
    for path in [*files, ARTIFACTS / "compsac_pg_epoch_dev.json"]:
        name = "Epoch" if "epoch" in path.name else path.stem.rsplit("_", 1)[1]
        conditions = defaultdict(list)
        for row in json.loads(path.read_text())["rows"]:
            conditions[row["workers"], row["fanout"]].append(row)
        for (workers, fanout), rows in conditions.items():
            prefix = (name, str(workers), str(fanout))
            by_arm = defaultdict(dict)
            for row in rows:
                label = row["arm"].split("_")[0].capitalize() if row["arm"] != "ssi" else "SSI"
                by_arm[label][row["seed"]] = row
            for label, seeds in by_arm.items():
                campaigns = [seeds[i] for i in range(6)]
                rates = [r["counts"]["committed"] / r["seconds"] for r in campaigns]
                counts = [
                    sum(r["counts"].get(k, 0) for r in campaigns)
                    for k in (
                        "committed",
                        "stale_dependency",
                        "stale_target",
                        "serialization_abort",
                        "retries",
                    )
                ]
                readback = [
                    sum(r[k] for r in campaigns) for k in ("missing_valid", "forbidden_installs")
                ]
                assert tables.pop(("Arm", *prefix, label)) == [
                    f"{median(rates):.1f}",
                    *map(str, counts + readback),
                ]
                if label != "SSI":
                    ratios = [
                        rate * by_arm["SSI"][i]["seconds"] / by_arm["SSI"][i]["counts"]["committed"]
                        for i, rate in enumerate(rates)
                    ]
                    assert tables.pop(("Arm / SSI", *prefix, label)) == [
                        *(f"{r:.3f}" for r in ratios),
                        f"{median(ratios):.3f}",
                        str(sum(r < 1 for r in ratios)),
                    ]
    assert not tables


def test_incomplete_and_duplicate_campaigns_rejected():
    data = json.loads((ARTIFACTS / "compsac_pg_scope_dev_v1.json").read_text())
    data["rows"].pop()
    with pytest.raises(ValueError, match="grid"):
        index_campaigns(data, "v1")
    data["rows"].append(data["rows"][0])
    with pytest.raises(ValueError, match="duplicate"):
        index_campaigns(data, "v1")
