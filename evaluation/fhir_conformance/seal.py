"""Seal the FHIR conformance evidence (H-007).

Hashes the fixture manifest, run output, and analysis, then writes:

- ``seal/artifact-sha256.json`` — sha256 of every sealed artifact,
- ``seal/seal.json`` — freeze metadata, validator execution status, verdict
  summary, preservation metrics, gaps, and the manual admin-fields gate,
- ``seal/analysis.json`` — narrative separating the HL7 structural result from
  the CLARA application-semantic result (spec 3.8).

A structurally valid Bundle can still violate the product's one-patient or
reference-scope contract; the analysis keeps those layers distinct.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from evaluation.fhir_conformance.freeze import FREEZE_ID, PACKAGE_DIR
from evaluation.fhir_conformance.validator_wrapper import sha256_file

SEAL_DIR = PACKAGE_DIR / "seal"
MANIFEST_PATH = PACKAGE_DIR / "fixtures" / "manifest.json"
RUN_PATH = SEAL_DIR / f"run-{FREEZE_ID}.json"
ARTIFACT_HASH_PATH = SEAL_DIR / "artifact-sha256.json"
SEAL_PATH = SEAL_DIR / "seal.json"
ANALYSIS_PATH = SEAL_DIR / "analysis.json"

SEALED_ARTIFACTS = (
    "support_matrix.md",
    "README.md",
    "validator_wrapper.py",
    "app_semantic.py",
    "preservation.py",
    "freeze.py",
    "run.py",
    "seal.py",
)


def _sealed_files() -> list[Path]:
    files = [PACKAGE_DIR / name for name in SEALED_ARTIFACTS]
    files.extend(sorted((PACKAGE_DIR / "fixtures").rglob("*.json")))
    files.extend(sorted((PACKAGE_DIR / "tests").rglob("*.py")))
    files.extend(
        path
        for path in sorted((PACKAGE_DIR / "seal").rglob("*"))
        if path.is_file()
        and path.name not in {ARTIFACT_HASH_PATH.name, SEAL_PATH.name}
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    )
    return [path for path in files if path.exists()]


def build_artifact_hashes(git_sha: str) -> dict:
    artifacts = {}
    for path in _sealed_files():
        rel = str(path.relative_to(PACKAGE_DIR))
        artifacts[rel] = sha256_file(path)
    return {
        "freeze_id": FREEZE_ID,
        "git_sha": git_sha,
        "artifacts": dict(sorted(artifacts.items())),
    }


def _verdict_counts(run_output: dict) -> dict:
    counts: dict[str, int] = {}
    for fixture in run_output["fixtures"]:
        for verdict in fixture["verdicts"]:
            counts[verdict["verdict"]] = counts.get(verdict["verdict"], 0) + 1
    return counts


def build_analysis(run_output: dict, manifest: dict) -> dict:
    fixtures_rows = []
    for fixture in run_output["fixtures"]:
        expected = next(f for f in manifest["fixtures"] if f["id"] == fixture["id"])["expected"]
        row = {
            "id": fixture["id"],
            "path": fixture["path"],
            "category": fixture["category"],
            "label": fixture["label"],
            "mode": fixture["mode"],
        }
        for verdict in fixture["verdicts"]:
            row[verdict["gate"]] = verdict
        hl7_layer = {
            gate: verdict["detail"]
            for verdict in fixture["verdicts"]
            if gate_hl7(verdict["gate"])
            for gate in [verdict["gate"]]
        }
        app_layer = {
            verdict["gate"]: verdict["detail"]
            for verdict in fixture["verdicts"]
            if not gate_hl7(verdict["gate"])
        }
        row["hl7_structural_layer"] = hl7_layer
        row["app_semantic_layer"] = app_layer
        row["expected"] = expected
        fixtures_rows.append(row)
    structural_summary = _layer_verdict_counts(run_output, structural=True)
    application_summary = _layer_verdict_counts(run_output, structural=False)
    return {
        "freeze_id": FREEZE_ID,
        "separates": {
            "hl7_structural": (
                "Pinned HL7 validator result: structural validity of the Bundle "
                "per the R4/STU3 base specification."
            ),
            "clara_application_semantic": (
                "CLARA import/bench gate result: one-patient rule, reference "
                "scope, supported resource surface, bundle-form scope. A Bundle "
                "can be structurally valid yet violate this contract (spec 3.8)."
            ),
        },
        "validator_execution": run_output["validator"]["execution"],
        "validator_jar_available": run_output["validator"].get("jar_available"),
        "layer_verdict_summary": {
            "hl7_structural": structural_summary,
            "clara_application_semantic": application_summary,
        },
        "fixtures": fixtures_rows,
        "preservation": run_output["preservation"],
        "gaps": run_output["gaps"],
    }


def gate_hl7(gate: str) -> bool:
    return gate.startswith("hl7_")


def _layer_verdict_counts(run_output: dict, *, structural: bool) -> dict[str, int]:
    counts: dict[str, int] = {}
    for fixture in run_output["fixtures"]:
        for verdict in fixture["verdicts"]:
            if gate_hl7(verdict["gate"]) is not structural:
                continue
            counts[verdict["verdict"]] = counts.get(verdict["verdict"], 0) + 1
    return counts


def build_seal(run_output: dict, manifest: dict, git_sha: str) -> dict:
    fixture_counts = {"positive": 0, "negative": 0, "snapshot_input": 0}
    for fixture in manifest["fixtures"]:
        if fixture["category"] == "positive":
            fixture_counts["positive"] += 1
        elif fixture["category"] == "snapshot_input":
            fixture_counts["snapshot_input"] += 1
        else:
            fixture_counts["negative"] += 1
    return {
        "freeze_id": FREEZE_ID,
        "git_sha": git_sha,
        "created_at": datetime.now(UTC).isoformat(),
        "validator": {
            "pin": run_output["validator"].get("pin"),
            "execution": run_output["validator"]["execution"],
            "jar_available": run_output["validator"].get("jar_available"),
            "jar_sha256": run_output["validator"].get("jar_sha256"),
        },
        "fixture_counts": fixture_counts,
        "verdict_summary": _verdict_counts(run_output),
        "layer_verdict_summary": {
            "hl7_structural": _layer_verdict_counts(run_output, structural=True),
            "clara_application_semantic": _layer_verdict_counts(
                run_output, structural=False
            ),
        },
        "preservation": run_output["preservation"],
        "gaps": run_output["gaps"],
        "admin_fields": {
            "status": "MANUAL_GATE",
            "note": (
                "Support letter, signatures, advisor confirmation, and the exact "
                "milestone date are HUMAN administrative gates (H-009, FHIR-05). "
                "They are never fabricated and are not part of this machine seal."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seal the FHIR conformance evidence (freeze + run required)."
    )
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH, help="fixture manifest")
    parser.add_argument("--run", type=Path, default=RUN_PATH, help="run output")
    args = parser.parse_args()
    if not args.run.is_file():
        raise SystemExit(
            f"run output {args.run} not found — run `python -m "
            "evaluation.fhir_conformance.run` first"
        )
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    run_output = json.loads(args.run.read_text(encoding="utf-8"))
    if run_output.get("freeze_id") != manifest.get("freeze_id"):
        raise SystemExit("run output freeze_id does not match the frozen manifest")
    if run_output.get("git_sha") != manifest.get("git_sha"):
        raise SystemExit("run output git_sha does not match the frozen manifest")
    git_sha = manifest["git_sha"]

    analysis = build_analysis(run_output, manifest)
    SEAL_DIR.mkdir(parents=True, exist_ok=True)
    ANALYSIS_PATH.write_text(
        json.dumps(analysis, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    artifact_hashes = build_artifact_hashes(git_sha)
    ARTIFACT_HASH_PATH.write_text(
        json.dumps(artifact_hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    seal = build_seal(run_output, manifest, git_sha)
    seal["artifact_sha256_manifest"] = sha256_file(ARTIFACT_HASH_PATH)
    SEAL_PATH.write_text(json.dumps(seal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"sealed {FREEZE_ID} at {git_sha}")
    print(f"validator execution: {seal['validator']['execution']}")
    print(f"fixtures: {seal['fixture_counts']}")
    print(f"verdicts: {seal['verdict_summary']}")
    print(f"gaps: {len(seal['gaps'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
