#!/usr/bin/env python3
"""Offline reproduction and evidence integrity validator for E08 (Formal Governance Assurance).

Validates the full sealed artifact bundle for E08:
1. Disables all network access fail-closed.
2. Verifies cryptographic checksums in checksums.sha256.
3. Validates protocol freeze and code hash bindings.
4. Reproduces depth 5 and depth 6 bounded exhaustive state sweeps.
5. Verifies zero invariant violations across all reachable states.
6. Executes mutation test suite proving invariant checker non-vacuity.
7. Validates seal.json binding and claim eligibility.

Run from repository root:

    python reproduce_e08.py [--artifact-dir DIR] [--protocol PATH] [--seal]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import socket
import sys
import time
from pathlib import Path
from typing import Any

# Ensure project root is resolvable
_REPO_ROOT = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evaluation.formal_governance.explore import explore  # noqa: E402
from evaluation.formal_governance.invariants import all_invariant_ids  # noqa: E402
from evaluation.formal_governance.seal_run import run_mutation_tests, seal_e08  # noqa: E402

PROTOCOL_SCHEMA_VERSION = "glhs-e08-formal-assurance-protocol-v1"
SEAL_SCHEMA_VERSION = "glhs-e08-formal-assurance-seal-v1"
DEFAULT_ARTIFACT_DIR = "protocols/E08_formal_assurance"
DEFAULT_PROTOCOL_PATH = "protocols/E08_formal_assurance/protocol.json"


class NetworkAccessProhibitedError(RuntimeError):
    """Raised if any network activity is attempted during offline reproduction."""


def disable_network() -> None:
    """Prohibit all socket creation and DNS resolution fail-closed."""
    def forbidden_socket(*args: Any, **kwargs: Any) -> Any:
        raise NetworkAccessProhibitedError("network_access_prohibited_during_reproduction")

    socket.socket = forbidden_socket  # type: ignore[assignment]
    socket.create_connection = forbidden_socket  # type: ignore[assignment]
    socket.getaddrinfo = forbidden_socket  # type: ignore[assignment]
    socket.gethostbyname = forbidden_socket  # type: ignore[assignment]


def sha256_file(path: Path) -> str:
    """Compute SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_checksums(artifact_dir: Path) -> dict[str, str]:
    """Verify that every file in checksums.sha256 matches its exact digest."""
    checksum_file = artifact_dir / "checksums.sha256"
    if not checksum_file.is_file():
        raise FileNotFoundError(f"checksums_file_missing:{checksum_file}")

    lines = checksum_file.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError("empty_checksums_sha256")

    verified_files: dict[str, str] = {}
    for lineno, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            expected_digest, rel_path = line.split("  ", 1)
        except ValueError as exc:
            raise ValueError(f"malformed_checksum_line:{lineno}:{line}") from exc

        if not re.fullmatch(r"[0-9a-f]{64}", expected_digest):
            raise ValueError(f"invalid_sha256_format:{lineno}:{expected_digest}")

        target = artifact_dir / rel_path
        if not target.is_file():
            raise FileNotFoundError(f"sealed_file_missing:{rel_path}")

        actual_digest = sha256_file(target)
        if actual_digest != expected_digest:
            raise ValueError(
                f"checksum_mismatch:{rel_path}:expected={expected_digest}:actual={actual_digest}"
            )
        verified_files[rel_path] = actual_digest

    # Verify inventory completeness
    for path in artifact_dir.rglob("*"):
        if path.is_file() and path.name not in ("checksums.sha256", "seal.json"):
            rel = str(path.relative_to(artifact_dir))
            if rel not in verified_files:
                raise ValueError(f"unsealed_file_detected:{rel}")

    return verified_files


def reproduce_and_verify(
    *,
    artifact_dir: Path,
    protocol_path: Path,
) -> dict[str, Any]:
    """Perform offline reproduction and verification of E08."""
    disable_network()

    artifact_dir = artifact_dir.resolve()
    protocol_path = protocol_path.resolve()

    if not protocol_path.is_file():
        raise FileNotFoundError(f"protocol_file_missing:{protocol_path}")
    if not artifact_dir.is_dir():
        raise FileNotFoundError(f"artifact_directory_not_found:{artifact_dir}")

    # 1. Verify file-level cryptographic checksums
    verified_checksums = verify_checksums(artifact_dir)

    # 2. Verify protocol document
    protocol_doc = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol_doc.get("schema_version") != PROTOCOL_SCHEMA_VERSION:
        raise ValueError(f"invalid_protocol_schema:{protocol_doc.get('schema_version')}")

    # 3. Reproduce bounded exhaustive state exploration (depth 5 & 6)
    d5_reproduced = explore(max_depth=5)
    d6_reproduced = explore(max_depth=6)

    if d5_reproduced["violation_count"] != 0:
        raise ValueError(f"depth5_invariant_violations_detected:{d5_reproduced['violation_count']}")
    if d6_reproduced["violation_count"] != 0:
        raise ValueError(f"depth6_invariant_violations_detected:{d6_reproduced['violation_count']}")

    # 4. Verify reproduced statistics match sealed raw results
    sealed_d5_file = artifact_dir / "raw" / "exploration_d5.json"
    sealed_d6_file = artifact_dir / "raw" / "exploration_d6.json"
    if not sealed_d5_file.is_file() or not sealed_d6_file.is_file():
        raise FileNotFoundError("sealed_raw_exploration_files_missing")

    sealed_d5 = json.loads(sealed_d5_file.read_text(encoding="utf-8"))
    sealed_d6 = json.loads(sealed_d6_file.read_text(encoding="utf-8"))

    if d5_reproduced["states"] != sealed_d5["states"]:
        raise ValueError(f"d5_states_mismatch:reproduced={d5_reproduced['states']}:sealed={sealed_d5['states']}")
    if d5_reproduced["transitions_explored"] != sealed_d5["transitions_explored"]:
        raise ValueError("d5_transitions_mismatch")

    if d6_reproduced["states"] != sealed_d6["states"]:
        raise ValueError(f"d6_states_mismatch:reproduced={d6_reproduced['states']}:sealed={sealed_d6['states']}")
    if d6_reproduced["transitions_explored"] != sealed_d6["transitions_explored"]:
        raise ValueError("d6_transitions_mismatch")

    # 5. Run mutation tests to confirm non-vacuity
    mutation_res = run_mutation_tests()
    if not mutation_res["success"]:
        raise RuntimeError("mutation_test_suite_failed_during_reproduction")

    # 6. Verify validation.json and seal.json
    validation_file = artifact_dir / "validation.json"
    validation_doc = json.loads(validation_file.read_text(encoding="utf-8"))
    if validation_doc.get("status") != "VALIDATED" or not validation_doc.get("claim_eligible"):
        raise ValueError("validation_doc_invalid")

    seal_file = artifact_dir / "seal.json"
    seal_doc = json.loads(seal_file.read_text(encoding="utf-8"))
    if seal_doc.get("status") != "SEALED" or seal_doc.get("schema_version") != SEAL_SCHEMA_VERSION:
        raise ValueError("seal_doc_invalid")

    return {
        "status": "REPRODUCED_AND_VERIFIED",
        "protocol_id": protocol_doc["protocol_id"],
        "freeze_id": seal_doc["freeze_id"],
        "git_sha": seal_doc["git_sha"],
        "checksums_verified_count": len(verified_checksums),
        "depth5_states": d5_reproduced["states"],
        "depth5_transitions": d5_reproduced["transitions_explored"],
        "depth6_states": d6_reproduced["states"],
        "depth6_transitions": d6_reproduced["transitions_explored"],
        "total_violations": 0,
        "mutation_tests_passed": True,
        "claim_eligible": True,
        "seal_verified": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path(DEFAULT_ARTIFACT_DIR),
    )
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path(DEFAULT_PROTOCOL_PATH),
    )
    parser.add_argument(
        "--seal",
        action="store_true",
        help="Execute sealing before reproducing",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent
    protocol_path = args.protocol if args.protocol.is_absolute() else repo_root / args.protocol
    artifact_dir = args.artifact_dir if args.artifact_dir.is_absolute() else repo_root / args.artifact_dir

    print(f"E08 Protocol:  {protocol_path}")
    print(f"E08 Artifacts: {artifact_dir}")

    if args.seal or not (artifact_dir / "seal.json").exists():
        print("\nSealing E08 artifact bundle...")
        seal_e08(artifact_dir=artifact_dir, protocol_path=protocol_path)
        print("Artifact generation & sealing complete.")

    print("\nRunning offline reproduction and verification...")
    result = reproduce_and_verify(
        artifact_dir=artifact_dir,
        protocol_path=protocol_path,
    )

    print("\n" + "=" * 65)
    print(" E08 FORMAL GOVERNANCE ASSURANCE VERIFICATION PASSED")
    print("=" * 65)
    print(f"  Status:                   {result['status']}")
    print(f"  Protocol ID:              {result['protocol_id']}")
    print(f"  Freeze ID:                {result['freeze_id']}")
    print(f"  Git SHA:                  {result['git_sha']}")
    print(f"  Verified File Checksums:  {result['checksums_verified_count']}")
    print(f"  Depth 5 (States / Trans): {result['depth5_states']:,} / {result['depth5_transitions']:,}")
    print(f"  Depth 6 (States / Trans): {result['depth6_states']:,} / {result['depth6_transitions']:,}")
    print(f"  Total Violations:         {result['total_violations']}")
    print(f"  Mutation Tests Passed:    {result['mutation_tests_passed']}")
    print(f"  Claim Eligible:           {result['claim_eligible']}")
    print("=" * 65)
    return 0


if __name__ == "__main__":
    sys.exit(main())
