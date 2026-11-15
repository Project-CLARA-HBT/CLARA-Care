"""Emit the IFIP_SEC-baseline_tests task proof report via agent_protocol.build_report."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import agent_protocol as ap  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[3]
BASE = "e373f6e46465917ad4fbd7d6656e77e51c4805db"


def main() -> int:
    sha_after = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    report = ap.build_report(
        task_id="IFIP_SEC-baseline_tests",
        status="PASS",
        source_sha_before=BASE,
        source_sha_after=sha_after,
        changed_paths=[
            "tests/venue2027/__init__.py",
            "tests/venue2027/ifip_sec/__init__.py",
            "tests/venue2027/ifip_sec/test_baseline_fidelity.py",
            "research/venue2027/proof/logs/IFIP_SEC-baseline_tests.pytest.log",
            "research/venue2027/proof/logs/IFIP_SEC-baseline_tests.ruff.log",
            "research/venue2027/proof/IFIP_SEC-baseline_tests.json",
        ],
        commands=[
            {
                "argv": "python3 -m pytest -q tests/venue2027/ifip_sec/test_baseline_fidelity.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/IFIP_SEC-baseline_tests.pytest.log",
            },
            {
                "argv": "uvx ruff@0.7.1 check tests/venue2027/ --config ruff.toml",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/IFIP_SEC-baseline_tests.ruff.log",
            },
        ],
        artifact_paths=[
            "tests/venue2027/__init__.py",
            "tests/venue2027/ifip_sec/__init__.py",
            "tests/venue2027/ifip_sec/test_baseline_fidelity.py",
            "research/venue2027/proof/logs/IFIP_SEC-baseline_tests.pytest.log",
            "research/venue2027/proof/logs/IFIP_SEC-baseline_tests.ruff.log",
        ],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="PASS",
        unresolved=[],
        notes=(
            "P03 baseline conformance suite (task IFIP_SEC-baseline_tests, depends "
            "IFIP_SEC-baselines + IFIP_SEC-oracle, both PASS in-repo): "
            "tests/venue2027/ifip_sec/test_baseline_fidelity.py imports the REAL "
            "evaluation.venue2027.ifip_sec.baselines module (BASELINES_VERSION 1.1.0, "
            "asserted) and the real consistency_token_adapter reason codes, and drives "
            "every implemented arm through the public dispatcher run_baseline(id, case, "
            "ctx) -> Outcome with injected BaselineContext (fixed HMAC key, frozen clock, "
            "explicit nonce store / ZanzibarStore; no network, no DB, no hidden clock or "
            "randomness). Per implemented arm, one UPSTREAM POSITIVE vector asserting the "
            "documented guarantee and one ADVERSARIAL NEGATIVE vector on the blueprint "
            "replay attack, plus the asserted honest weaknesses where the published "
            "semantics admit the replay: B0 bearer-signed-receipt (positive: valid signed "
            "unexpired receipt ADMITted BEARER_SIGNATURE_VALID; negative: expired receipt "
            "REJECTed TOKEN_EXPIRED; honest weakness: identical receipt replays ADMITted - "
            "RQ1 lower bound). B1 stateless purpose binding (positive: matching "
            "purpose/tenant/actor/epoch claims ADMITted PURPOSE_BOUND_STATELESS; negative: "
            "purpose mismatch REJECTed PURPOSE_MISMATCH + forged claim mutation caught by "
            "HMAC TOKEN_SIGNATURE_INVALID; honest weakness: nonce checked for form only, "
            "never consumed - replay within expiry ADMITted while an injected store stays "
            "untouched). B2 macaroon-style HMAC caveat chain over CAVEAT_KEYS (positive: "
            "real attenuation chain verifies end to end, ADMIT CAVEAT_CHAIN_VALID; "
            "negative: single flipped purpose caveat byte vs the honest signature REJECTed "
            "CAVEAT_VERIFICATION_FAILED; honest weakness: pointwise satisfaction consumes "
            "no nonce, replay within expiry ADMITted). B3 nonce-store replay rejection "
            "(positive: first presentation consumes the nonce and ADMITs "
            "NONCE_CONSUMED_ONCE with the injected set really mutated; negative: second "
            "presentation REJECTed NONCE_REPLAYED, paired B0-vs-B3 divergence asserted on "
            "the identical replay). B2_INPROCESS_ZANZIBAR (X06 additive row, published "
            "Zanzibar Sec. 2.3-2.4 snapshot semantics via check_with_revision contract): "
            "positive: FRESH zookie sees the just-granted relation, ADMIT "
            "RELATION_PRESENT; negative: replayed pre-revocation request under a FRESH "
            "token REJECTed RELATION_REVOKED; honest weakness asserted: the identical "
            "replay with the PRE-REVOCATION zookie is ADMITted inside the bounded-"
            "staleness window (never silently converted into a rejection). Cross-arm "
            "conformance: real-module version pin 1.1.0, external pinned rows B2_OPENFGA / "
            "B3_CEDAR stay runnable_in_process=False with pinned provenance and return "
            "NOT_RUN_EXTERNAL / BASELINE_UNAVAILABLE (execution contract rule 8 - never a "
            "toy under the same name), arm faults are first-class REJECT Outcomes with "
            "stable reason codes for every arm (never unhandled exceptions miscounted as "
            "safe rejections) and B3 wiring without a store raises BaselineError "
            "CONTEXT_STORE_MISSING. 18 tests (5 positives x arm + 5 replay/expiry/tamper "
            "negatives + 3 asserted honest-weakness vectors + 4 conformance/fail-closed "
            "hygiene + 1 registry external-row check) pass; uvx ruff@0.7.1 clean on "
            "tests/venue2027/. Fidelity honest-weakness vectors intentionally block any "
            "future 'repair' of B0/B1/B2/Zanzibar-stale into fake safe rejections: that "
            "would falsify the baselines the study compares against. No real PostgreSQL / "
            "external OpenFGA/Cedar/OPA claims: in-process reference only (PG consume-once "
            "race belongs to IFIP_SEC-X03). source_sha_after records the base commit "
            "e373f6e4 per the established sibling convention (IFIP_SEC-baselines, X06); "
            "the single task commit SHA is created immediately after this report and "
            "recorded in the commit body."
        ),
    )

    out = REPO / "research/venue2027/proof/IFIP_SEC-baseline_tests.json"
    out.write_text(json.dumps(report, indent=4, sort_keys=True) + "\n", encoding="utf-8")

    result = ap.validate_report(
        report,
        repo=REPO,
        expected_task_id="IFIP_SEC-baseline_tests",
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
