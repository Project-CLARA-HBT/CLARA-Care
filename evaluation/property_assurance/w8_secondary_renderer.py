"""Deterministic offline renderer for the sealed W8 GovMut/SOICT study.

GMT-05 (spec 2.8): the renderer reads the *existing* sealed analysis artifact
``research/assurance_soict/results/final-analysis.json`` and renders secondary
endpoints (per-mutant kill matrix, kill fraction, seed instability, first
killing seed, time to first kill, family/layer/invariant mapping, unique kills,
all-survive list, runtime totals). It NEVER re-runs W8, never re-scores it, and
never mutates the sealed artifacts (GMT-01).

The input is byte-verified against the sealed copy
``research/assurance_soict/seal/govmut-soict-2026-final_analysis-v2`` before
any rendering; a mismatch aborts rather than renders stale data.

Available fields are taken verbatim from the frozen ``govmut-final-analysis.v1``
schema. Fields that are ``null`` by the frozen aggregation rule are rendered as
``"N/A"`` (e.g. ``first_killing_seed`` for the unseeded M0 slot) and are never
invented. Runtime totals come from the frozen ``runtime_stats`` block.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from evaluation.evidence_program.freeze import FreezeError

METHOD_IDS = (
    "M0_regression",
    "M1_stateless_property",
    "M2_state_machine",
    "M3_combined",
)
METHOD_LABELS = {
    "M0_regression": "M0",
    "M1_stateless_property": "M1",
    "M2_state_machine": "M2",
    "M3_combined": "M3",
}
LAYER_BY_SOURCE = {
    "services/api/src/clara_api/glhs/gateway.py": "generic gateway",
    "services/api/src/clara_api/glhs/commitment_gateway.py": "commitment gateway",
}
SEALED_ANALYSIS_SHA256 = "e3ab1832c42be2a745ddae4ab960697143688302f78f6f4c08e82ef379278a67"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path, error: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FreezeError(f"{error}: {exc}") from exc
    if not isinstance(value, dict):
        raise FreezeError(error)
    return value


def _read_sealed_analysis(research_dir: Path) -> dict[str, Any]:
    """Load results/final-analysis.json and byte-verify it against the seal."""
    analysis_path = research_dir / "results" / "final-analysis.json"
    sealed_path = research_dir / "seal" / "govmut-soict-2026-final_analysis-v2"
    if not analysis_path.is_file() or not sealed_path.is_file():
        raise FreezeError("govmut_w8_secondary_analysis_or_seal_missing")
    if _sha256_bytes(analysis_path.read_bytes()) != _sha256_bytes(sealed_path.read_bytes()):
        raise FreezeError("govmut_w8_secondary_seal_mismatch")
    if _sha256_bytes(sealed_path.read_bytes()) != SEALED_ANALYSIS_SHA256:
        raise FreezeError("govmut_w8_secondary_seal_hash_mismatch")
    analysis = _load_json(analysis_path, "govmut_w8_secondary_analysis_invalid")
    if analysis.get("schema_version") != "govmut-final-analysis.v1":
        raise FreezeError("govmut_w8_secondary_schema_unsupported")
    return analysis


def _load_catalog(research_dir: Path) -> dict[str, dict[str, str]]:
    catalog = _load_json(
        research_dir / "mutation_site_candidates.json", "govmut_w8_secondary_catalog_invalid"
    )
    candidates = catalog.get("candidates")
    if not isinstance(candidates, list):
        raise FreezeError("govmut_w8_secondary_catalog_invalid")
    fields: dict[str, dict[str, str]] = {}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise FreezeError("govmut_w8_secondary_catalog_invalid")
        mutant_id = candidate.get("id")
        row = {key: candidate.get(key) for key in ("family_seed", "source_path", "anchor")}
        if (
            not isinstance(mutant_id, str)
            or not mutant_id
            or not all(isinstance(value, str) and value for value in row.values())
        ):
            raise FreezeError("govmut_w8_secondary_catalog_invalid")
        fields[mutant_id] = row
    return fields


def _load_family_manifest(research_dir: Path) -> dict[str, dict[str, str]]:
    manifest = _load_json(
        research_dir / "mutation_manifest.json", "govmut_w8_secondary_manifest_invalid"
    )
    seeds = manifest.get("fault_family_seeds")
    if not isinstance(seeds, list):
        raise FreezeError("govmut_w8_secondary_manifest_invalid")
    by_id: dict[str, dict[str, str]] = {}
    for seed in seeds:
        if not isinstance(seed, dict):
            raise FreezeError("govmut_w8_secondary_manifest_invalid")
        seed_id = seed.get("id")
        fault = seed.get("fault")
        invariants = seed.get("invariants")
        if (
            not isinstance(seed_id, str)
            or not isinstance(fault, str)
            or not isinstance(invariants, list)
        ):
            raise FreezeError("govmut_w8_secondary_manifest_invalid")
        by_id[seed_id] = {
            "fault": fault,
            "invariants": ",".join(str(item) for item in sorted(invariants)),
        }
    return by_id


def _layer_for(source_path: str) -> str:
    return LAYER_BY_SOURCE.get(source_path, "other")


def _null(value: Any) -> str:
    return "N/A" if value is None else str(value)


def _round3(value: Any) -> Any:
    return round(value, 3) if isinstance(value, (int, float)) else value


def _render_kill_matrix(
    *,
    per_mutant_method: dict[str, dict[str, dict[str, Any]]],
    family_fields: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for mutant_id in sorted(per_mutant_method):
        row: dict[str, Any] = {"mutant_id": mutant_id}
        for method in METHOD_IDS:
            agg = per_mutant_method[mutant_id][method]
            row[METHOD_LABELS[method]] = agg["detected_any_seed"]
            row[f"{METHOD_LABELS[method]}_kill_fraction"] = _round3(agg["kill_fraction"])
        row["family"] = family_fields[mutant_id]["family_seed"]
        rows.append(row)
    return rows


def _render_seed_stability(
    *, per_mutant_method: dict[str, dict[str, dict[str, Any]]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for mutant_id in sorted(per_mutant_method):
        for method in METHOD_IDS:
            agg = per_mutant_method[mutant_id][method]
            rows.append(
                {
                    "mutant_id": mutant_id,
                    "method": method,
                    "kill_fraction": _round3(agg["kill_fraction"]),
                    "seed_instability": _round3(agg["seed_instability"]),
                    "first_killing_seed": _null(agg["first_killing_seed"]),
                    "time_to_first_kill_ms": _null(_round3(agg["time_to_first_kill_ms"])),
                    "executable_seed_count": agg["executable_seed_count"],
                    "infra_seed_count": agg["infra_seed_count"],
                }
            )
    return rows


def _unique_and_incremental_kills(
    per_mutant_method: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    killed_by: dict[str, set[str]] = {method: set() for method in METHOD_IDS}
    for mutant_id, by_method in per_mutant_method.items():
        for method in METHOD_IDS:
            if by_method[method]["detected_any_seed"] == 1:
                killed_by[method].add(mutant_id)
    unique: dict[str, list[str]] = {}
    for method in METHOD_IDS:
        others = set().union(*(killed_by[other] for other in METHOD_IDS if other != method))
        unique[method] = sorted(killed_by[method] - others)
    union_before: set[str] = set()
    incremental: dict[str, list[str]] = {}
    for method in METHOD_IDS:
        incremental[method] = sorted(killed_by[method] - union_before)
        union_before |= killed_by[method]
    return {
        "killed_sets": {method: sorted(kills) for method, kills in killed_by.items()},
        "unique_kills": unique,
        "incremental_kills": incremental,
        "total_unique": sorted(union_before),
    }


def _render_efficiency(
    *,
    analysis: dict[str, Any],
    unique_kills: dict[str, list[str]],
    incremental_kills: dict[str, list[str]],
) -> list[dict[str, Any]]:
    runtime = analysis["runtime_stats"]["per_method"]
    scores = analysis["mutation_scores"]
    rows: list[dict[str, Any]] = []
    for method in METHOD_IDS:
        total_ms = runtime[method]["total_ms"]
        killed = scores[method]["killed"]
        denominator = scores[method]["denominator"]
        kills_per_minute = round(killed / (total_ms / 60000.0), 3) if total_ms and killed else None
        rows.append(
            {
                "method": method,
                "executions": runtime[method]["count"],
                "total_ms": round(total_ms, 3),
                "mean_ms": _round3(runtime[method]["mean_ms"]),
                "median_ms": _round3(runtime[method]["median_ms"]),
                "killed": killed,
                "denominator": denominator,
                "unique_kills": len(unique_kills[method]),
                "incremental_kills": len(incremental_kills[method]),
                "kills_per_minute": kills_per_minute,
                "cost_per_incremental_kill_ms": (
                    round(total_ms / len(incremental_kills[method]), 3)
                    if len(incremental_kills[method]) > 0
                    else "N/A"
                ),
            }
        )
    return rows


def _field_availability(
    *,
    per_mutant_method: dict[str, dict[str, dict[str, Any]]],
    efficiency: list[dict[str, Any]],
) -> dict[str, Any]:
    """Describe source-backed fields and concrete nulls rendered as N/A."""

    available = [
        "kill_matrix.mutant_id",
        "kill_matrix.M0/M1/M2/M3",
        "kill_matrix.M0/M1/M2/M3.kill_fraction",
        "seed_stability.kill_fraction",
        "seed_stability.seed_instability",
        "seed_stability.executable_seed_count",
        "seed_stability.infra_seed_count",
        "family_layer_invariant.family_seed/fault/invariants/layer/source_path/anchor",
        "unique_incremental_kills.killed_sets/unique_kills/incremental_kills",
        "runtime_stats.per_method",
        "mutation_scores",
        "robustness_scores",
        "paired_method_comparisons",
        "outcome_counts",
    ]
    rendered_as_na: list[str] = []
    for mutant_id in sorted(per_mutant_method):
        for method in METHOD_IDS:
            aggregate = per_mutant_method[mutant_id][method]
            for field in ("first_killing_seed", "time_to_first_kill_ms"):
                if aggregate[field] is None:
                    rendered_as_na.append(f"seed_stability[{mutant_id},{method}].{field}")
    for row in efficiency:
        for field in ("kills_per_minute", "cost_per_incremental_kill_ms"):
            if row[field] is None or row[field] == "N/A":
                rendered_as_na.append(f"efficiency[{row['method']}].{field}")
    return {
        "available": available,
        "rendered_as_na": rendered_as_na,
        "null_policy": (
            "Only nulls present in the sealed govmut-final-analysis.v1 input are "
            "rendered as N/A; no missing metric is imputed."
        ),
    }


def render_secondary_report(*, research_dir: Path, output_dir: Path) -> dict[str, Any]:
    """Render all W8 secondary endpoints deterministically and persist tables."""
    analysis = _read_sealed_analysis(research_dir)
    catalog_fields = _load_catalog(research_dir)
    family_manifest = _load_family_manifest(research_dir)
    per_mutant_method = analysis["per_mutant_method"]

    missing = set(per_mutant_method) - set(catalog_fields)
    if missing:
        raise FreezeError("govmut_w8_secondary_catalog_missing_mutants")

    kill_matrix = _render_kill_matrix(
        per_mutant_method=per_mutant_method, family_fields=catalog_fields
    )
    seed_stability = _render_seed_stability(per_mutant_method=per_mutant_method)

    family_rows: list[dict[str, Any]] = []
    for mutant_id in sorted(per_mutant_method):
        catalog = catalog_fields[mutant_id]
        family = catalog["family_seed"]
        family_rows.append(
            {
                "mutant_id": mutant_id,
                "family_seed": family,
                "fault": family_manifest.get(family, {}).get("fault", "N/A"),
                "invariants": family_manifest.get(family, {}).get("invariants", "N/A"),
                "layer": _layer_for(catalog["source_path"]),
                "source_path": catalog["source_path"],
                "anchor": catalog["anchor"],
            }
        )

    all_survive = [
        mutant_id
        for mutant_id in sorted(per_mutant_method)
        if all(
            per_mutant_method[mutant_id][method]["detected_any_seed"] == 0 for method in METHOD_IDS
        )
    ]
    unique_incremental = _unique_and_incremental_kills(per_mutant_method)
    efficiency = _render_efficiency(
        analysis=analysis,
        unique_kills=unique_incremental["unique_kills"],
        incremental_kills=unique_incremental["incremental_kills"],
    )
    field_availability = _field_availability(
        per_mutant_method=per_mutant_method, efficiency=efficiency
    )

    report: dict[str, Any] = {
        "schema_version": "govmut-w8-secondary-report.v1",
        "status": "rendered_from_sealed_analysis",
        "freeze_id": analysis["freeze_id"],
        "run_sha256": analysis["run_sha256"],
        "sealed_analysis_sha256": SEALED_ANALYSIS_SHA256,
        "source_artifacts": {
            "analysis": str((research_dir / "results" / "final-analysis.json").resolve()),
            "seal": str((research_dir / "seal" / "govmut-soict-2026-final_analysis-v2").resolve()),
        },
        "note": (
            "Rendered deterministically from the sealed W8 analysis; W8 was not "
            "re-run or re-scored. All fields come from the frozen "
            "govmut-final-analysis.v1 schema; N/A marks fields the frozen "
            "aggregation leaves unrecorded (e.g. first_killing_seed for the "
            "unseeded M0 slot, time_to_first_kill_ms for never-killed slots)."
        ),
        "method_labels": METHOD_LABELS,
        "methods": list(METHOD_IDS),
        "kill_matrix": kill_matrix,
        "seed_stability": seed_stability,
        "family_layer_invariant": family_rows,
        "unique_incremental_kills": unique_incremental,
        "all_survive": all_survive,
        "all_survive_count": len(all_survive),
        "efficiency": efficiency,
        "field_availability": field_availability,
        "runtime_stats": analysis["runtime_stats"],
        "mutation_scores": analysis["mutation_scores"],
        "robustness_scores": analysis["robustness_scores"],
        "paired_method_comparisons": analysis["paired_method_comparisons"],
        "outcome_counts": analysis["outcome_counts"],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_markdown_tables(report, output_dir)
    (output_dir / "w8_secondary_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def _md_escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _write_markdown_tables(report: dict[str, Any], output_dir: Path) -> None:
    header = [
        "Mutant",
        "Family",
        "Layer",
        *[f"{label} killed" for label in ("M0", "M1", "M2", "M3")],
    ]
    lines = ["# W8 kill matrix (45 x strategy, detected_any_seed)", ""]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "---|" * len(header))
    for row in report["kill_matrix"]:
        cells = [
            row["mutant_id"],
            row["family"],
            _layer_for(
                next(
                    item["source_path"]
                    for item in report["family_layer_invariant"]
                    if item["mutant_id"] == row["mutant_id"]
                )
            ),
            *(str(row[label]) for label in ("M0", "M1", "M2", "M3")),
        ]
        lines.append("| " + " | ".join(_md_escape(cell) for cell in cells) + " |")
    (output_dir / "w8_kill_matrix.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    fli_lines = [
        "# W8 family / layer / invariant mapping",
        "",
        "| Mutant | Family | Fault | Invariants | Layer | Source | Anchor |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in report["family_layer_invariant"]:
        fli_lines.append(
            "| "
            + " | ".join(
                _md_escape(row[key])
                for key in (
                    "mutant_id",
                    "family_seed",
                    "fault",
                    "invariants",
                    "layer",
                    "source_path",
                    "anchor",
                )
            )
            + " |"
        )
    (output_dir / "w8_family_layer_invariant.md").write_text(
        "\n".join(fli_lines) + "\n", encoding="utf-8"
    )

    survive_lines = [
        "# W8 all-survive mutants (25; no method killed them)",
        "",
        f"Count: {report['all_survive_count']}",
        "",
        "| Mutant |",
        "|---|---|",
    ]
    for mutant_id in report["all_survive"]:
        survive_lines.append(f"| {mutant_id} |")
    (output_dir / "w8_all_survive.md").write_text("\n".join(survive_lines) + "\n", encoding="utf-8")

    stab_header = [
        "Mutant",
        "Method",
        "kill_fraction",
        "seed_instability",
        "first_killing_seed",
        "time_to_first_kill_ms",
        "executable_seeds",
        "infra_seeds",
    ]
    stab_lines = ["# W8 seed stability / kill fraction / time to first kill", ""]
    stab_lines.append("| " + " | ".join(stab_header) + " |")
    stab_lines.append("|" + "---|" * len(stab_header))
    for row in report["seed_stability"]:
        stab_lines.append(
            "| "
            + " | ".join(
                _md_escape(row[key])
                for key in (
                    "mutant_id",
                    "method",
                    "kill_fraction",
                    "seed_instability",
                    "first_killing_seed",
                    "time_to_first_kill_ms",
                    "executable_seed_count",
                    "infra_seed_count",
                )
            )
            + " |"
        )
    (output_dir / "w8_seed_stability.md").write_text("\n".join(stab_lines) + "\n", encoding="utf-8")

    eff_header = [
        "method",
        "executions",
        "total_ms",
        "mean_ms",
        "median_ms",
        "killed",
        "denominator",
        "unique_kills",
        "incremental_kills",
        "kills_per_minute",
        "cost_per_incremental_kill_ms",
    ]
    eff_lines = [
        "# W8 runtime totals and derived efficiency (non-budget-normalized)",
        "",
        (
            "These efficiency rows are derived from the sealed runtime_stats and are "
            "explicitly NOT budget-normalized (GMT-04); W8 strategies ran with "
            "unconstrained wall-clock budgets."
        ),
        "",
    ]
    eff_lines.append("| " + " | ".join(eff_header) + " |")
    eff_lines.append("|" + "---|" * len(eff_header))
    for row in report["efficiency"]:
        eff_lines.append("| " + " | ".join(_md_escape(row[key]) for key in eff_header) + " |")
    (output_dir / "w8_runtime_efficiency.md").write_text(
        "\n".join(eff_lines) + "\n", encoding="utf-8"
    )

    availability_lines = [
        "# W8 field availability",
        "",
        (
            "Available fields are copied or deterministically derived from the sealed "
            "analysis. Concrete nulls are rendered as `N/A`; no values are imputed."
        ),
        "",
        "## Available",
        "",
    ]
    availability_lines.extend(f"- `{field}`" for field in report["field_availability"]["available"])
    availability_lines.extend(["", "## Rendered as N/A", ""])
    availability_lines.extend(
        f"- `{field}`" for field in report["field_availability"]["rendered_as_na"]
    )
    (output_dir / "w8_field_availability.md").write_text(
        "\n".join(availability_lines) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--research-dir",
        type=Path,
        default=Path("research/assurance_soict"),
        help="research/assurance_soict directory (default: ./research/assurance_soict)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("research/assurance_soict/w8_secondary_report"),
        help="output directory for rendered tables (default: ./research/assurance_soict/w8_secondary_report)",
    )
    args = parser.parse_args()
    report = render_secondary_report(research_dir=args.research_dir, output_dir=args.output_dir)
    print(
        json.dumps(
            {
                "status": report["status"],
                "freeze_id": report["freeze_id"],
                "all_survive_count": report["all_survive_count"],
                "output_dir": str(args.output_dir),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
