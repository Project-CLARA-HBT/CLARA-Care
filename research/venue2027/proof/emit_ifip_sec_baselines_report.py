"""Emit the IFIP_SEC-baselines task proof report via agent_protocol.build_report."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import agent_protocol as ap  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[3]
BASE = "9b6be889db89c2228c6ea1ac599f0000d03c63a4"


def main() -> int:
    sha_after = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    report = ap.build_report(
        task_id="IFIP_SEC-baselines",
        status="PASS",
        source_sha_before=BASE,
        source_sha_after=sha_after,
        changed_paths=[
            "evaluation/venue2027/ifip_sec/__init__.py",
            "evaluation/venue2027/ifip_sec/baselines.py",
            "evaluation/venue2027/ifip_sec/test_baselines.py",
            "research/venue2027/proof/logs/IFIP_SEC-baselines.pytest.log",
            "research/venue2027/proof/logs/IFIP_SEC-baselines.ruff.log",
            "research/venue2027/proof/IFIP_SEC-baselines.json",
        ],
        commands=[
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/ifip_sec/test_baselines.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/IFIP_SEC-baselines.pytest.log",
            },
            {
                "argv": "uvx ruff@0.7.1 check evaluation/venue2027/ifip_sec/ --config ruff.toml",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/IFIP_SEC-baselines.ruff.log",
            },
        ],
        artifact_paths=[
            "evaluation/venue2027/ifip_sec/baselines.py",
            "evaluation/venue2027/ifip_sec/test_baselines.py",
            "evaluation/venue2027/ifip_sec/__init__.py",
            "research/venue2027/proof/logs/IFIP_SEC-baselines.pytest.log",
            "research/venue2027/proof/logs/IFIP_SEC-baselines.ruff.log",
        ],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="PASS",
        unresolved=[],
        notes=(
            "P03 baseline fidelity adapters: run_baseline(baseline_id, case, ctx) -> Outcome "
            "with real in-process implementations for B0 bearer-signed receipt (signature+expiry "
            "only; replay ACCEPTED is the asserted RQ1 weak-control signal), B1 stateless purpose "
            "binding (pointwise claim checks, nonce form-only, replay within expiry admitted - "
            "faithful stateless semantics), B2 real HMAC caveat-chain attenuation over hmac+"
            "hashlib (Macaroon-style: build_caveat_chain folds actor/purpose/task/expiry/nonce/"
            "parent into the running signature; tampering any caveat byte fails constant-time "
            "verification; pointwise satisfaction), B3 real consume-once nonce store (set.discard "
            "consume; replay REJECTED with NONCE_REPLAYED; paired B0-vs-B3 divergence test). "
            "parity_check round-trips the caveat construction (attenuate->serialize->verify) and "
            "proves tampered variants fail byte binding (PARITY_TAMPER_DETECTED path exercised "
            "via a broken-verifier simulation). External pinned upstreams (OpenFGA v1.22.1, "
            "Cedar v4.14.1, OPA v1.22.4 binaries) are NOT bundled: B2_OPENFGA/B3_CEDAR registry "
            "rows return NOT_RUN_EXTERNAL / BASELINE_UNAVAILABLE with retriable=True (execution "
            "contract rule 8 - never a toy under the same name; adapters are tasks X05/X03/X06). "
            "BASELINE_REGISTRY carries provenance for all six rows. 33 tests (16 positive incl. "
            "end-to-end admits + parity round-trip; 17 adversarial incl. NOT_RUN_EXTERNAL, B0/B1 "
            "replay admission, tampered caveat/signature/epoch, constant-deny stub refusal, "
            "unknown-id fail-closed, short-key refusal, no-oracle-import AST check) pass; ruff "
            "0.7.1 clean. source_sha_after = the task commit that contains the hashed artifacts "
            "(sibling convention; hashes bound at emit time)."
        ),
    )

    out = REPO / "research/venue2027/proof/IFIP_SEC-baselines.json"
    out.write_text(json.dumps(report, indent=4, sort_keys=True) + "\n", encoding="utf-8")

    result = ap.validate_report(
        report,
        repo=REPO,
        expected_task_id="IFIP_SEC-baselines",
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
