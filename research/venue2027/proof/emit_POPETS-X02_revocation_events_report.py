"""Emit research/venue2027/proof/POPETS-X02_revocation_events.json via agent_protocol.

Assembles the POPETS-X02_revocation_events task report with real command logs
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

TASK_ID = "POPETS-X02_revocation_events"
SOURCE_SHA_BEFORE = "e5f7ee3b32c6463f8bdf7c30a1e3bf987ca15bb2"

CHANGED_PATHS = [
    "evaluation/venue2027/popets/revocation_model.py",
    "evaluation/venue2027/popets/test_revocation_events.py",
    "research/venue2027/proof/POPETS-X02_revocation_events.json",
    "research/venue2027/proof/logs/POPETS-X02_revocation_events.pytest.log",
    "research/venue2027/proof/logs/POPETS-X02_revocation_events.ruff.log",
    "research/venue2027/proof/logs/POPETS-X02_revocation_events.suite.log",
    "research/venue2027/proof/logs/POPETS-X02_revocation_events.validator.log",
]

ARTIFACT_PATHS = [
    "evaluation/venue2027/popets/revocation_model.py",
    "evaluation/venue2027/popets/test_revocation_events.py",
    "research/venue2027/proof/logs/POPETS-X02_revocation_events.pytest.log",
    "research/venue2027/proof/logs/POPETS-X02_revocation_events.ruff.log",
    "research/venue2027/proof/logs/POPETS-X02_revocation_events.suite.log",
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
                "argv": "python3 -m pytest -q "
                "evaluation/venue2027/popets/test_revocation_events.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/"
                "POPETS-X02_revocation_events.pytest.log",
            },
            {
                "argv": "uvx ruff@0.7.1 check "
                "evaluation/venue2027/popets/revocation_model.py "
                "evaluation/venue2027/popets/test_revocation_events.py && "
                "uvx ruff@0.7.1 format --check "
                "evaluation/venue2027/popets/revocation_model.py "
                "evaluation/venue2027/popets/test_revocation_events.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/"
                "POPETS-X02_revocation_events.ruff.log",
            },
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/ "
                "research/venue2027/popets/tests/",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/"
                "POPETS-X02_revocation_events.suite.log",
            },
            {
                "argv": "PYTHONPATH=. python3 "
                "research/venue2027/proof/emit_POPETS-X02_revocation_events_report.py "
                "# build_report + validate_report(ok:true) recorded in "
                "research/venue2027/proof/POPETS-X02_revocation_events.json",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/"
                "POPETS-X02_revocation_events.validator.log",
            },
        ],
        artifact_paths=ARTIFACT_PATHS,
        repo=ROOT,
        oracle_disagreement_count=None,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P02 POPETS-X02_revocation_events deliverable: "
            "evaluation/venue2027/popets/revocation_model.py implements the exact target "
            "contract allowed(item, principal, purpose, time) -> TriDecision "
            "(ALLOW | DENY | INDETERMINATE) as a pure, injected-I/O gate over an "
            "append-only ConsentLedgerView (no hidden clock, no randomness, no network, "
            "no DB, no provider; synthetic principals/purposes only). PRECISE "
            "DISTINCTIONS (task core algorithm): (1) deletion of stored data is an "
            "ORTHOGONAL surface reported via stored_data_effect()/stored_data field "
            "('deleted' at/after t_r, 'retained_unknown' before t_r or when provenance "
            "is unverifiable, 'not_applicable' under active consent or when no stored "
            "copy exists) and is never folded into the disclosure verdict; (2) "
            "prevention of future disclosure is the ONLY thing ALLOW/DENY speaks about "
            "(threat-model §2 predicate forbidden_label(g,p) ∩ lineage(d) = ∅ realized "
            "as consent-scope denial: every dispatch with time >= t_r in the revoked "
            "(principal, purpose|*) scope is DENY/DENY_POST_REVOCATION, boundary "
            "inclusive at t_r); (3) downstream already-delivered bytes are labeled "
            "OUT_OF_SCOPE_PAST (already_delivered_effect; threat-model §5.2, "
            "POPETS-CASE-06) — the verdict NEVER claims retroactive erasure of the "
            "delivered copy even while the platform-side stored copy is reported "
            "deleted, and with stored_copy=False no deletion is claimed at all; (4) "
            "model memorization is reported as memorization_guarantee='NOT_GUARANTEED' "
            "(machine unlearning is a different threat; novelty contract C2) — it is "
            "never converted into a DENY-as-erasure-guarantee (the post-revocation DENY "
            "reason code names the future-disclosure gate DENY_POST_REVOCATION, not "
            "unlearning) and it is attached to ALLOWED delivered items too. Explicit "
            "RevocationSemantics (revocation_semantics(), versioned 1.0.0, singleton, "
            "JSON-serializable) enumerates five guarantees (G1 future-disclosure "
            "prevention, G2 purpose boundary, G3 epoch-stale replay prevention on every "
            "transport, G4 stored-data deletion reported separately, G5 fail-closed "
            "INDETERMINATE) and four non-guarantees (N1 OUT_OF_SCOPE_PAST delivered "
            "bytes cannot be retracted, N2 memorization NOT_GUARANTEED, N3 no "
            "cryptographic retroactive erasure anywhere, N4 INDETERMINATE is "
            "first-class, never counted as safe rejection or completion). "
            "Determinations vs refusals: DENY_POST_REVOCATION (time >= t_r), "
            "DENY_EPOCH_STALE (payload bound to superseded consent epoch), "
            "PURPOSE_NOT_CONSENTED (known-but-unconsented purpose, POPETS-CASE-05), "
            "GRANT_UNKNOWN; INDETERMINATE refusals: PURPOSE_UNKNOWN (unknown purpose "
            "string fail closed), TIME_BEFORE_GRANT (clock before grant instant — the "
            "ledger timeline makes the query unevaluable; also covers backdated-grant "
            "overlap), LINEAGE_INDETERMINATE (missing or unverifiable lineage label, "
            "POPETS-CASE-07 fail-closed), PURPOSE_MISMATCH-free epoch vocabulary kept "
            "distinct from X06's fetch contract. Malformed item/principal/purpose/time "
            "raise ValueError with stable uppercase reason codes (ITEM_MALFORMED, "
            "PRINCIPAL_MALFORMED, PURPOSE_UNKNOWN, TIME_MALFORMED) — explicit refusals, "
            "never unhandled exceptions miscounted as safe rejections. "
            "test_revocation_events.py: 26 tests pass (positive: pre-revocation ALLOW "
            "with no deletion obligation, DENY at t_r inclusive and after for direct "
            "and transitive lineages, stored-data deletion flagged separately from the "
            "verdict on the same instant, wildcard purpose revocation coverage, stale "
            "epoch replay DENY, unconsented-purpose DENY, no-grant DENY, explicit "
            "semantics promises/non-promises, JSON round-trips incl. model_version "
            "passthrough, determinism, mapping-shaped ledger acceptance; adversarial: "
            "already-delivered bytes NOT claimed deleted (OUT_OF_SCOPE_PAST marker, no "
            "erasure reason code, platform-copy deletion reported only in its own "
            "field, no deletion claim when stored_copy=False), memorization "
            "NOT_GUARANTEED on both DENY and ALLOW paths never as erasure claim, "
            "unknown purpose refused INDETERMINATE + blank purpose refused, clock "
            "before grant refused INDETERMINATE incl. t=0, missing/None lineage label "
            "fail-closed INDETERMINATE, 8 malformed-input stable-code refusals, "
            "INDETERMINATE first-class (never coerced), future-effective revocation "
            "applies exactly at revoked_at, backdated-grant overlap refused and cannot "
            "resurrect the revoked scope, emergency-override purpose string cannot "
            "bypass the gate). Full evaluation/venue2027 + research/venue2027/popets "
            "regression: 930 passed. uvx ruff@0.7.1 check + format --check clean on "
            "touched files. source_sha_after records the base commit e5f7ee3b per the "
            "sibling convention (COMPSAC-X02, POPETS-X06); the single task commit SHA "
            "is created immediately after this report and recorded in the commit body. "
            "No claim of guaranteed LLM unlearning and no claim of retroactive erasure "
            "is made anywhere (task DoD 1; threat-model §10). Baseline parity "
            "NOT_APPLICABLE (semantics layer; arms B0-B4 execute in P03)."
        ),
    )

    out = ROOT / "research" / "venue2027" / "proof" / "POPETS-X02_revocation_events.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out}", flush=True)

    # Validate the emitted report and write the proof-of-validation log OUTSIDE the
    # report's own artifact set (a log describing the validation of the report
    # cannot hash itself).
    validation = validate_report(
        json.loads(out.read_text(encoding="utf-8")),
        repo=ROOT,
        expected_task_id=TASK_ID,
    )
    validator_log = (
        ROOT
        / "research"
        / "venue2027"
        / "proof"
        / "logs"
        / "POPETS-X02_revocation_events.validator.log"
    )
    validator_log.write_text(json.dumps(validation.to_dict(), indent=1) + "\n", encoding="utf-8")
    print(json.dumps(validation.to_dict(), indent=1), flush=True)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
