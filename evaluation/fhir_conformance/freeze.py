"""Freeze the FHIR conformance fixture manifest (H-007).

Generates ``evaluation/fhir_conformance/fixtures/manifest.json`` containing:
per-fixture sha256, expected outcomes per gate (HL7 structural + CLARA
application-semantic), the pinned validator coordinate, and the git SHA.

``EXPECTED_OUTCOMES`` is the single declared contract for the fixture set. If a
fixture on disk is not declared here, or a declared path is missing, the freeze
fails — orphan fixtures are not silently carried along.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evaluation.fhir_conformance.validator_wrapper import (
    load_pin,
    sha256_file,
)

PACKAGE_DIR = Path(__file__).resolve().parent
FREEZE_ID = "FHIR-CONFORMANCE-V1-20260819"
MANIFEST_PATH = PACKAGE_DIR / "fixtures" / "manifest.json"

# path (relative to package dir) -> declaration.
# `expected` keys are gate names; each value is {accepted: bool} for app gates
# and {structural: "valid"|"error"} for hl7 gates.
EXPECTED_OUTCOMES: dict[str, dict[str, Any]] = {
    "fixtures/positive/r4/lifemap-summary-r4.json": {
        "id": "pos-r4-golden",
        "label": "repo",
        "category": "positive",
        "mode": "r4",
        "gates": ["hl7_r4", "api_r4", "bench_r4"],
        "notes": "repo fixture services/api/tests/fixtures/fhir/lifemap-summary-r4.json",
        "expected": {
            "hl7_r4": {"structural": "valid"},
            "api_r4": {"accepted": True},
            "bench_r4": {"accepted": True},
        },
    },
    "fixtures/positive/r4/lifemap-full-export-r4.json": {
        "id": "pos-r4-full",
        "label": "synthetic",
        "category": "positive",
        "mode": "r4",
        "gates": ["hl7_r4", "api_r4", "bench_r4"],
        "notes": (
            "mapper-shaped full export surface; synthetic, no real data; bench_r4 "
            "rejects the product urn reference convention (cross_subject_reference)"
        ),
        "expected": {
            "hl7_r4": {"structural": "valid"},
            "api_r4": {"accepted": True},
            "bench_r4": {"accepted": False},
        },
    },
    "fixtures/positive/r4/lifemap-document-r4.json": {
        "id": "pos-r4-document",
        "label": "synthetic",
        "category": "positive",
        "mode": "r4",
        "gates": ["hl7_r4", "api_r4", "bench_r4"],
        "notes": (
            "document bundle form; Composition first entry; bench supports only "
            "collection/transaction"
        ),
        "expected": {
            "hl7_r4": {"structural": "valid"},
            "api_r4": {"accepted": True},
            "bench_r4": {"accepted": False},
        },
    },
    "fixtures/positive/r4/bench-r4-collection.json": {
        "id": "pos-r4-bench-collection",
        "label": "synthetic",
        "category": "positive",
        "mode": "r4",
        "gates": ["hl7_r4", "api_r4", "bench_r4"],
        "notes": (
            "bench R4 collection incl. ServiceRequest; ServiceRequest is outside "
            "the product API's 15-type surface so api_r4 rejects by design"
        ),
        "expected": {
            "hl7_r4": {"structural": "valid"},
            "api_r4": {"accepted": False},
            "bench_r4": {"accepted": True},
        },
    },
    "fixtures/positive/r4/bench-r4-transaction.json": {
        "id": "pos-r4-bench-transaction",
        "label": "synthetic",
        "category": "positive",
        "mode": "r4",
        "gates": ["hl7_r4", "api_r4", "bench_r4"],
        "notes": "transaction bundle form; bench accepts, product API rejects by design",
        "expected": {
            "hl7_r4": {"structural": "valid"},
            "api_r4": {"accepted": False},
            "bench_r4": {"accepted": True},
        },
    },
    "fixtures/positive/stu3/bench-stu3-collection.json": {
        "id": "pos-stu3-bench-collection",
        "label": "synthetic",
        "category": "positive",
        "mode": "stu3",
        "gates": ["hl7_stu3", "api_r4", "bench_stu3"],
        "notes": (
            "bench STU3 collection incl. ProcedureRequest; product API is R4-only "
            "and rejects STU3-only types by design"
        ),
        "expected": {
            "hl7_stu3": {"structural": "valid"},
            "api_r4": {"accepted": False},
            "bench_stu3": {"accepted": True},
        },
    },
    "fixtures/negative/missing-patient.json": {
        "id": "neg-missing-patient",
        "label": "synthetic",
        "category": "missing_patient",
        "mode": "r4",
        "gates": ["hl7_r4", "api_r4", "bench_r4"],
        "notes": "FHIR-02: missing Patient",
        "expected": {
            "hl7_r4": {"structural": "valid"},
            "api_r4": {"accepted": False},
            "bench_r4": {"accepted": False},
        },
    },
    "fixtures/negative/multiple-patient.json": {
        "id": "neg-multiple-patient",
        "label": "synthetic",
        "category": "multiple_patient",
        "mode": "r4",
        "gates": ["hl7_r4", "api_r4", "bench_r4"],
        "notes": "FHIR-02: multiple Patient where unsupported",
        "expected": {
            "hl7_r4": {"structural": "valid"},
            "api_r4": {"accepted": False},
            "bench_r4": {"accepted": False},
        },
    },
    "fixtures/negative/cross-subject-reference.json": {
        "id": "neg-cross-subject-reference",
        "label": "synthetic",
        "category": "cross_subject_reference",
        "mode": "r4",
        "gates": ["hl7_r4", "api_r4", "bench_r4"],
        "notes": "FHIR-02: wrong/cross-subject reference",
        "expected": {
            "hl7_r4": {"structural": "valid"},
            "api_r4": {"accepted": False},
            "bench_r4": {"accepted": False},
        },
    },
    "fixtures/negative/wrong-patient-reference.json": {
        "id": "neg-wrong-patient-reference",
        "label": "synthetic",
        "category": "wrong_patient_reference",
        "mode": "r4",
        "gates": ["hl7_r4", "api_r4", "bench_r4"],
        "notes": "FHIR-02: resource points at a Patient id absent from the bundle",
        "expected": {
            "hl7_r4": {"structural": "valid"},
            "api_r4": {"accepted": False},
            "bench_r4": {"accepted": False},
        },
    },
    "fixtures/negative/dangling-reference.json": {
        "id": "neg-dangling-reference",
        "label": "synthetic",
        "category": "reference_rejection",
        "mode": "r4",
        "gates": ["hl7_r4", "api_r4", "bench_r4"],
        "notes": (
            "FHIR-02: dangling reference; bench reference-scope is subject-only "
            "and does not resolve CarePlan.goal, so bench accepts"
        ),
        "expected": {
            "hl7_r4": {"structural": "valid"},
            "api_r4": {"accepted": False},
            "bench_r4": {"accepted": True},
        },
    },
    "fixtures/negative/unsupported-resource.json": {
        "id": "neg-unsupported-resource",
        "label": "synthetic",
        "category": "resource_unsupported",
        "mode": "r4",
        "gates": ["hl7_r4", "api_r4", "bench_r4"],
        "notes": (
            "FHIR-02: unsupported resource (Procedure is valid R4 but outside the "
            "product API surface); bench silently drops it"
        ),
        "expected": {
            "hl7_r4": {"structural": "valid"},
            "api_r4": {"accepted": False},
            "bench_r4": {"accepted": True},
        },
    },
    "fixtures/negative/invalid-temporal.json": {
        "id": "neg-invalid-temporal",
        "label": "synthetic",
        "category": "temporal_error",
        "mode": "r4",
        "gates": ["hl7_r4", "api_r4", "bench_r4"],
        "notes": (
            "FHIR-02: invalid temporal field (2026-02-30); HL7 rejects, CLARA "
            "import gate does not parse temporal values — recorded as a gap; "
            "bench refs use the product urn convention so bench_r4 rejects on "
            "reference scope, not on the temporal value"
        ),
        "expected": {
            "hl7_r4": {"structural": "error"},
            "api_r4": {"accepted": True},
            "bench_r4": {"accepted": False},
        },
    },
    "fixtures/negative/provenance-loss.json": {
        "id": "neg-provenance-loss",
        "label": "synthetic",
        "category": "provenance_loss",
        "mode": "r4",
        "gates": ["hl7_r4", "api_r4", "bench_r4"],
        "notes": (
            "FHIR-02: provenance/source identity loss; Provenance is present in the "
            "bundle but the import gate accepts it without retaining a Provenance "
            "candidate; bench does not emit Provenance events"
        ),
        "expected": {
            "hl7_r4": {"structural": "valid"},
            "api_r4": {"accepted": True},
            "bench_r4": {"accepted": False},
        },
    },
    "fixtures/negative/duplicate-replay.json": {
        "id": "neg-duplicate-replay",
        "label": "synthetic",
        "category": "replay",
        "mode": "r4",
        "gates": ["hl7_r4", "api_r4", "bench_r4"],
        "notes": (
            "FHIR-02: duplicate/replayed bundle — byte-identical to "
            "lifemap-summary-r4.json (same sha256); parse gate is idempotent; "
            "endpoint-level replay protection uses Idempotency-Key (N/D offline)"
        ),
        "expected": {
            "hl7_r4": {"structural": "valid"},
            "api_r4": {"accepted": True},
            "bench_r4": {"accepted": True},
        },
    },
    "fixtures/negative/version-mismatch-stu3-r4.json": {
        "id": "neg-version-mismatch",
        "label": "synthetic",
        "category": "version_mismatch",
        "mode": "stu3",
        "gates": ["hl7_stu3", "api_r4", "bench_stu3"],
        "notes": (
            "FHIR-02: STU3/R4 version mismatch — ServiceRequest (R4-only resource) "
            "in a STU3-claimed bundle"
        ),
        "expected": {
            "hl7_stu3": {"structural": "error"},
            "api_r4": {"accepted": False},
            "bench_stu3": {"accepted": True},
        },
    },
    "fixtures/snapshot-inputs/export-snapshot.json": {
        "id": "snapshot_input",
        "label": "synthetic",
        "category": "snapshot_input",
        "mode": "n/a",
        "gates": [],
        "notes": "CLARA canonical snapshot input for export-path temporal mapping",
        "expected": {},
    },
}


def _git_sha() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout.strip() or "unknown"


def build_manifest() -> dict[str, Any]:
    pin = load_pin()
    on_disk = sorted(
        str(path.relative_to(PACKAGE_DIR))
        for path in (PACKAGE_DIR / "fixtures").rglob("*.json")
        if path.name != "manifest.json"
    )
    declared = set(EXPECTED_OUTCOMES)
    orphans = sorted(set(on_disk) - declared)
    missing = sorted(declared - set(on_disk))
    if orphans:
        raise SystemExit(
            f"freeze failed: fixture files on disk without an expected-outcome "
            f"declaration: {orphans}"
        )
    if missing:
        raise SystemExit(f"freeze failed: declared fixtures missing on disk: {missing}")
    fixtures = []
    for rel_path in on_disk:
        declaration = EXPECTED_OUTCOMES[rel_path]
        fixtures.append(
            {
                "id": declaration["id"],
                "path": rel_path,
                "sha256": sha256_file(PACKAGE_DIR / rel_path),
                "label": declaration["label"],
                "category": declaration["category"],
                "mode": declaration["mode"],
                "gates": declaration["gates"],
                "expected": declaration["expected"],
                "notes": declaration["notes"],
            }
        )
    return {
        "freeze_id": FREEZE_ID,
        "created_at": datetime.now(UTC).isoformat(),
        "git_sha": _git_sha(),
        "validator_pin": {
            "version": pin.version,
            "artifact": pin.artifact,
            "url": pin.url,
            "sha256": pin.sha256,
        },
        "fixtures": fixtures,
    }


def load_frozen_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    """Load the manifest and refuse to run if a frozen fixture changed."""
    if not path.is_file():
        raise SystemExit(f"frozen manifest {path} not found; run freeze first")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("freeze_id") != FREEZE_ID:
        raise SystemExit(
            f"unexpected freeze_id {manifest.get('freeze_id')!r}; expected {FREEZE_ID!r}"
        )
    for fixture in manifest.get("fixtures", []):
        fixture_path = PACKAGE_DIR / fixture["path"]
        if not fixture_path.is_file():
            raise SystemExit(f"frozen fixture missing: {fixture['path']}")
        actual_sha256 = sha256_file(fixture_path)
        if actual_sha256 != fixture.get("sha256"):
            raise SystemExit(
                f"frozen fixture changed: {fixture['path']} "
                f"(expected {fixture.get('sha256')}, got {actual_sha256})"
            )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the FHIR conformance fixture manifest.")
    parser.add_argument(
        "--output",
        type=Path,
        default=MANIFEST_PATH,
        help="output manifest path (default: fixtures/manifest.json)",
    )
    args = parser.parse_args()
    manifest = build_manifest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    fixture_count = len(manifest["fixtures"])
    positive = sum(1 for f in manifest["fixtures"] if f["category"] == "positive")
    negative = sum(
        1 for f in manifest["fixtures"] if f["category"] not in {"positive", "snapshot_input"}
    )
    print(
        f"freeze {manifest['freeze_id']} at {manifest['git_sha']}: "
        f"{fixture_count} fixtures ({positive} positive, {negative} negative)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
