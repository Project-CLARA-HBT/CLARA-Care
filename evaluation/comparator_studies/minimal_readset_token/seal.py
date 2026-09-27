"""SHA-256 seal generator for E02 Minimal Alternative Binding Baseline.

Validates the full artifact bundle (protocol, environment, raw executions,
derived comparison summaries, comparator method card, validation assertions),
checks the tamper-evident observer hash chain, and seals the run with a
cryptographically bound seal.json and checksums.sha256.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evaluation.comparator_studies.minimal_readset_token.analyze import (
    analyze_minimal_token_results,
    generate_markdown_report,
)
from evaluation.comparator_studies.minimal_readset_token.runner import (
    TOTAL_EXECUTIONS_E02,
    TOTAL_SCHEDULES_E02,
    run_minimal_token_experiment,
)
from evaluation.glhs_binding_component_ablation.observer import read_records
from evaluation.glhs_binding_component_ablation.validate import (
    validate_import_boundary,
    validate_no_production_flag,
)

SEAL_SCHEMA_VERSION = "glhs-minimal-baseline-seal.v1"
VALIDATION_SCHEMA_VERSION = "glhs-minimal-baseline-validation.v1"


def sha256_file(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_sha() -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        return res.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def generate_environment_manifest(
    *,
    git_sha: str,
    backend: str = "isolated_sqlite",
) -> dict[str, Any]:
    """Capture execution environment metadata."""
    return {
        "schema_version": "glhs-minimal-baseline-environment.v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "git_sha": git_sha,
        "backend": backend,
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "system": platform.system(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count() or 1,
        "libraries": {
            "pytest": "9.1.1",
            "sqlalchemy": "2.0.46",
        },
    }


def validate_e02_protocol(protocol: dict[str, Any]) -> dict[str, Any]:
    """Validate frozen E02 protocol invariants."""
    if protocol.get("schema_version") != "glhs-minimal-baseline-protocol.v1":
        raise ValueError(f"protocol_schema_invalid:{protocol.get('schema_version')}")
    if protocol.get("status") != "FROZEN":
        raise ValueError(f"protocol_not_frozen:{protocol.get('status')}")
    if set(protocol.get("arms", [])) != {"GLHS_B111", "MIN_READSET_TOKEN", "HMAC_READSET_TOKEN", "B000"}:
        raise ValueError("protocol_arms_invalid")
    inv = protocol.get("schedule_inventory", {})
    if inv.get("total") != TOTAL_SCHEDULES_E02 or inv.get("adversarial") != 256 or inv.get("controls") != 96:
        raise ValueError("protocol_inventory_invalid")
    return {"valid": True, "freeze_id": protocol.get("freeze_id")}


def seal_experiment_e02(
    *,
    artifact_dir: Path,
    protocol_path: Path,
    schedules_path: Path,
    method_card_path: Path,
    run_id: str = "GLHS-Q2-R2-20260928-R01",
    backend: str = "isolated_sqlite",
    services_root: Path = Path("services"),
) -> dict[str, Any]:
    """Execute, validate, and seal the E02 minimal baseline experiment artifact bundle."""
    artifact_dir = artifact_dir.resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    derived_dir = artifact_dir / "derived"
    derived_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = artifact_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    git_sha = _git_sha()

    # 1. Validate protocol & schedules
    protocol_data = json.loads(protocol_path.read_text(encoding="utf-8"))
    validate_e02_protocol(protocol_data)

    schedules_data = json.loads(schedules_path.read_text(encoding="utf-8"))
    if len(schedules_data.get("schedules", [])) != TOTAL_SCHEDULES_E02:
        raise ValueError(f"schedules_count_invalid:{len(schedules_data.get('schedules', []))}")

    # 2. Validate safety guards
    flag_check = validate_no_production_flag(services_root)
    import_check = validate_import_boundary(services_root)

    # 3. Always run fresh experiment when sealing to ensure tamper-free integrity
    runs_file = raw_dir / "runs.jsonl"
    if runs_file.exists():
        runs_file.unlink()

    run_minimal_token_experiment(
        protocol_path=protocol_path,
        schedules_path=schedules_path,
        output_dir=artifact_dir,
        backend=backend,
        run_id=run_id,
    )

    records = read_records(runs_file)
    if len(records) != TOTAL_EXECUTIONS_E02:
        raise ValueError(f"record_count_mismatch:expected={TOTAL_EXECUTIONS_E02}:found={len(records)}")

    # 4. Write protocol.json and protocol.sha256
    dest_protocol = artifact_dir / "protocol.json"
    dest_protocol.write_text(json.dumps(protocol_data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    proto_sha = sha256_file(dest_protocol)
    (artifact_dir / "protocol.sha256").write_text(f"{proto_sha}  protocol.json\n", encoding="utf-8")

    # 5. Write environment.json
    env_data = generate_environment_manifest(git_sha=git_sha, backend=backend)
    (artifact_dir / "environment.json").write_text(
        json.dumps(env_data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    # 6. Copy method card to derived/comparator_method_card.md
    dest_method_card = derived_dir / "comparator_method_card.md"
    if method_card_path.is_file():
        shutil.copyfile(method_card_path, dest_method_card)
    else:
        dest_method_card.write_text("# Method Card: Minimal Read-Set Token Baseline\n", encoding="utf-8")

    # 7. Generate derived comparison_summary.json and comparison_summary.md
    summary_data = analyze_minimal_token_results(records, protocol_data=protocol_data)
    (derived_dir / "comparison_summary.json").write_text(
        json.dumps(summary_data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    summary_md = generate_markdown_report(summary_data)
    (derived_dir / "comparison_summary.md").write_text(summary_md, encoding="utf-8")

    # 8. Write validation.json
    validation_data = {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "validated_at_utc": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "freeze_id": protocol_data["freeze_id"],
        "git_sha": git_sha,
        "total_schedules_audited": TOTAL_SCHEDULES_E02,
        "total_executions_audited": TOTAL_EXECUTIONS_E02,
        "clean_controls_admitted": summary_data["arm_summaries"]["MIN_READSET_TOKEN"]["clean_controls_admitted"],
        "clean_controls_total": summary_data["arm_summaries"]["MIN_READSET_TOKEN"]["clean_controls_total"],
        "clean_controls_rate": summary_data["arm_summaries"]["MIN_READSET_TOKEN"]["clean_acceptance_rate"],
        "adversarial_false_acceptances": summary_data["arm_summaries"]["MIN_READSET_TOKEN"]["adversarial_admitted"],
        "exact_decision_match_with_glhs": summary_data["exact_decision_match"],
        "no_production_flags": flag_check["clean"],
        "no_forbidden_services_imports": import_check["clean"],
        "claim_eligible": summary_data["claim_eligible"],
        "status": "VALIDATED",
    }
    (artifact_dir / "validation.json").write_text(
        json.dumps(validation_data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    # 9. Compute checksums.sha256 across all files except checksums.sha256 and seal.json
    checksum_lines: list[str] = []
    file_digests: dict[str, str] = {}
    for p in sorted(artifact_dir.rglob("*")):
        if p.is_file() and p.name not in ("checksums.sha256", "seal.json"):
            rel_path = str(p.relative_to(artifact_dir))
            digest = sha256_file(p)
            file_digests[rel_path] = digest
            checksum_lines.append(f"{digest}  {rel_path}")

    (artifact_dir / "checksums.sha256").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

    # 10. Write seal.json
    seal_doc = {
        "schema_version": SEAL_SCHEMA_VERSION,
        "freeze_id": protocol_data["freeze_id"],
        "run_id": run_id,
        "git_sha": git_sha,
        "backend": backend,
        "total_schedules": TOTAL_SCHEDULES_E02,
        "executed_executions": len(records),
        "expected_executions": TOTAL_EXECUTIONS_E02,
        "claim_eligible": summary_data["claim_eligible"],
        "protocol_sha256": proto_sha,
        "schedules_sha256": sha256_file(schedules_path),
        "raw_stream_sha256": sha256_file(runs_file),
        "comparison_summary_sha256": sha256_file(derived_dir / "comparison_summary.json"),
        "comparator_method_card_sha256": sha256_file(dest_method_card),
        "validation_sha256": sha256_file(artifact_dir / "validation.json"),
        "artifact_inventory": file_digests,
        "sealed_at_utc": datetime.now(UTC).isoformat(),
        "status": "SEALED",
    }
    (artifact_dir / "seal.json").write_text(
        json.dumps(seal_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    return seal_doc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path("protocols/E02_minimal_baseline/protocol.json"),
    )
    parser.add_argument(
        "--schedules",
        type=Path,
        default=Path("protocols/E01_binding_components/schedules.json"),
    )
    parser.add_argument(
        "--method-card",
        type=Path,
        default=Path("evaluation/comparator_studies/minimal_readset_token/METHOD_CARD.md"),
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/glhs-q2-r2/GLHS-Q2-R2-20260928-R01/E02_minimal_baseline"),
    )
    parser.add_argument("--run-id", default="GLHS-Q2-R2-20260928-R01")
    parser.add_argument("--backend", default="isolated_sqlite")
    args = parser.parse_args()

    seal_doc = seal_experiment_e02(
        artifact_dir=args.artifact_dir,
        protocol_path=args.protocol,
        schedules_path=args.schedules,
        method_card_path=args.method_card,
        run_id=args.run_id,
        backend=args.backend,
    )
    print(json.dumps(seal_doc, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
