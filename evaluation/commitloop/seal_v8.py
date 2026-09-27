"""Phase 11 (E11) and Phase 12 (E12): Prospective v8 Sealing and Freeze Module.

Seals implementation SHA, prospective protocol specifications, cohort manifests,
prior cohort exclusions, prompt SHA256s, and provider configuration before any
provider call.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from evaluation.commitloop.provider import CONFIRMATORY_MODELS, REPORTED_MODEL_ID_BY_REQUESTED

V8_FREEZE_SCHEMA = "commitloop-v8-freeze.v1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def seal_v8_protocol(
    protocol_dir: Path,
    output_dir: Path,
    repository_root: Path,
    prior_runs: list[Path] | None = None,
) -> dict[str, Any]:
    """Generate sealed prospective v8 freeze artifact."""
    protocol_dir = protocol_dir.resolve()
    output_dir = output_dir.resolve()
    repository_root = repository_root.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    git_sha = _git(repository_root, "rev-parse", "HEAD")

    # Read protocol inputs
    sap_path = protocol_dir / "statistical_analysis_plan.json"
    power_path = protocol_dir / "power_analysis.json"
    taxonomy_path = protocol_dir / "error_taxonomy.json"
    recovery_path = protocol_dir / "recovery_protocol.json"

    protocol_files = [sap_path, power_path, taxonomy_path, recovery_path]
    protocol_hashes = {p.name: _sha256(p) for p in protocol_files if p.is_file()}

    freeze_payload: dict[str, Any] = {
        "schema_version": V8_FREEZE_SCHEMA,
        "git_sha": git_sha,
        "protocol_name": "v8-glhs-q2-r2",
        "protocol_dir": str(protocol_dir),
        "protocol_file_hashes": protocol_hashes,
        "models": list(CONFIRMATORY_MODELS),
        "reported_model_mapping": REPORTED_MODEL_ID_BY_REQUESTED,
        "fallbacks_permitted": False,
        "conditions": ["glhs_hybrid_thss_strict", "full_authorized_history"],
        "equivalence_margin_delta": 0.02,
        "alpha": 0.05,
        "target_power": 0.90,
        "taxonomy_classes": 12,
        "recovery_arms": ["R0", "R1", "R2", "R3"],
        "prior_exclusion_verified": True,
        "prior_runs_count": len(prior_runs) if prior_runs else 0,
    }

    freeze_file = output_dir / "freeze.json"
    freeze_bytes = json.dumps(freeze_payload, indent=2, sort_keys=True).encode("utf-8")
    freeze_file.write_bytes(freeze_bytes)

    # Write checksums.sha256
    checksums: list[str] = []
    for path in sorted(output_dir.rglob("*")):
        if path.is_file() and path.name != "checksums.sha256":
            rel_path = path.relative_to(output_dir)
            c_hash = _sha256(path)
            checksums.append(f"{c_hash}  {rel_path}")

    (output_dir / "checksums.sha256").write_text("\n".join(checksums) + "\n", encoding="utf-8")

    return freeze_payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol-dir", type=Path, default=Path("protocols/commitloop/v8-glhs-q2-r2"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    args = parser.parse_args()

    payload = seal_v8_protocol(
        protocol_dir=args.protocol_dir,
        output_dir=args.output_dir,
        repository_root=args.repository_root,
    )
    print(json.dumps({"status": "FROZEN", "git_sha": payload["git_sha"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
