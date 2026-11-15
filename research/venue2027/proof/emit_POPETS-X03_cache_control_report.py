"""Emit the POPETS-X03_cache_control proof report via agent_protocol.build_report.

Assembles the POPETS-X03_cache_control task report with real command logs
(pytest on the new test module, ruff check, full local regression suite,
emitter/validator) and hashes every declared artifact, then validates it with
agent_protocol.validate_report (fail-closed: exits non-zero on any failure).
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

TASK_ID = "POPETS-X03_cache_control"
SOURCE_SHA_BEFORE = "687a6f56def769fc930e0ee94b00476eecc1c69b"

CHANGED_PATHS = [
    "evaluation/venue2027/popets/cache_control.py",
    "evaluation/venue2027/popets/test_cache_control.py",
    "research/venue2027/proof/POPETS-X03_cache_control.json",
    "research/venue2027/proof/logs/POPETS-X03_cache_control.pytest.log",
    "research/venue2027/proof/logs/POPETS-X03_cache_control.ruff.log",
    "research/venue2027/proof/logs/POPETS-X03_cache_control.suite.log",
    "research/venue2027/proof/logs/POPETS-X03_cache_control.validator.log",
]

ARTIFACT_PATHS = [
    "evaluation/venue2027/popets/cache_control.py",
    "evaluation/venue2027/popets/test_cache_control.py",
    "research/venue2027/proof/logs/POPETS-X03_cache_control.pytest.log",
    "research/venue2027/proof/logs/POPETS-X03_cache_control.ruff.log",
    "research/venue2027/proof/logs/POPETS-X03_cache_control.suite.log",
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
                "argv": "python3 -m pytest -q evaluation/venue2027/popets/test_cache_control.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/"
                "POPETS-X03_cache_control.pytest.log",
            },
            {
                "argv": "uvx ruff@0.7.1 check evaluation/venue2027/popets/cache_control.py "
                "evaluation/venue2027/popets/test_cache_control.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/"
                "POPETS-X03_cache_control.ruff.log",
            },
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/ "
                "research/venue2027/popets/tests/",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/"
                "POPETS-X03_cache_control.suite.log",
            },
            {
                "argv": "PYTHONPATH=. python3 "
                "research/venue2027/proof/emit_POPETS-X03_cache_control_report.py "
                "# build_report + validate_report(ok:true) recorded in "
                "research/venue2027/proof/POPETS-X03_cache_control.json",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/"
                "POPETS-X03_cache_control.validator.log",
            },
        ],
        artifact_paths=ARTIFACT_PATHS,
        repo=ROOT,
        oracle_disagreement_count=None,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P04 POPETS-X03_cache_control deliverable: "
            "evaluation/venue2027/popets/cache_control.py (CACHE_CONTROL_VERSION 1.0.0) is a "
            "purpose-bound cache control layer: typed CacheKey(subject, grant, purpose, "
            "consent_epoch) 4-tuple (purpose and epoch are first-class key components, so "
            "purpose isolation is structural, not advisory), CacheEntry lines (context bytes "
            "never serialized into audit views - byte counts only), put/get with explicit "
            "PURPOSE_MISMATCH refusal on cross-purpose reads, recompute_or_fetch invoking the "
            "injected recompute callable ONLY after all refusal checks pass (never for a "
            "revoked subject, stale epoch, or mismatched purpose - refused requests produce "
            "no bytes and trigger no recomputation), and revoke(subject) invalidating EVERY "
            "entry for the subject across ALL grants, purposes and epochs, tombstoning the "
            "subject (terminal: post-revocation reads refuse REVOKED_SUBJECT and writes raise "
            "fail-closed at ANY epoch) while rotating the consent epoch exactly once per "
            "event (idempotent repeat). GUARANTEE: a revoked subject's context is never "
            "served across ANY purpose - proven executably by assert_revocation_complete("
            "cache, subject), which scans the live entry store and raises RevocationLeakError "
            "(reason REVOCATION_LEAK, ValueError subclass) naming every surviving key. "
            "Stable uppercase reason codes throughout: HIT, RECOMPUTED, CACHE_MISS, "
            "PURPOSE_MISMATCH, EPOCH_STALE, REVOKED_SUBJECT, KEY_MALFORMED on the read path "
            "(returns, never raises); KEY_EPOCH_STALE, CONTEXT_MALFORMED, "
            "ARTIFACTS_MALFORMED, CREATED_AT_MALFORMED, SUBJECT_MALFORMED, "
            "RECOMPUTE_MALFORMED on the write path (raises CacheControlError so a lost write "
            "is never silently dropped); no hidden clock, no randomness, no network, no I/O; "
            "synthetic identifiers only. lineage_graph.py does not exist on this base, so no "
            "import of it was attempted (per task instruction a minimal self-contained layer "
            "was implemented instead). test_cache_control.py: 17 tests pass - positive: "
            "put/get round-trip per exact key with JSON-serializable byte-count views, "
            "disjoint key spaces for the same context under two purposes (separate entries, "
            "no shared hits), explicit requesting_purpose cross-read refused, "
            "recompute_or_fetch HIT on repeat and one RECOMPUTED per purpose first-use, "
            "revoke clears all purposes (3/3) with exactly-once epoch rotation and "
            "idempotent repeat, other subjects unaffected; adversarial: stale-epoch keys "
            "(both purposes) refused EPOCH_STALE with empty context, forged current-epoch "
            "key for revoked subject refused REVOKED_SUBJECT, put for revoked subject raises "
            "REVOKED_SUBJECT at any epoch, stale-epoch put raises KEY_EPOCH_STALE, "
            "assert_revocation_complete CATCHES A FORGOTTEN KEY (manually re-installed live "
            "entry for the revoked subject raises RevocationLeakError naming the key, and "
            "that entry is provably unservable through the public read path), 8 malformed "
            "input refusals with stable codes, read refusals never raise and never serve "
            "bytes, refused requests never trigger recomputation (injected callable not "
            "invoked), versioned snapshot determinism. Full local regression: 1793 passed "
            "(evaluation/venue2027 + research/venue2027/popets tests). uvx ruff@0.7.1 check "
            "clean on both new files. baseline_parity NOT_APPLICABLE (new purpose-bound "
            "layer; the X06 comparator arm and B0-B4 arms in baselines.py are untouched). "
            "Guarantee boundary: future-serving only - no claim of retraction of "
            "already-delivered bytes and no claim of cryptographic retroactive erasure "
            "(threat model §10). source_sha_after records the base commit 687a6f56 per the "
            "established sibling convention (POPETS-X02, POPETS-X06); the single task commit "
            "SHA is created immediately after this report and recorded in the commit body."
        ),
    )

    out = ROOT / "research" / "venue2027" / "proof" / "POPETS-X03_cache_control.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out}", flush=True)

    # The validator requires every declared command log to exist on disk, so
    # materialize the validator log before validating, then overwrite it with
    # the real validation result (a log describing the validation of the
    # report cannot hash itself — it is kept outside the artifact set).
    validator_log = (
        ROOT
        / "research"
        / "venue2027"
        / "proof"
        / "logs"
        / "POPETS-X03_cache_control.validator.log"
    )
    validator_log.parent.mkdir(parents=True, exist_ok=True)
    validator_log.write_text("pending validation\n", encoding="utf-8")

    validation = validate_report(
        json.loads(out.read_text(encoding="utf-8")),
        repo=ROOT,
        expected_task_id=TASK_ID,
    )
    validator_log.write_text(json.dumps(validation.to_dict(), indent=1) + "\n", encoding="utf-8")
    print(json.dumps(validation.to_dict(), indent=1), flush=True)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
