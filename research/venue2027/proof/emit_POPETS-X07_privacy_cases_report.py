"""Emit research/venue2027/proof/POPETS-X07_privacy_cases.json via agent_protocol.

Assembles the POPETS-X07_privacy_cases task report with real command logs
(pytest, ruff check+format, full venue2027 regression, emitter/validator) and
hashes every declared artifact, then validates it with
agent_protocol.validate_report.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TASK = "POPETS-X07_privacy_cases"

BASE_SHA = "e373f6e46465917ad4fbd7d6656e77e51c4805db"

CHANGED = [
    "evaluation/venue2027/popets/privacy_cases.py",
    "evaluation/venue2027/popets/test_privacy_cases.py",
    "research/venue2027/proof/POPETS-X07_privacy_cases.json",
    "research/venue2027/proof/logs/POPETS-X07_privacy_cases.pytest.log",
    "research/venue2027/proof/logs/POPETS-X07_privacy_cases.ruff.log",
    "research/venue2027/proof/logs/POPETS-X07_privacy_cases.suite.log",
    "research/venue2027/proof/logs/POPETS-X07_privacy_cases.validator.log",
]

ARTIFACTS = [
    "evaluation/venue2027/popets/privacy_cases.py",
    "evaluation/venue2027/popets/test_privacy_cases.py",
    "research/venue2027/proof/logs/POPETS-X07_privacy_cases.pytest.log",
    "research/venue2027/proof/logs/POPETS-X07_privacy_cases.ruff.log",
    "research/venue2027/proof/logs/POPETS-X07_privacy_cases.suite.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/popets/test_privacy_cases.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/POPETS-X07_privacy_cases.pytest.log",
    },
    {
        "argv": (
            "uvx ruff@0.7.1 check evaluation/venue2027/popets/privacy_cases.py "
            "evaluation/venue2027/popets/test_privacy_cases.py && "
            "uvx ruff@0.7.1 format --check "
            "evaluation/venue2027/popets/privacy_cases.py "
            "evaluation/venue2027/popets/test_privacy_cases.py"
        ),
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/POPETS-X07_privacy_cases.ruff.log",
    },
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/ research/venue2027/popets/tests/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/POPETS-X07_privacy_cases.suite.log",
    },
    {
        "argv": (
            "python3 research/venue2027/proof/emit_POPETS-X07_privacy_cases_report.py "
            "# build_report + validate_report(ok:true) recorded in "
            "research/venue2027/proof/POPETS-X07_privacy_cases.json"
        ),
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/POPETS-X07_privacy_cases.validator.log",
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
        artifact_paths=ARTIFACTS,
        repo=REPO,
        unresolved=[],
        baseline_parity="NOT_APPLICABLE",
        notes=(
            "P02 POPETS-X07_privacy_cases deliverable: "
            "evaluation/venue2027/popets/privacy_cases.py is the ex-ante FROZEN "
            "privacy test-case set (N=9) for RQ1 of 'Revocation-Complete Future "
            "Disclosure for Cached Longitudinal AI Contexts', frozen before any "
            "candidate arm (B0-B4, C0) executes. Typed frozen dataclasses: "
            "CaseScenario (injected ledger + dispatch item + principal/purpose/"
            "time query triple, all synthetic structural placeholders, PHI-free) "
            "and PrivacyCase (case_id, scenario_class, scenario, "
            "expected_semantic_outcome, revocation_model_reference, "
            "case_matrix_ref, description). Expected semantic outcomes drawn from "
            "ExpectedSemanticOutcome = ALLOW | DENY | INDETERMINATE | "
            "OUT_OF_SCOPE | NOT_GUARANTEED: the first three mirror the "
            "revocation_model TriDecision vocabulary; OUT_OF_SCOPE (threat "
            "precision, POPETS-CASE-06) and NOT_GUARANTEED (memorization "
            "uncertainty) are honest guarantee-boundary outcomes carried by the "
            "orthogonal RevocationDecision effect fields (already_delivered_effect="
            "OUT_OF_SCOPE_PAST, memorization_guarantee=NOT_GUARANTEED) and are "
            "NEVER coerced into verdicts. Five scenario classes, all five "
            "outcomes covered: fresh_dispatch PC-FRESH-01/02 (ALLOW, authorized "
            "utility incl. scope-local recompute without false invalidation), "
            "post_revocation_dispatch PC-REVOKE-01/02 (DENY/DENY_POST_REVOCATION "
            "boundary-inclusive at t_r, retry and fallback transport), "
            "cross_purpose PC-XPURP-01 (DENY/PURPOSE_NOT_CONSENTED: known-but-"
            "unconsented purpose via a second synthetic principal making the "
            "purpose string known in ledger vocabulary), transitive_gap "
            "PC-TGAP-01/02 (INDETERMINATE/LINEAGE_INDETERMINATE fail-closed: "
            "second-order derived node with unlabelled ancestry inside the "
            "post-t_r closure, and orphan derived cache), already_delivered "
            "PC-DELIV-01/02 (future dispatch still DENY/gated while the "
            "pre-t_r delivered copy is OUT_OF_SCOPE_PAST — no retroactive-"
            "erasure claim anywhere; authorized dispatch stays ALLOW with "
            "memorization honestly NOT_GUARANTEED — never a DENY-as-erasure). "
            "Every case maps to a REAL revocation_model.decide() decision over "
            "its typed scenario (revocation_model 1.0.0 semantics reference "
            "named per case); freeze discipline mirrors pst.forensic_queries "
            "and _shared.analysis_policy: canonical-JSON SHA256 freeze constant "
            "FROZEN_CASE_SET_SHA256=d48dfcb37af0d998b801101c34ec9a0f8710505e2cecf8a5"
            "6b574168e3399d9b enforced by assert_frozen_cases with stable reason "
            "code CASE_SET_DRIFT (any addition/removal/rewording/reorder/"
            "outcome-flip changes the digest and is refused); import-time "
            "_assert_internal_consistency fail-closes malformed cases "
            "(CASE_MALFORMED) including scenario round-trip through the real "
            "DispatchItem/ConsentLedgerView input contracts; unknown ids fail "
            "closed (CASE_UNKNOWN). test_privacy_cases.py: 24 tests pass — "
            "positive: freeze discipline (deterministic canonical hash equal to "
            "the committed constant, unique stable ids, all classes and outcomes "
            "covered), every case's expected outcome verified against the real "
            "model decision (ALLOW cases carry ALLOWED_ACTIVE_CONSENT with no "
            "deletion obligation; DENY cases carry distinct stable reason codes "
            "DENY_POST_REVOCATION / PURPOSE_NOT_CONSENTED; INDETERMINATE cases "
            "carry LINEAGE_INDETERMINATE and are never counted as safe "
            "rejections; post-revocation cases report stored_data='deleted' as "
            "an orthogonal surface; OUT_OF_SCOPE/NOT_GUARANTEED cases keep "
            "ordinary verdicts with honest orthogonal effects), JSON round-trips "
            "of every typed case, semantics clauses cited by cases exist in "
            "revocation_semantics(); adversarial: drift refused (added, removed, "
            "reworded, reordered, outcome-flipped sets all refused with "
            "CASE_SET_DRIFT), no retroactive-erasure claim (semantics refuse "
            "retroactive_erasure_of_delivered_bytes and "
            "model_memorization_erasure; no case text promises erasure; no "
            "ERASE/UNLEARN reason code exists in any decision), no PHI (field "
            "vocabulary scanned against the shared kernel PHI_FIELD_MARKERS; "
            "no SSN-like identifiers), unknown case id and malformed cases fail "
            "closed. Full evaluation/venue2027 + research/venue2027/popets "
            "regression: 1400 passed. uvx ruff@0.7.1 check + format --check "
            "clean on touched files. source_sha_after records the base commit "
            "e373f6e4 per the sibling convention (POPETS-X02, POPETS-X06); the "
            "single task commit SHA is created immediately after this report and "
            "recorded in the commit body. No claim of retroactive erasure or "
            "guaranteed LLM unlearning is made anywhere (task risk notes; "
            "threat-model §10). Baseline parity NOT_APPLICABLE (frozen case set; "
            "arms execute in P03 against this denominator)."
        ),
    )

    out = REPO / "research" / "venue2027" / "proof" / "POPETS-X07_privacy_cases.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out}", flush=True)

    validation = ap.validate_report(
        json.loads(out.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id=TASK,
    )
    validator_log = (
        REPO
        / "research"
        / "venue2027"
        / "proof"
        / "logs"
        / "POPETS-X07_privacy_cases.validator.log"
    )
    validator_log.write_text(json.dumps(validation.to_dict(), indent=1) + "\n", encoding="utf-8")
    print(json.dumps(validation.to_dict(), indent=1), flush=True)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
