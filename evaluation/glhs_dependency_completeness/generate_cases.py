"""Generate structured test cases for dependency completeness experiments.

Each case represents a clinical operation with its expected minimum dependency
vector, structured application-semantic inputs, and metadata for mutation.

Case schema version: ``dep-completeness-case.v1``
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


CASE_SCHEMA_VERSION = "dep-completeness-case.v1"

# Domain configurations mirroring risk.py
DOMAIN_CONFIGS: dict[str, dict[str, Any]] = {
    "medications": {
        "semantic_keys": ["metformin", "lisinopril", "aspirin"],
        "evidence_ids": ["ev-lab-001", "ev-rx-002"],
        "policy_version": "glhs.v1",
        "consent_version": "medical_disclaimer:v3:42",
    },
    "allergies": {
        "semantic_keys": ["penicillin", "sulfa"],
        "evidence_ids": ["ev-allergy-report-001"],
        "policy_version": "glhs.v1",
        "consent_version": "medical_disclaimer:v3:42",
    },
    "conditions": {
        "semantic_keys": ["type_2_diabetes", "hypertension"],
        "evidence_ids": ["ev-dx-001"],
        "policy_version": "glhs.v1",
        "consent_version": "medical_disclaimer:v3:42",
    },
    "observations": {
        "semantic_keys": ["hba1c", "blood_pressure_systolic"],
        "evidence_ids": ["ev-obs-001", "ev-obs-002"],
        "policy_version": "glhs.v1",
        "consent_version": "medical_disclaimer:v3:42",
    },
}

OPERATION_KINDS = [
    "COMMIT_PROPOSAL",
    "ACTIVATE_ASSERTION",
    "SUPERSEDE_ASSERTION",
    "RESOLVE_CONFLICT",
    "RECONCILE_MEDICATION",
    "IMPORT_FHIR_BUNDLE",
    "RECORD_OBSERVATION",
]


@dataclass
class TestCase:
    case_id: str
    schema_version: str
    operation_kind: str
    domain: str
    semantic_keys: list[str]
    evidence_ids: list[str]
    policy_version: str
    consent_version: str
    policy_domain: str | None
    observed_entity_versions: dict[str, int]
    expected_dep_kinds: list[str]
    expected_dep_count_min: int
    description: str
    created_at: str


def _entity_versions(domain: str, keys: list[str]) -> dict[str, int]:
    """Simulate observed entity versions (all at version 1)."""
    return {f"{domain}:{k}": 1 for k in keys}


def generate_cases() -> list[dict[str, Any]]:
    """Generate the full matrix of test cases."""
    cases: list[dict[str, Any]] = []

    for op_kind in OPERATION_KINDS:
        for domain, cfg in DOMAIN_CONFIGS.items():
            # Skip incompatible combinations
            if op_kind == "RECONCILE_MEDICATION" and domain != "medications":
                continue

            skeys = cfg["semantic_keys"]
            eids = cfg["evidence_ids"]

            # For operations that don't require evidence, clear evidence_ids
            needs_evidence = op_kind in {
                "COMMIT_PROPOSAL",
                "ACTIVATE_ASSERTION",
                "RECONCILE_MEDICATION",
                "RECORD_OBSERVATION",
            }

            expected_kinds = ["GOVERNANCE"]  # policy always required
            expected_kinds.append("GOVERNANCE")  # consent always required
            expected_kinds.extend(["ENTITY"] * len(skeys))
            if needs_evidence:
                expected_kinds.extend(["EVIDENCE"] * len(eids))

            case = TestCase(
                case_id=f"case-{op_kind.lower()}-{domain}-{uuid4().hex[:8]}",
                schema_version=CASE_SCHEMA_VERSION,
                operation_kind=op_kind,
                domain=domain,
                semantic_keys=skeys,
                evidence_ids=eids if needs_evidence else [],
                policy_version=cfg["policy_version"],
                consent_version=cfg["consent_version"],
                policy_domain=domain,
                observed_entity_versions=_entity_versions(domain, skeys),
                expected_dep_kinds=sorted(expected_kinds),
                expected_dep_count_min=len(expected_kinds),
                description=(
                    f"{op_kind} on {domain} with {len(skeys)} entities"
                    f"{f' and {len(eids)} evidence items' if needs_evidence else ''}"
                ),
                created_at=datetime.now(UTC).isoformat(),
            )
            cases.append(asdict(case))

    # Multi-entity write-skew case
    cases.append(asdict(TestCase(
        case_id=f"case-multi-entity-write-skew-{uuid4().hex[:8]}",
        schema_version=CASE_SCHEMA_VERSION,
        operation_kind="COMMIT_PROPOSAL",
        domain="medications",
        semantic_keys=["metformin", "lisinopril", "aspirin", "warfarin"],
        evidence_ids=["ev-rx-001", "ev-rx-002"],
        policy_version="glhs.v1",
        consent_version="medical_disclaimer:v3:42",
        policy_domain="medications",
        observed_entity_versions={
            "medications:metformin": 3,
            "medications:lisinopril": 2,
            "medications:aspirin": 1,
            "medications:warfarin": 5,
        },
        expected_dep_kinds=sorted(
            ["GOVERNANCE", "GOVERNANCE"]
            + ["ENTITY"] * 4
            + ["EVIDENCE"] * 2
        ),
        expected_dep_count_min=8,
        description="Multi-entity write with 4 medications (write-skew scenario)",
        created_at=datetime.now(UTC).isoformat(),
    )))

    # Cross-domain case: careguard needs medications + allergies
    cases.append(asdict(TestCase(
        case_id=f"case-cross-domain-careguard-{uuid4().hex[:8]}",
        schema_version=CASE_SCHEMA_VERSION,
        operation_kind="COMMIT_PROPOSAL",
        domain="medications",
        semantic_keys=["metformin", "penicillin_allergy_check"],
        evidence_ids=["ev-rx-001", "ev-allergy-001"],
        policy_version="glhs.v1",
        consent_version="medical_disclaimer:v3:42",
        policy_domain="medications",
        observed_entity_versions={
            "medications:metformin": 1,
            "medications:penicillin_allergy_check": 1,
        },
        expected_dep_kinds=sorted(
            ["GOVERNANCE", "GOVERNANCE"]
            + ["ENTITY"] * 2
            + ["EVIDENCE"] * 2
        ),
        expected_dep_count_min=6,
        description="Cross-domain careguard: medications + allergy evidence",
        created_at=datetime.now(UTC).isoformat(),
    )))

    return cases


def write_cases(output_dir: Path) -> Path:
    """Write generated cases to JSONL file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    cases = generate_cases()
    out_path = output_dir / "cases.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for case in cases:
            f.write(json.dumps(case, sort_keys=True) + "\n")

    manifest = {
        "schema_version": CASE_SCHEMA_VERSION,
        "case_count": len(cases),
        "generated_at": datetime.now(UTC).isoformat(),
        "cases_sha256": hashlib.sha256(
            out_path.read_bytes()
        ).hexdigest(),
    }
    manifest_path = output_dir / "cases-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return out_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate dependency completeness test cases")
    parser.add_argument("--output", type=Path, default=Path("evaluation/glhs_dependency_completeness/output"))
    args = parser.parse_args()
    path = write_cases(args.output)
    print(f"Generated {sum(1 for _ in path.open())} cases to {path}")
