"""Run the FHIR conformance batch (H-007).

Executes:
1. the pinned HL7 validator over every fixture that declares an ``hl7_*`` gate
   (JAR resolved per the toolchain lock; offline -> honest PENDING records),
2. the CLARA application-semantic gates (api_r4 / bench_r4 / bench_stu3),
3. preservation and temporal-mapping metrics.

Writes ``seal/run-<freeze_id>.json`` plus a ``seal/latest-run.json`` copy and
raw validator logs under ``seal/validator-logs/``.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evaluation.fhir_conformance import app_semantic
from evaluation.fhir_conformance.app_semantic import GateResult
from evaluation.fhir_conformance.freeze import (
    FREEZE_ID,
    MANIFEST_PATH,
    PACKAGE_DIR,
    load_frozen_manifest,
)
from evaluation.fhir_conformance.preservation import compute_metrics
from evaluation.fhir_conformance.validator_wrapper import (
    load_pin,
    resolve_jar,
    sha256_file,
    validate_file,
)

SEAL_DIR = PACKAGE_DIR / "seal"
LOGS_DIR = SEAL_DIR / "validator-logs"

HL7_GATE_TO_MODE = {"hl7_r4": "r4", "hl7_stu3": "stu3"}
APP_GATES = ("api_r4", "bench_r4", "bench_stu3")


def _run_gate(gate: str, bundle: dict[str, Any]) -> GateResult:
    if gate == "api_r4":
        return app_semantic.api_r4_gate(bundle)
    if gate in {"bench_r4", "bench_stu3"}:
        return app_semantic.bench_gate(bundle, gate.split("_", 1)[1])
    raise ValueError(f"unknown gate {gate}")


def _verdict(gate: str, expected: dict[str, Any], observed: dict[str, Any]) -> dict:
    if gate.startswith("hl7_"):
        if observed.get("execution") == "PENDING":
            return {"gate": gate, "verdict": "PENDING", "detail": observed.get("reason", "")}
        passed = observed.get("structural") == expected.get("structural")
        return {
            "gate": gate,
            "verdict": "PASS" if passed else "MISMATCH",
            "detail": f"structural={observed.get('structural')}",
        }
    if not observed.get("available"):
        return {
            "gate": gate,
            "verdict": "PENDING",
            "detail": "; ".join(observed.get("notes", [])),
        }
    passed = observed.get("accepted") is expected.get("accepted")
    return {
        "gate": gate,
        "verdict": "PASS" if passed else "MISMATCH",
        "detail": (f"accepted={observed.get('accepted')} errors={observed.get('errors', [])}"),
    }


def _collect_gaps(
    manifest: dict[str, Any],
    results: dict[str, dict[str, GateResult]],
    validator: dict[str, Any],
) -> list[dict[str, str]]:
    gaps: list[dict[str, str]] = []
    if validator["execution"] == "PENDING":
        gaps.append(
            {
                "fixture": "*",
                "category": "validator_execution",
                "message": (
                    "Pinned HL7 validator JAR unavailable/undownloadable in this "
                    "environment; HL7 structural results are PENDING and must be "
                    "rerun with the JAR before asserting structural conformance."
                ),
            }
        )
    for fixture in manifest["fixtures"]:
        expected = fixture["expected"]
        observed = results[fixture["id"]]
        for hl7_gate, app_gate in (
            ("hl7_r4", "api_r4"),
            ("hl7_stu3", "bench_stu3"),
        ):
            if hl7_gate not in expected:
                continue
            if expected.get(hl7_gate, {}).get("structural") == "error":
                app_result = observed.get(app_gate)
                if app_result is not None and app_result.available and app_result.accepted is True:
                    gaps.append(
                        {
                            "fixture": fixture["id"],
                            "category": fixture["category"],
                            "message": (
                                f"HL7 {hl7_gate.replace('hl7_', '')} rejects this "
                                "fixture but the "
                                f"{app_gate} application gate accepts it; the CLARA "
                                "gate does not validate this domain."
                            ),
                        }
                    )
        if fixture["category"] == "replay":
            gaps.append(
                {
                    "fixture": fixture["id"],
                    "category": "replay",
                    "message": (
                        "Duplicate/replay protection is endpoint-level "
                        "(Idempotency-Key + payload digest); not measurable offline "
                        "without the DB-backed API."
                    ),
                }
            )
        if fixture["category"] == "provenance_loss":
            gaps.append(
                {
                    "fixture": fixture["id"],
                    "category": "provenance_loss",
                    "message": (
                        "Provenance is accepted by the import gate but never becomes "
                        "a capture candidate (documented product policy); provenance "
                        "preservation is therefore N/D for import candidates."
                    ),
                }
            )
        if fixture["id"] == "pos-stu3-bench-collection":
            gaps.append(
                {
                    "fixture": fixture["id"],
                    "category": "temporal_mapping",
                    "message": (
                        "Bench temporal mapping does not parse STU3 canonical "
                        "ProcedureRequest.occurrenceDateTime (valid_at stays None); "
                        "counted in temporal_mapping_correctness:bench_stu3."
                    ),
                }
            )
    return gaps


def run_batch() -> dict[str, Any]:
    manifest = load_frozen_manifest(MANIFEST_PATH)
    logs_dir = LOGS_DIR
    logs_dir.mkdir(parents=True, exist_ok=True)

    # 1. HL7 validator batch.
    validator_fixtures = [
        (PACKAGE_DIR / f["path"], HL7_GATE_TO_MODE[gate])
        for f in manifest["fixtures"]
        for gate in f["gates"]
        if gate in HL7_GATE_TO_MODE
    ]
    validator_results: dict[str, Any] = {"execution": "N/A", "fixtures": []}
    if validator_fixtures:
        jar = resolve_jar()
        per_file: list[dict[str, Any]] = []
        executed = 0
        for fixture_path, mode in validator_fixtures:
            record = validate_file(fixture_path, mode)
            output_tail = record.pop("output_tail", "")
            if record["execution"] == "OK":
                executed += 1
                fixture_id = next(
                    f["id"] for f in manifest["fixtures"] if PACKAGE_DIR / f["path"] == fixture_path
                )
                (logs_dir / f"{fixture_id}.{mode}.txt").write_text(output_tail, encoding="utf-8")
            per_file.append(record)
        pin = load_pin()
        validator_results = {
            "execution": "OK" if executed == len(per_file) else "PENDING",
            "pin": {
                "version": pin.version,
                "artifact": pin.artifact,
                "sha256": pin.sha256,
            },
            "jar_available": jar is not None,
            "jar_sha256": sha256_file(jar) if jar is not None else None,
            "fixtures": per_file,
        }

    # 2. Application-semantic gates (execute once, reuse objects).
    gate_results: dict[str, dict[str, GateResult]] = {}
    bundles: dict[str, dict[str, Any]] = {}
    for fixture in manifest["fixtures"]:
        path = PACKAGE_DIR / fixture["path"]
        bundle = json.loads(path.read_text(encoding="utf-8"))
        bundles[fixture["id"]] = bundle
        gate_results[fixture["id"]] = {
            gate: _run_gate(gate, bundle) for gate in fixture["gates"] if gate in APP_GATES
        }

    # 3. Verdicts.
    hl7_by_path = {Path(record["fixture"]): record for record in validator_results["fixtures"]}
    fixtures_out = []
    for fixture in manifest["fixtures"]:
        observed_app = gate_results[fixture["id"]]
        verdicts = []
        for gate in fixture["gates"]:
            if gate in APP_GATES:
                verdicts.append(
                    _verdict(
                        gate,
                        fixture["expected"].get(gate, {}),
                        _summary(observed_app[gate]),
                    )
                )
            else:
                verdicts.append(
                    _verdict(
                        gate,
                        fixture["expected"].get(gate, {}),
                        hl7_by_path.get(PACKAGE_DIR / fixture["path"], {}),
                    )
                )
        structural = {v["gate"]: v for v in verdicts if v["gate"].startswith("hl7_")}
        application = {
            v["gate"]: v for v in verdicts if not v["gate"].startswith("hl7_")
        }
        fixtures_out.append(
            {
                "id": fixture["id"],
                "path": fixture["path"],
                "sha256": fixture["sha256"],
                "category": fixture["category"],
                "mode": fixture["mode"],
                "label": fixture["label"],
                "verdicts": verdicts,
                "structural": structural,
                "application_semantic": application,
                "app": {gate: _summary(result) for gate, result in observed_app.items()},
            }
        )

    # 4. Preservation / temporal metrics.
    metrics = compute_metrics(manifest, bundles, gate_results)
    gaps = _collect_gaps(manifest, gate_results, validator_results)

    run_output = {
        "freeze_id": manifest["freeze_id"],
        "git_sha": manifest["git_sha"],
        "created_at": datetime.now(UTC).isoformat(),
        "validator": validator_results,
        "fixtures": fixtures_out,
        "preservation": metrics,
        "gaps": gaps,
    }
    SEAL_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(run_output, indent=2, sort_keys=True) + "\n"
    (SEAL_DIR / f"run-{FREEZE_ID}.json").write_text(payload, encoding="utf-8")
    (SEAL_DIR / "latest-run.json").write_text(payload, encoding="utf-8")
    return run_output


def _summary(result: GateResult) -> dict[str, Any]:
    return {
        "available": result.available,
        "accepted": result.accepted,
        "errors": result.errors,
        "candidate_count": result.candidate_count,
        "event_count": result.event_count,
        "dropped_types": result.dropped_types,
        "notes": result.notes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the FHIR conformance validator batch and gates."
    )
    parser.parse_args()
    output = run_batch()
    print(f"freeze_id: {output['freeze_id']}")
    print(f"git_sha:   {output['git_sha']}")
    print(
        f"validator: execution={output['validator']['execution']} "
        f"jar_available={output['validator'].get('jar_available')}"
    )
    for fixture in output["fixtures"]:
        verdicts = "; ".join(f"{v['gate']}={v['verdict']}" for v in fixture["verdicts"])
        print(f"  {fixture['id']:<28} {verdicts}")
    for name, metric in output["preservation"].items():
        if isinstance(metric, dict) and "ratio" in metric:
            print(
                f"metric {name:<50} n={metric['n']} d={metric['d']} "
                f"ratio={metric['ratio']} na={metric['na']}"
            )
    print(f"gaps: {len(output['gaps'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
