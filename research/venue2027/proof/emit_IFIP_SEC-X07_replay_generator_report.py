"""Emit the IFIP_SEC-X07_replay_generator proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the IFIP_SEC-X07_replay_generator task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TASK = "IFIP_SEC-X07_replay_generator"

BASE_SHA = "11a9219ce0a1d3d523400350abb959c0f56699f2"

CHANGED = [
    "evaluation/venue2027/ifip_sec/replay_generator.py",
    "evaluation/venue2027/ifip_sec/test_replay_generator.py",
    "research/venue2027/proof/emit_IFIP_SEC-X07_replay_generator_report.py",
    "research/venue2027/proof/IFIP_SEC-X07_replay_generator.json",
    "research/venue2027/proof/logs/IFIP_SEC-X07_replay_generator.pytest.log",
    "research/venue2027/proof/logs/IFIP_SEC-X07_replay_generator.ruff.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/ifip_sec/test_replay_generator.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/IFIP_SEC-X07_replay_generator.pytest.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check evaluation/venue2027/ifip_sec/ --config ruff.toml",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/IFIP_SEC-X07_replay_generator.ruff.log",
    },
]


def main() -> int:
    report = ap.build_report(
        task_id=TASK,
        status="PASS",
        source_sha_before=BASE_SHA,
        source_sha_after=BASE_SHA,
        changed_paths=CHANGED,
        commands=COMMANDS,
        artifact_paths=CHANGED[:2],
        repo=REPO,
        unresolved=[],
        baseline_parity="NOT_APPLICABLE",
        notes=(
            "IFIP_SEC-X07_replay_generator (Phase P02, RQ1): implemented the deterministic "
            "replay-attack sequence builder generate_replays(seed, base_cases=None, n=8) -> "
            "list[ReplayAttack] in evaluation/venue2027/ifip_sec/replay_generator.py "
            "(REPLAY_GENERATOR_VERSION 1.0.0, schema clara.venue2027.ifip_sec.replay_attack.v1), "
            "realizing the task contract as the X07-specific counterpart to the dataset "
            "generator's Schedule contract (source_reference_map target "
            "replay_schedules.py 'generate(seed,families)->list[Schedule]'; this worktree "
            "delivers the replay-attack variant at the collision-checked path replay_generator.py "
            "per the deliverable spec - no pre-existing symbol was overwritten). Four attack "
            "families, each mutating exactly its declared primary field of a legitimate "
            "fresh_accept base request and encoding the dataset ground-truth signal convention: "
            "cross_purpose (purpose shifted away from granted_purpose; violates "
            "purpose_domain_separation, CASE-02), delegation_replay (nonce_state -> "
            "consumed_by_delegate; violates consume_once_nonce), lineage_splice (consent_epoch "
            "re-pointed to an epoch that no longer derives from parent_consent_epoch; violates "
            "delegation_ancestry_binding) and nonce_replay (nonce_state -> consumed, verbatim "
            "same-nonce duplicate presentation of an already-consumed receipt; violates "
            "consume_once_nonce). Every ReplayAttack records attack_id (seed-bound digest), "
            "family, mutated_field, original_request verbatim, mutated_request, "
            "violated_invariant (frozen VIOLATED_INVARIANTS table), expected_oracle_verdict "
            "(always REJECT) and the frozen independent-oracle rule-table binding "
            "ORACLE_FAMILY_FOR_ATTACK (cross_purpose -> cross_purpose_replay, lineage_splice -> "
            "lineage_splice, delegation_replay/nonce_replay -> delegation_replay; no dedicated "
            "nonce_replay row exists so it shares the consume-once row - an explicit mapping, "
            "not an invented rule). Round-robin family distribution guarantees all four families "
            "appear for n >= 4; ordering and content are pure functions of (seed, base_cases, n) "
            "- same inputs always yield identical output. Paired legitimate operation for every "
            "attacker variant via legitimate_control(attack) -> fresh_accept-shape request "
            "sharing actor/tenant/operation with the attack (expected ADMIT), per the task's "
            "'paired legitimate operation for each attacker variant' requirement. Fail closed "
            "with stable reason codes via ReplayGeneratorError: INVALID_SEED, INVALID_N, "
            "INVALID_BASE_CASE (non-mapping, missing required fields, bad delegation_depth/"
            "replay_flag/nonce_state types, malformed consent-<int> epochs), UNKNOWN_FAMILY "
            "(smuggled family in base case or unknown mutator family) and UNMUTATED_REQUEST (a "
            "primary-field no-op - e.g. an already-consumed receipt offered to nonce_replay - is "
            "refused as not-an-attack, never silently returned), plus PHI_FIELD_PRESENT on "
            "PHI-like field names; all requests validated with the same synthetic-identifier "
            "discipline as the venue dataset. Test driver evaluation/venue2027/ifip_sec/"
            "test_replay_generator.py (26 tests) imports only the generator plus the independent "
            "oracle for verdict cross-checking (no candidate, no baseline adapter - oracle "
            "independence preserved): positive controls prove determinism (identical inputs, "
            "JSON round-trip), every family generated with named violated invariant, exactly-one-"
            "field mutations, unique deterministic attack_ids, oracle adjudication of every "
            "attack to REJECT and every paired control to ADMIT against the frozen "
            "IFIP_REFERENCE_RULES, JSON-serializability and PHI-free payloads; adversarial "
            "controls prove unmutated requests refused as not-an-attack (UNMUTATED_REQUEST, incl. "
            "defense-in-depth _verify_mutation gate), unknown families refused (UNKNOWN_FAMILY), "
            "malformed base cases refused (INVALID_BASE_CASE), invalid seed/n refused "
            "(INVALID_SEED/INVALID_N) and no attack ever equals its original. 26 passed; 101 "
            "passed on the full evaluation/venue2027/ifip_sec/ suite (no regression); uvx "
            "ruff@0.7.1 check clean on evaluation/venue2027/ifip_sec/. No production path "
            "touched; no network, DB, live provider, hidden clock or randomness beyond the seed; "
            "no real PostgreSQL condition claimed (pure-function generator). "
            "baseline_parity=NOT_APPLICABLE (attack-fixture generator feeding RQ1/B0-B4 "
            "measurement; parity is exercised by X05/X06 comparators downstream). "
            "source_sha_after records the base commit 11a9219c per the established sibling "
            "convention (IFIP_SEC-X01/X06); the single task commit SHA is created immediately "
            "after this report and recorded in the commit body. Downstream consumers: "
            "IFIP_SEC-oracle pilots, baseline_tests (B0-B4 adjudication of these attacks), "
            "unit/pilot/confirm."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "IFIP_SEC-X07_replay_generator.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
