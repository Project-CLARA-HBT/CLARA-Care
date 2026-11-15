"""Emit research/venue2027/proof/POPETS-baseline_tests.json via agent_protocol.

Assembles the POPETS-baseline_tests task report with real command logs
(pytest, ruff check+format, emitter/validator) and hashes every declared
artifact, then validates it with agent_protocol.validate_report.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from research.venue2027._shared.tools.agent_protocol import (  # noqa: E402
    build_report,
    validate_report,
)

TASK_ID = "POPETS-baseline_tests"
SOURCE_SHA_BEFORE = "e373f6e46465917ad4fbd7d6656e77e51c4805db"

CHANGED_PATHS = [
    "tests/venue2027/__init__.py",
    "tests/venue2027/popets/__init__.py",
    "tests/venue2027/popets/test_baseline_fidelity.py",
    "research/venue2027/proof/POPETS-baseline_tests.json",
    "research/venue2027/proof/logs/POPETS-baseline_tests.pytest.log",
    "research/venue2027/proof/logs/POPETS-baseline_tests.ruff.log",
]

ARTIFACT_PATHS = [
    "tests/venue2027/popets/test_baseline_fidelity.py",
    "research/venue2027/proof/logs/POPETS-baseline_tests.pytest.log",
    "research/venue2027/proof/logs/POPETS-baseline_tests.ruff.log",
]


def main() -> int:
    source_sha_after = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()

    report = build_report(
        task_id=TASK_ID,
        status="PASS",
        source_sha_before=SOURCE_SHA_BEFORE,
        source_sha_after=source_sha_after,
        changed_paths=CHANGED_PATHS,
        commands=[
            {
                "argv": "python3 -m pytest -q tests/venue2027/popets/test_baseline_fidelity.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/POPETS-baseline_tests.pytest.log",
            },
            {
                "argv": "uvx ruff@0.7.1 check tests/venue2027/ && "
                "uvx ruff@0.7.1 format --check tests/venue2027/",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/POPETS-baseline_tests.ruff.log",
            },
            {
                "argv": "PYTHONPATH=. python3 "
                "research/venue2027/proof/emit_POPETS-baseline_tests_report.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/POPETS-baseline_tests.emit.log",
            },
        ],
        artifact_paths=ARTIFACT_PATHS,
        repo=ROOT,
        oracle_disagreement_count=None,
        baseline_parity="PASS",
        unresolved=[],
        notes=(
            "POPETS-baseline_tests (Phase P03, depends on PASS'd POPETS-baselines and "
            "POPETS-oracle): baseline conformance suite at the task's exact target path "
            "tests/venue2027/popets/test_baseline_fidelity.py importing the REAL module "
            "evaluation/venue2027/popets/baselines.py (no reimplementation). For EACH "
            "implemented baseline — coarse-cache-purge-on-revocation (B1), "
            "always-recompute-authorized-projection (B2), purpose-bound-cache-keying "
            "(design-reference ablation), purpose-aware-cache-x06 (POPETS-X06 comparator "
            "arm) — one UPSTREAM POSITIVE and one ADVERSARIAL NEGATIVE vector, plus a "
            "malformed-input fail-closed negative. Positives assert the documented "
            "guarantee end to end through run_baseline (post-revocation direct AND "
            "transitive dispatches REJECT with REVOKED_CONTEXT and zero exposed bytes, "
            "unaffected grants/purposes keep serving, epoch rotation/scoping, parity_check "
            "reproduces each registry-declared fixture exactly). Negatives assert the "
            "declared weaknesses explicitly as fidelity evidence: B1 over-invalidation "
            "(subject-wide purge destroys the still-authorized g-admin/clinical cached "
            "entry -> entries_destroyed_by_purges>=1 and forced recompute of an untouched "
            "scope); B2 zero-cache cost (cache_hit False on every record, "
            "invalidation_events==dispatch_count) and fail-closed LINEAGE_SOURCE_MISSING "
            "on unexpandable derived lineage; purpose-bound keying's NO-reverse-edges gap "
            "(transitive retry artifact not invalidated while authorization still denies "
            "-> transitive_gaps>=1); X06 fetch contract refusals (PURPOSE_MISMATCH on "
            "cross-purpose read returned before any lookup, CACHE_MISS on rotated keys, "
            "KEY_MALFORMED, EPOCH_STALE on a tampered entry whose stored consent_epoch "
            "contradicts its key) and purpose_isolation_violations==0 on the executable "
            "invariant over real cache state. Unavailable arms (ttl-only-cache B0, "
            "zanzibar-like-consistency-token-cache / zanzibar-openfga B3, "
            "muse-unlearning-comparator) asserted honestly NOT_RUN_EXTERNAL/"
            "BASELINE_UNAVAILABLE with parity None — no toy substitution. Observable "
            "behaviour recorded per baseline in OBSERVED_BEHAVIOUR. All errors asserted "
            "as stable uppercase reason codes, never bare exceptions counted as safe "
            "rejections. 13 passed in 0.25s; uvx ruff@0.7.1 check + format --check clean "
            "on tests/venue2027/. Regression: 165 passed across tests/venue2027/popets/, "
            "evaluation/venue2027/popets/test_baselines.py and research/venue2027/popets/"
            "tests/ (pre-existing suites green, unmodified). "
            "source_sha_before and source_sha_after record the base commit e373f6e4 per "
            "sibling convention (POPETS-baselines, POPETS-X05/X06); the single task "
            "commit SHA is created immediately after this report and reported in the "
            "handoff. baseline_parity=PASS: all four implemented POPETS parity vectors "
            "reproduce inside the fidelity positives. No claim of retroactive erasure: "
            "all vectors measure post-revocation FUTURE dispatches only."
        ),
    )

    out = ROOT / "research" / "venue2027" / "proof" / "POPETS-baseline_tests.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out}", flush=True)

    # Validate the emitted report and write the proof-of-validation log
    # OUTSIDE the report's own artifact set (a log describing the validation
    # of the report cannot hash itself).
    validation = validate_report(
        json.loads(out.read_text(encoding="utf-8")),
        repo=ROOT,
        expected_task_id=TASK_ID,
    )
    validator_log = (
        ROOT / "research" / "venue2027" / "proof" / "logs" / "POPETS-baseline_tests.validator.log"
    )
    validator_log.write_text(json.dumps(validation.to_dict(), indent=1) + "\n", encoding="utf-8")
    print(json.dumps(validation.to_dict(), indent=1), flush=True)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
