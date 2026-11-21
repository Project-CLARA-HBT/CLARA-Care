"""Generate the development manuscript section. Use --check to verify the saved copy."""

import argparse
import json
import math
from collections import Counter
from itertools import product
from pathlib import Path
from statistics import median

VENUE = Path(__file__).resolve().parents[3] / "research/venue2027"
ARTIFACTS = VENUE / "proof/artifacts"
SECTION = VENUE / "compsac/submission/pg_development_results.md"
ARMS = ("ssi", "shared_dependencies", "exclusive_dependencies")
LABELS = ("SSI", "Shared", "Exclusive")
ROUNDS = {f"v{i}": f"compsac_pg_scope_dev_v{i}.json" for i in range(1, 5)}
ROUNDS["Epoch"] = "compsac_pg_epoch_dev.json"
SEEDS = range(6)


def index_campaigns(data, round_name):
    epoch = round_name == "Epoch"
    expected_scope = (
        "development_changing_dependency_epochs"
        if epoch
        else "development_disjoint_targets_shared_dependencies"
    )
    if (data["scope"], data["server_version_num"], data["operations_per_campaign"]) != (
        expected_scope,
        160004,
        96,
    ):
        raise ValueError("unexpected campaign metadata")
    indexed = {}
    for row in data["rows"]:
        key = (row["workers"], row["fanout"], row["seed"], row["arm"])
        if key in indexed:
            raise ValueError(f"duplicate campaign {key}")
        c = Counter(row["counts"])
        missing, forbidden = row["missing_valid"], row["forbidden_installs"]
        if (
            set(c)
            - {"committed", "serialization_abort", "retries", "stale_dependency", "stale_target"}
            or any(type(n) is not int or n < 0 for n in [*c.values(), missing, forbidden])
            or c.total() - c["retries"] != 96
            or c["committed"] != 84 - missing + forbidden
            or missing > 84
            or forbidden > 12
            or c["retries"] > 96 * data.get("retry_limit", 0)
        ):
            raise ValueError(f"invalid counts {key}")
        if (
            row["seconds"] <= 0
            or not math.isfinite(row["seconds"])
            or not math.isclose(
                c["committed"] / row["seconds"], row["committed_per_second"], rel_tol=1e-12
            )
        ):
            raise ValueError(f"invalid throughput {key}")
        if epoch:
            waves = row["waves"]
            installed = set(row["installed_ids"])
            valid = {i for i in range(9, 105) if i % 8}
            if (
                [w["epoch"] for w in waves] != [1, 2, 3, 4]
                or any(
                    sum(w["counts"].values()) - w["counts"].get("retries", 0) != 24 for w in waves
                )
                or sum((Counter(w["counts"]) for w in waves), Counter()) != c
                or sum(w["seconds"] for w in waves) != row["seconds"]
                or len(valid - installed) != missing
                or len(installed - valid) != forbidden
                or len(installed) != len(row["installed_ids"])
            ):
                raise ValueError(f"epoch readback mismatch {key}")
        indexed[key] = row
    workers, fanouts = ([4], [8]) if epoch else ([1, 4], [1, 8])
    if set(indexed) != set(product(workers, fanouts, SEEDS, ARMS)):
        raise ValueError("unexpected seed/arm grid")
    return indexed


def table(headers, rows):
    def line(values):
        return "| " + " | ".join(map(str, values)) + " |"

    return "\n".join([line(headers), line(["---"] * len(headers)), *map(line, rows)])


def render():
    ratios, outcomes, summary = [], [], {}
    ssi_missing = {}
    for name, file in ROUNDS.items():
        index = index_campaigns(json.loads((ARTIFACTS / file).read_text()), name)
        for w, f in sorted({(w, f) for w, f, _, _ in index}):
            for arm, label in zip(ARMS, LABELS, strict=True):
                rows = [index[w, f, s, arm] for s in SEEDS]
                rates = [r["committed_per_second"] for r in rows]
                c = sum((Counter(r["counts"]) for r in rows), Counter())
                missing = sum(r["missing_valid"] for r in rows)
                outcomes.append(
                    [
                        name,
                        w,
                        f,
                        label,
                        f"{median(rates):.1f}",
                        c["committed"],
                        c["stale_dependency"],
                        c["stale_target"],
                        c["serialization_abort"],
                        c["retries"],
                        missing,
                        sum(r["forbidden_installs"] for r in rows),
                    ]
                )
                if arm == "ssi":
                    ssi_missing[name, w, f] = missing
                else:
                    paired = [
                        rates[s] / index[w, f, s, "ssi"]["committed_per_second"] for s in SEEDS
                    ]
                    summary[name, w, f, label] = median(paired)
                    ratios.append(
                        [
                            name,
                            w,
                            f,
                            label,
                            *[f"{v:.3f}" for v in paired],
                            f"{median(paired):.3f}",
                            sum(v < 1 for v in paired),
                        ]
                    )

    def trajectory(w, f, label):
        return ", ".join(f"{summary[name, w, f, label]:.3f}" for name in ("v1", "v2", "v3", "v4"))

    ratio_table = table(
        ["Round", "Workers", "Fanout", "Arm / SSI", *SEEDS, "Median", "Losses / 6"], ratios[:-2]
    )
    epoch_ratios = table(
        ["Round", "Workers", "Fanout", "Arm / SSI", *SEEDS, "Median", "Losses / 6"], ratios[-2:]
    )
    count_headers = [
        "Round",
        "Workers",
        "Fanout",
        "Arm",
        "Commits/s",
        "Committed",
        "Stale dep.",
        "Stale target",
        "Final aborts",
        "Retries",
        "Missing valid",
        "Forbidden",
    ]
    sources = "\n".join(
        f"- [{name} raw campaigns](../../proof/artifacts/{f})" for name, f in ROUNDS.items()
    )
    return f"""# Disjoint-target PostgreSQL development results

On PostgreSQL 16.4, four development rounds compared native serializable snapshot
isolation (SSI) with two READ COMMITTED implementations that locked dependency rows
using FOR SHARE or FOR UPDATE. Each campaign submitted 96 proposals for distinct
targets. All proposals read the same one or eight dependency rows. Of the 96,
84 carried the current version and 12 carried a mismatched version. Each arm used
the same shuffled targets for a given seed. The six seeds covered all six arm orders.

With four workers and eight dependencies, the median shared-lock/SSI throughput
ratio was {trajectory(4, 8, "Shared")} in successive rounds. With four workers and
one dependency, the corresponding ratios were {trajectory(4, 1, "Shared")}.
The direction of this latter comparison reversed in v3, when fresh planner
statistics and bounded retries were introduced together. In that cell SSI
left {ssi_missing["v2", 4, 1]} valid targets uninstalled in v2 and {ssi_missing["v3", 4, 1]}
in v3. Throughput counts only installed targets, so it reflects completion as
well as elapsed time.

With four workers
and eight dependencies, the exclusive-lock median moved from
{summary["v3", 4, 8, "Exclusive"]:.3f} in v3 to {summary["v4", 4, 8, "Exclusive"]:.3f} in v4
when dependencies and targets were placed in separate relations. With one
worker and eight dependencies, both lock arms had median ratios below one
in every round.
These are descriptive measurements of the disjoint-target validation and write
component. Full B4 and confirmatory evaluation remain outside this study.

## Paired throughput across four rounds

v1 read dependency versions and issued a separate conditional target update for
eligible proposals. v2 combined validation and the write in one SQL statement in
all three arms. Neither round retried a serialization failure. v3 added ANALYZE
after fixture population and allowed two retries per proposal. v4 retained those
settings and split the dependency and target relations. These successive runs
describe sensitivity to implementation and workload choices. Attribution to
individual planner, locking or retry mechanisms would require additional controls.

Throughput is committed target writes per wall-clock second from the worker start
barrier to the last worker finishing, including retries. Each numbered column
is the dimensionless ratio of the lock-arm rate to the SSI rate at the same
round, worker count, fanout and seed. The median summarizes six paired ratios.
Losses count strictly lower unrounded rates. Fanout counts dependency rows per
proposal. All 288 campaigns enter the comparison.

{ratio_table}

## Completion and readback

Each row below covers six campaigns of one arm, or 576 submitted proposals
(504 eligible and 72 stale). Commits/s is the median campaign rate. All other
outcome columns are counts summed across seeds. The four terminal outcomes
sum to 576. Retries count additional attempts after serialization failure.
Adding retries and final aborts gives the total number of serialization failures.
Missing valid counts eligible targets absent at final readback. Forbidden counts
installed targets whose proposals carried a mismatched version.

{table(count_headers, outcomes[:-3])}

Across the four rounds, SSI missed {sum(v for (r, _, _), v in ssi_missing.items() if r != "Epoch"):,}
of 8,064 eligible targets. Shared and exclusive locks missed
{sum(r[-2] for r in outcomes if r[0] != "Epoch" and r[3] == "Shared")} and
{sum(r[-2] for r in outcomes if r[0] != "Epoch" and r[3] == "Exclusive")}, respectively.
Readback found {sum(r[-1] for r in outcomes if r[0] != "Epoch")} forbidden installs among
3,456 stale proposals across all arms. Each proposal is counted within its own campaign.

## Changing dependency epochs

A separately prespecified split-relation condition advanced all eight dependency
versions before each of four 24-proposal waves. Four workers then processed
21 current and three previously valid proposals in each wave. The advances
occurred between waves, so this measures invalidation across a committed version
change. The timing denominator is the sum of the four proposal intervals and
excludes version updates. Comparisons are paired within this condition.

{epoch_ratios}

{table(count_headers, outcomes[-3:])}

Across six campaigns per arm, readback found {outcomes[-3][-2]} missing eligible
targets for SSI, {outcomes[-2][-2]} for shared locks and {outcomes[-1][-2]} for
exclusive locks. The three arms together installed {sum(row[-1] for row in outcomes[-3:])}
expired proposals. This readback scores committed database state independently
of the throughput timer. Concurrent mutation during a proposal remains unmeasured.

## Reproduction

Run `python -m evaluation.venue2027.compsac.pg_development_results --check` from
the repository root to validate the campaign grid and compare this section with
the recorded measurements. The sources retain the original timings and counts.

{sources}
- [Epoch condition and scoring rules](../protocols/pg_epoch_development.md)
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = render()
    if args.check:
        if SECTION.read_bytes() != content.encode():
            raise SystemExit("saved section differs from generated section")
    else:
        SECTION.write_bytes(content.encode())
