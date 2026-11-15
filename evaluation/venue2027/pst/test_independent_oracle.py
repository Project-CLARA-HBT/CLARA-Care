"""Tests for PST-oracle — independent per-case truth oracle.

Positive controls prove the oracle derives truth from the case's declared
scenario family (the dataset kernel's registered audit-receipt families)
through the shared kernel, deterministically and JSON-serializably, matching
the CASE_MATRIX sentinel semantics (PST-CASE-01/04 reconstruct+integrity ->
ADMIT; PST-CASE-05 over-redaction and PST-CASE-02/06 linkability leak ->
REJECT).

Adversarial controls prove independence and fail-closed semantics:

- ``verify_independence`` accepts the clean oracle source but refuses any
  source variant importing the PST candidate machinery (the B0-B4 baseline
  arms ``baselines.py`` or the C0 arm ``candidate.py``) with
  ``CANDIDATE_IMPORT`` — covering plain, aliased, from-import,
  package-qualified and tampered-live-source forms, plus a temp oracle file
  on disk that imports the candidate and is refused by the kernel-level
  scanner.
- The oracle derives truth from the declared family, NOT from candidate
  reason codes: a case whose payload carries candidate-claimed reason codes
  or observed arm outcomes is adjudicated purely by its declared family, and
  flipping the candidate labels never flips the verdict.
- Unknown/undeclared families return first-class ``INDETERMINATE`` (never a
  silent safe verdict); missing case_id raises the stable kernel reason code.
- This test module imports only the oracle and the shared kernel
  (independent-oracle rule): no candidate baselines/candidate import, no DB,
  no model, no clock/randomness.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from evaluation.venue2027._shared import oracle_kernel as ok
from evaluation.venue2027.pst.independent_oracle import (
    FORBIDDEN_MODULE_NAMES,
    ORACLE_ID,
    PST_ORACLE_VERSION,
    PST_RULES,
    adjudicate,
    verify_independence,
)

EVIDENCE = (
    {"uri": "sha256:cases/pst-case-01.json"},
    {"uri": "sha256:receipts/minimal-receipt.json"},
)


def case(family: str, case_id: str = "PST-CASE-01", **extra: object) -> dict[str, object]:
    payload: dict[str, object] = {"case_id": case_id, "family": family, "evidence": EVIDENCE}
    payload.update(extra)
    return payload


# ---------------------------------------------------------------------------
# Positive controls — ground-truth families match the CASE_MATRIX sentinels
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("family", "expected_outcome"),
    [
        ("full_evidence", "ADMIT"),
        ("minimized_omission", "REJECT"),
        ("receipt_anchored", "ADMIT"),
        ("linkability_leak", "REJECT"),
    ],
)
def test_positive_registered_families_adjudicated_from_ground_truth(
    family: str, expected_outcome: str
) -> None:
    result = adjudicate(case(family))
    assert isinstance(result, ok.OracleResult)
    assert result.outcome == expected_outcome
    assert result.reason_code == f"RULE_{family.upper()}"
    assert result.oracle_id == ORACLE_ID
    assert result.evidence_refs == (
        "sha256:cases/pst-case-01.json",
        "sha256:receipts/minimal-receipt.json",
    )


def test_positive_kernel_delegation_identity() -> None:
    # The PST oracle is a thin, faithful delegate of the audited kernel:
    # same verdict, same reason code, same evidence, oracle_id overridden.
    direct = ok.adjudicate(
        case("full_evidence", "PST-CASE-DELEGATION"), PST_RULES, oracle_id=ORACLE_ID
    )
    assert adjudicate(case("full_evidence", "PST-CASE-DELEGATION")) == direct


def test_positive_payload_nested_family_is_honored() -> None:
    # Kernel contract accepts the family declared under `payload` too —
    # ground truth still flows from the case record, not from any arm output.
    result = adjudicate({"case_id": "PST-CASE-02", "payload": {"family": "receipt_anchored"}})
    assert result.outcome == "ADMIT"


def test_positive_rule_table_shape_and_oracle_id() -> None:
    assert PST_RULES == {
        "full_evidence": "ADMIT",
        "minimized_omission": "REJECT",
        "receipt_anchored": "ADMIT",
        "linkability_leak": "REJECT",
    }
    assert ORACLE_ID == "pst-forensic-reference"
    assert PST_ORACLE_VERSION == "1.0.0"
    assert FORBIDDEN_MODULE_NAMES == ("pst.baselines", "baselines", "candidate")


def test_positive_deterministic_and_json_serializable() -> None:
    first = adjudicate(case("full_evidence", "PST-CASE-DET"))
    second = adjudicate(case("full_evidence", "PST-CASE-DET"))
    assert first == second
    payload = json.dumps(first.to_dict(), sort_keys=True).encode()
    restored = json.loads(payload)
    assert restored["outcome"] == "ADMIT"
    assert restored["oracle_id"] == ORACLE_ID
    assert restored["kernel_version"] == ok.ORACLE_KERNEL_VERSION


def test_positive_deterministic_across_all_families() -> None:
    # Same case adjudicated twice per family must yield identical results —
    # no hidden clock, randomness or environment dependence.
    for family, expected in PST_RULES.items():
        verdicts = {adjudicate(case(family, "PST-CASE-DETF")) for _ in range(3)}
        assert len(verdicts) == 1
        assert next(iter(verdicts)).outcome == expected


def test_positive_evidence_refs_captured_from_case() -> None:
    single = adjudicate(
        {"case_id": "PST-CASE-EV", "family": "minimized_omission", "evidence": [{"uri": "ev-1"}]}
    )
    assert single.evidence_refs == ("ev-1",)
    empty = adjudicate({"case_id": "PST-CASE-EV2", "family": "full_evidence"})
    assert empty.evidence_refs == ()


# ---------------------------------------------------------------------------
# Adversarial controls — truth is NOT candidate reason codes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "candidate_label",
    [
        "CANDIDATE_CLAIMED_ADMIT",
        "CANDIDATE_CLAIMED_REJECT",
        "B4_MINIMIZED_RECEIPT_PASS",
        "PERMIT",
        "DENY",
    ],
)
def test_adversarial_candidate_reason_codes_never_drive_truth(candidate_label: str) -> None:
    # A case whose ground truth is minimized_omission stays REJECT even when
    # the candidate claims ADMIT/PERMIT and vice versa — the oracle reads the
    # declared scenario family, never candidate-supplied labels.
    leaky = case("full_evidence", "PST-CASE-CAND-1", candidate_reason_code=candidate_label)
    assert adjudicate(leaky).outcome == "ADMIT"
    omitted = case("minimized_omission", "PST-CASE-CAND-2", candidate_reason_code=candidate_label)
    assert adjudicate(omitted).outcome == "REJECT"


def test_adversarial_candidate_outcome_fields_ignored() -> None:
    # Even a payload impersonating an arm observation (observed_outcome /
    # candidate verdict block / tampered witness status) cannot move the
    # verdict off the ground truth.
    forged = case(
        "linkability_leak",
        "PST-CASE-FORGED",
        observed_outcome="ADMIT",
        arm={"verdict": "PERMIT", "reason": "receipt_forged_clean"},
    )
    verdict = adjudicate(forged)
    assert verdict.outcome == "REJECT"
    assert verdict.reason_code == "RULE_LINKABILITY_LEAK"


def test_adversarial_unknown_family_is_indeterminate() -> None:
    result = adjudicate(case("novel_unmodelled_family", "PST-CASE-UNK"))
    assert result.outcome == "INDETERMINATE"
    assert result.reason_code == "UNMODELLED_FAMILY"
    assert result.oracle_id == ORACLE_ID


def test_adversarial_missing_family_is_indeterminate() -> None:
    result = adjudicate({"case_id": "PST-CASE-NOFAM"})
    assert result.outcome == "INDETERMINATE"
    assert result.reason_code == "NO_FAMILY_DECLARED"


def test_adversarial_missing_case_id_raises_stable_code() -> None:
    with pytest.raises(ok.OracleError) as excinfo:
        adjudicate({"family": "full_evidence"})
    assert excinfo.value.reason_code == "MISSING_CASE_ID"


# ---------------------------------------------------------------------------
# Adversarial controls — independence from the PST candidate machinery
# ---------------------------------------------------------------------------


def test_adversarial_clean_source_passes_independence() -> None:
    verify_independence()  # live module source: must not raise


@pytest.mark.parametrize(
    "snippet",
    [
        "import evaluation.venue2027.pst.baselines",
        "import evaluation.venue2027.pst.baselines as bl",
        "from evaluation.venue2027.pst.baselines import FullPlaintextLogArm",
        "from evaluation.venue2027.pst import baselines",
        "import baselines",
        "from baselines import run_baseline",
        "import evaluation.venue2027.pst.candidate",
        "from evaluation.venue2027.pst.candidate import MinimizedReceiptArm",
        "from evaluation.venue2027.pst import candidate",
        "import candidate",
    ],
)
def test_adversarial_candidate_import_refused(snippet: str) -> None:
    with pytest.raises(ok.OracleError) as excinfo:
        verify_independence(f'"""doc"""\n{snippet}\n')
    assert excinfo.value.reason_code == "CANDIDATE_IMPORT"


def test_adversarial_dynamic_import_refused() -> None:
    dynamic = (
        "import importlib\n" "m = importlib.import_module('evaluation.venue2027.pst.baselines')\n"
    )
    with pytest.raises(ok.OracleError) as excinfo:
        verify_independence(f'"""doc"""\n{dynamic}\n')
    assert excinfo.value.reason_code == "DYNAMIC_IMPORT_UNRESOLVABLE"


def test_adversarial_tampered_live_source_refused() -> None:
    # Tamper control: appending one candidate import to the real oracle source
    # must flip the verdict — the scan really reads the source it is given.
    from evaluation.venue2027.pst import independent_oracle

    live = pathlib.Path(independent_oracle.__file__)
    source = live.read_text(encoding="utf-8")
    verify_independence(source)  # unmodified live source stays clean
    tampered = source + "\nimport evaluation.venue2027.pst.baselines\n"
    with pytest.raises(ok.OracleError) as excinfo:
        verify_independence(tampered)
    assert excinfo.value.reason_code == "CANDIDATE_IMPORT"


def test_adversarial_temp_oracle_importing_candidate_refused(tmp_path: pathlib.Path) -> None:
    # A temp oracle module on disk that imports the PST candidate machinery is
    # refused by the audited kernel scanner run against the file path itself —
    # the independence gate binds to real files, not just injected text.
    # (Root-level bare import form so the kernel-level root-component scan
    # fires; the package-qualified form is covered by the module-local scan.)
    temp_oracle = tmp_path / "independent_oracle.py"
    temp_oracle.write_text(
        "from evaluation.venue2027._shared import oracle_kernel\n" "import baselines\n",
        encoding="utf-8",
    )
    with pytest.raises(ok.OracleError) as excinfo:
        ok.assert_oracle_independence(str(temp_oracle), FORBIDDEN_MODULE_NAMES)
    assert excinfo.value.reason_code == "CANDIDATE_IMPORT"
    # The module-local full-target scan refuses the same file's source too.
    with pytest.raises(ok.OracleError) as excinfo_local:
        verify_independence(temp_oracle.read_text(encoding="utf-8"))
    assert excinfo_local.value.reason_code == "CANDIDATE_IMPORT"
    # A clean temp oracle passes the same file-level gate.
    clean_oracle = tmp_path / "clean_oracle.py"
    clean_oracle.write_text(
        "from evaluation.venue2027._shared import oracle_kernel\n",
        encoding="utf-8",
    )
    ok.assert_oracle_independence(str(clean_oracle), FORBIDDEN_MODULE_NAMES)  # must not raise


def test_adversarial_unrelated_imports_accepted() -> None:
    # ast matching is exact per dotted component: similar-looking names of
    # OTHER modules must not trip the scanner (no substring over-matching).
    snippet = (
        "import json\n"
        "from evaluation.venue2027._shared import oracle_kernel\n"
        "import my_baselines_tests\n"
        "import pst_baseline_helpers\n"
        "import candidate_eval_tools\n"
        "from dataclasses import dataclass\n"
    )
    verify_independence(snippet)  # must not raise
