"""Audit evidence-program readiness from current files without inferring results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluation.evidence_program.freeze import FreezeError
from evaluation.evidence_program.release_gate import validate as validate_release_gate

WORKSTREAMS = {
    "comparator": (
        "evaluation/comparator_studies/bitemporal_state_arbitration/comparator_manifest.json",
        "mechanism comparator metadata present",
    ),
    "external_validation": (
        "evaluation/external_validation/README.md",
        "NOT RUN unless curator-owned sealed cohort artifact exists",
    ),
    "independent_adjudication": (
        "evaluation/clinical_adjudication/README.md",
        "NOT RUN unless qualified human labels and adjudication exist",
    ),
    "domain_portability": (
        "evaluation/domain_portability/policies.json",
        "PROTOCOL_ONLY until domain results are frozen",
    ),
    "downstream_utility": (
        "evaluation/clinical_utility/README.md",
        "NOT RUN unless two model-family output grid exists",
    ),
    "human_review": (
        "evaluation/human_review/README.md",
        "NOT RUN unless human review CSV and attestation exist",
    ),
    "governance_adversarial": (
        "evaluation/governance_adversarial/README.md",
        "NOT RUN unless real-boundary classified attack results exist",
    ),
    "audit_reconstruction": (
        "evaluation/audit_reconstruction/README.md",
        "IMPLEMENTED_NOT_HEADLINE; independent audit usability remains NOT RUN",
    ),
    "fullstack_benchmark": (
        "evaluation/fullstack_benchmark/README.md",
        "NOT RUN unless PostgreSQL-to-API metrics exist",
    ),
    "property_assurance": (
        "evaluation/property_assurance/test_glhs_gateway_properties.py",
        "IMPLEMENTED_NOT_HEADLINE; executable assurance is not external evidence",
    ),
}


def audit(repository_root: Path, artifact_root: Path) -> dict[str, object]:
    results: dict[str, dict[str, object]] = {}
    for name, (relative, interpretation) in WORKSTREAMS.items():
        path = repository_root / relative
        results[name] = {
            "status": "PRESENT_PROTOCOL" if path.is_file() else "MISSING",
            "path": relative,
            "interpretation": interpretation,
        }
    sealed_runs = []
    if artifact_root.is_dir():
        sealed_runs = sorted(
            str(path.relative_to(artifact_root))
            for path in artifact_root.glob("*/artifact-sha256.json")
            if path.is_file()
        )
    protocol_inventory_complete = bool(sealed_runs) and all(
        result["status"] == "PRESENT_PROTOCOL"
        for result in results.values()
    )
    release_attestation = artifact_root / "headline-release-attestation.json"
    release_gate_passed = False
    if release_attestation.is_file():
        try:
            validate_release_gate(release_attestation)
        except FreezeError:
            pass
        else:
            release_gate_passed = True
    return {
        "schema_version": "evidence-program-readiness-audit-v1",
        # File presence and artifact seals alone do not establish lawful access,
        # independence, clinical correctness, or predeclared evaluation.
        "headline_ready": release_gate_passed,
        "headline_claims_permitted": release_gate_passed,
        "protocol_inventory_complete": protocol_inventory_complete,
        "release_attestation": (
            str(release_attestation.relative_to(artifact_root))
            if release_attestation.is_file()
            else None
        ),
        "sealed_runs": sealed_runs,
        "workstreams": results,
        "limitations": [
            "This report inspects metadata and file presence only.",
            "It does not validate lawful access, human qualifications, independence, or clinical correctness.",
            "No absence is interpreted as a zero failure rate or successful result.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument("--artifact-root", type=Path, default=Path("artifacts/evidence-program"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.repository_root, args.artifact_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
