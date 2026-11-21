"""Render paired throughput and readback summaries from the five development artifacts."""

import json
import math
from itertools import product
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[3] / "research/venue2027"
ARMS = ("ssi", "exclusive_dependencies", "shared_dependencies")
ROUNDS = {
    "v1": "Separate read and write statements, one table, zero retries.",
    "v2": "One conditional statement for all arms, one table, zero retries.",
    "v3": "One conditional statement, one table, fresh planner statistics and two retries.",
    "v4": "Separate dependency and target tables, fresh statistics and two retries.",
    "epoch": "Split tables and two retries. Four dependency updates commit between proposal waves.",
}


def summarize():
    lines = [
        "# PostgreSQL development results",
        "",
        "Each cell compares six target-order seeds on PostgreSQL 16.4. Each seed ran native serializable snapshot isolation (SSI), exclusive dependency locks and shared dependency locks in balanced arm order. Each campaign scheduled 96 proposals on disjoint targets, including 12 carrying an ineligible dependency version. The two ratio columns give the median of the six within-seed committed-throughput ratios to SSI. A ratio below one favors SSI. W counts proposal workers and F counts shared dependencies.",
        "",
    ]
    for rnd, label in ROUNDS.items():
        name = "compsac_pg_epoch_dev" if rnd == "epoch" else f"compsac_pg_scope_dev_{rnd}"
        file = ROOT / "proof/artifacts" / f"{name}.json"
        doc = json.loads(file.read_bytes())
        if doc["server_version_num"] != 160004 or doc["operations_per_campaign"] != 96:
            raise ValueError("incompatible_campaign")
        rows = {(r["workers"], r["fanout"], r["seed"], r["arm"]): r for r in doc["rows"]}
        configs = [(4, 8)] if rnd == "epoch" else list(product((1, 4), (1, 8)))
        expected = {(w, f, s, a) for w, f in configs for s, a in product(range(6), ARMS)}
        if rows.keys() != expected or len(doc["rows"]) != len(rows):
            raise ValueError("incomplete_or_duplicated_campaigns")
        for r in rows.values():
            c = r["counts"]
            if (
                sum(c.values()) - c.get("retries", 0) != 96
                or 84 - r["missing_valid"] + r["forbidden_installs"] != c["committed"]
                or not math.isclose(c["committed"] / r["seconds"], r["committed_per_second"])
            ):
                raise ValueError("invalid_campaign_accounting")
        lines.extend(
            [
                f"## {rnd}",
                "",
                f"{label} [Campaign records](../proof/artifacts/{name}.json)",
                "",
                "| W | F | Exclusive / SSI | Shared / SSI | SSI commits/s¹ | Retries² | Missing eligible² | Forbidden installs² |",
                "|---:|---:|---:|---:|---:|---|---|---|",
            ]
        )
        for w, f in configs:
            cells = {a: [rows[w, f, s, a] for s in range(6)] for a in ARMS}
            base = [r["committed_per_second"] for r in cells["ssi"]]
            ratios = [
                median(r["committed_per_second"] / b for r, b in zip(cells[a], base, strict=True))
                for a in ARMS[1:]
            ]

            def triplet(field):
                return " / ".join(
                    str(
                        sum(
                            r["counts"].get("retries", 0) if field == "retries" else r[field]
                            for r in cells[a]
                        )
                    )
                    for a in ARMS
                )

            lines.append(
                f"| {w} | {f} | {ratios[0]:.2f} | {ratios[1]:.2f} | {median(base):.1f} | {triplet('retries')} | {triplet('missing_valid')} | {triplet('forbidden_installs')} |"
            )
        lines.append("")
    lines.extend(
        [
            "¹ Median across six campaigns. ² Totals over six campaigns, in SSI / exclusive / shared order. The throughput numerator counts installed proposals. Retries are additional attempts within a proposal.",
            "",
            "Layout, statistics, retry policy and query shape changed during development. Differences across rounds combine these changes with run-to-run variation. In the epoch experiment, the writer advances all eight versions before the next wave starts. This establishes the version seen by each proposal and leaves overlap with the governance writer untested. Finite retries can reduce SSI's committed-work numerator. These campaigns estimate component behavior on a fixed workload. The registered safety and utility endpoints for the dependency-complete kernel still require independent history labels and a fresh workload.",
        ]
    )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(summarize(), end="")
