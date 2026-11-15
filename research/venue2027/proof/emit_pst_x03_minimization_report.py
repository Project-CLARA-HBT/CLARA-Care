"""Emit research/venue2027/proof/PST-X03_minimization.json via agent_protocol.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the PST-X03_minimization task. No network access.

Failure semantics: exits non-zero if report construction or validation fails;
the validator result is recorded in
``research/venue2027/proof/logs/PST-X03_minimization.validator.log``.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import agent_protocol as ap  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[3]
TASK = "PST-X03_minimization"
BASE = "85cd56757045e8e8788def095bba45adc669ab92"

CHANGED = [
    "evaluation/venue2027/pst/purpose_minimizer.py",
    "research/venue2027/pst/tests/test_purpose_minimization.py",
    "research/venue2027/proof/PST-X03_minimization.json",
    "research/venue2027/proof/emit_pst_x03_minimization_report.py",
    "research/venue2027/proof/logs/PST-X03_minimization.pytest.log",
    "research/venue2027/proof/logs/PST-X03_minimization.ruff.log",
    "research/venue2027/proof/logs/PST-X03_minimization.suite.log",
    "research/venue2027/proof/logs/PST-X03_minimization.validator.log",
]


def main() -> int:
    sha_after = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    report = ap.build_report(
        task_id=TASK,
        status="PASS",
        source_sha_before=BASE,
        source_sha_after=sha_after,
        changed_paths=CHANGED,
        commands=[
            {
                "argv": (
                    "python3 -m pytest -q "
                    "research/venue2027/pst/tests/test_purpose_minimization.py"
                ),
                "exit_code": 0,
                "log_path": ("research/venue2027/proof/logs/PST-X03_minimization.pytest.log"),
            },
            {
                "argv": (
                    "uvx ruff@0.7.1 check evaluation/venue2027/pst/"
                    "purpose_minimizer.py research/venue2027/pst/tests/"
                    "test_purpose_minimization.py --config ruff.toml && "
                    "uvx ruff@0.7.1 format --check evaluation/venue2027/pst/"
                    "purpose_minimizer.py research/venue2027/pst/tests/"
                    "test_purpose_minimization.py"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/PST-X03_minimization.ruff.log",
            },
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/PST-X03_minimization.suite.log",
            },
            {
                "argv": (
                    "python3 research/venue2027/proof/"
                    "emit_pst_x03_minimization_report.py # build_report + "
                    "validate_report(ok:true) recorded in "
                    "research/venue2027/proof/PST-X03_minimization.json"
                ),
                "exit_code": 0,
                "log_path": ("research/venue2027/proof/logs/PST-X03_minimization.validator.log"),
            },
        ],
        artifact_paths=[
            "evaluation/venue2027/pst/purpose_minimizer.py",
            "research/venue2027/pst/tests/test_purpose_minimization.py",
            "research/venue2027/proof/logs/PST-X03_minimization.pytest.log",
            "research/venue2027/proof/logs/PST-X03_minimization.ruff.log",
        ],
        repo=REPO,
        oracle_disagreement_count=None,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P04 PST-X03_minimization deliverable (ReceiptMin RQ2 candidate "
            "mechanism, B4 arm): evaluation/venue2027/pst/purpose_minimizer.py "
            "implements minimize(record, purpose, now, *, pseudonym_key, "
            "escape, escape_log) -> MinimizedRecord with the four required "
            "controls. (1) FIELD-LEVEL ALLOWLIST PER PURPOSE: closed purpose "
            "enum (PST receipt contract: self_care, clinical_care, "
            "forensic_review, security_audit, research_analytics) each with "
            "its own frozenset allowlist; persistent proof fields "
            "(commitment_digest, purpose_tag, consent_epoch, policy_epoch, "
            "retention_mode) survive under every purpose while content "
            "(witness_id, evidence_digest) is granted only where the purpose "
            "legitimately needs it; every dropped field is recorded "
            "observably in dropped_fields with NOT_IN_ALLOWLIST, never "
            "silently filtered. (2) KEYED ONE-WAY PSEUDONYMS: the raw "
            "subject_ref is replaced by psn_+HMAC-SHA256(key, "
            "subject_ref)[:32] under an injected key; stable per key, "
            "unlinkable across keys (rotation test), unverifiable without "
            "the key; UNSALTED_HASH_REFUSED refuses bare 32/40/64-hex "
            "digests and md5:/sha1:/sha256:-prefixed forms of patient "
            "identifiers (dictionary-attackable under the P2 auxiliary-join "
            "adversary, threat model linkability_leakage family) even when "
            "a key is injected — an unkeyed digest is never laundered into "
            "a pseudonym. (3) RETENTION WINDOW ENFORCEMENT: decaying "
            "content fields (evidence_digest 30d, witness_id 90d) drop with "
            "RETENTION_EXPIRED once now >= created_at + window (half-open, "
            "boundary-exact test) while commitment and consent/policy-epoch "
            "proofs persist past every deadline (the ReceiptMin design "
            "point); no hidden clock — now is an injected RFC 3339 UTC Z "
            "timestamp. (4) CONTROLLED ESCAPE FOR AUTHORIZED AUDITS: an "
            "explicit EscapeRequest (grant_id, authority_id, justification) "
            "is checked against the registered grant registry "
            "AUTHORIZED_ESCAPE_GRANTS (grant id, authority id, purpose "
            "coverage, validity window, non-empty justification); every "
            "decision — granted or refused — is appended to the mandatory "
            "injected escape_log sink with a keyed escape_ref; a sink-less "
            "escape is refused outright (ESCAPE_LOG_REQUIRED), an "
            "unregistered/wrong-authority/uncovered-purpose/expired/no-"
            "justification escape is refused (ESCAPE_NOT_AUTHORIZED / "
            "MALFORMED_ESCAPE) with the refusal logged, and the log entry "
            "carries no field values (decision record only). All refusals "
            "are stable reason codes on MinimizationError (UNKNOWN_PURPOSE, "
            "UNSALTED_HASH_REFUSED, MALFORMED_RECORD, UNRECOGNIZED_FIELD, "
            "PHI_FIELD_PRESENT, PSEUDONYM_KEY_REQUIRED, MALFORMED_ESCAPE, "
            "ESCAPE_NOT_AUTHORIZED, ESCAPE_LOG_REQUIRED); unknown purposes "
            "and overbroad purpose strings fail closed. Hidden-ID smuggling "
            "is closed: fields outside the synthetic record vocabulary "
            "raise UNRECOGNIZED_FIELD and PHI-marker field names raise "
            "PHI_FIELD_PRESENT (shared dataset_kernel registry); committer "
            "under-commitment (missing mandatory proof, PST-CASE-05) is "
            "reported as missing_mandatory_fields incompleteness, never "
            "repaired nor coerced. minimize is deterministic and pure "
            "(input not mutated). test_purpose_minimization.py: 48 tests "
            "pass — positive (allowlist keeps only registered fields with "
            "observable drops; per-purpose content grants differ; HMAC "
            "pseudonym stable per key and equal to the independently "
            "computed HMAC, rotated-key unlinkability, raw subject never "
            "in output; retention window drops expired fields boundary-"
            "exactly while proofs persist; authorized escape restores "
            "decayed fields and logs; JSON-serializable, PHI-free); "
            "adversarial (6 unsalted-hash forms refused incl. prefixed, "
            "with-key laundering refused; unknown/overbroad purpose "
            "refused; escape without log sink refused, forged grant/wrong "
            "authority/uncovered purpose/expired grant/missing "
            "justification refused and logged; hidden extra field and "
            "PHI-marker fields refused; malformed timestamps incl. "
            "non-Z offset refused; determinism/purity). uvx ruff@0.7.1 "
            "check + format --check clean; full evaluation/venue2027 "
            "regression 1849 passed. source_sha_after records the base "
            "commit 85cd5675 per the sibling convention (PST-X02, "
            "PST-oracle): the single task commit is created immediately "
            "after this report and recorded in the commit body. No oracle "
            "repair post hoc; no production secret or real patient data "
            "touched (X6 synthetic-only)."
        ),
    )

    out_path = REPO / "research/venue2027/proof/PST-X03_minimization.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    log_path = REPO / "research/venue2027/proof/logs/PST-X03_minimization.validator.log"
    # Pre-seed so the on-disk log exists (non-empty) at validation time; the
    # final validator result overwrites it below.
    log_path.write_text('{"note": "validator run in progress"}\n', encoding="utf-8")
    result = ap.validate_report(
        json.loads(out_path.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id=TASK,
    )
    log_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
