"""Tests for SACMAT-oracle — independent per-case truth oracle.

Positive controls prove the oracle derives truth from the case's declared
policy/consent ground truth (the dataset kernel's registered conformance
family) through the shared kernel, deterministically and JSON-serializably,
matching the manual canonical history per CASE_MATRIX sentinel semantics.

Adversarial controls prove independence and fail-closed semantics:

- ``verify_independence`` accepts the clean oracle source but refuses any
  source variant importing the SACMAT candidate machinery (the B0-B3
  baselines/engine models ``baselines.py`` or the temporal
  ``policy_trace_dsl.py``) with ``CANDIDATE_IMPORT`` — covering plain,
  aliased, from-import, package-qualified and tampered-live-source forms.
- The oracle derives truth from policy/consent ground truth, NOT from
  candidate reason codes: a case whose payload carries candidate-claimed
  reason codes or outcomes is adjudicated purely by its declared family, and
  flipping the candidate labels never flips the verdict.
- Unknown/undeclared families return first-class ``INDETERMINATE`` (never a
  silent safe verdict); missing case_id raises the stable kernel reason code.
- This test module imports only the oracle and the shared kernel
  (independent-oracle rule): no candidate baselines/DSL import, no DB, no
  model, no clock/randomness.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from evaluation.venue2027._shared import oracle_kernel as ok
from evaluation.venue2027.sacmat.independent_oracle import (
    ORACLE_ID,
    SACMAT_ORACLE_VERSION,
    SACMAT_RULES,
    adjudicate,
    verify_independence,
)

EVIDENCE = (
    {"uri": "sha256:cases/sacmat-case-01.json"},
    {"uri": "sha256:consent/grant-receipt.json"},
)


def case(family: str, case_id: str = "SACMAT-CASE-01", **extra: object) -> dict[str, object]:
    payload: dict[str, object] = {"case_id": case_id, "family": family, "evidence": EVIDENCE}
    payload.update(extra)
    return payload


# ---------------------------------------------------------------------------
# Positive controls — ground-truth families match the manual canonical history
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("family", "expected_outcome"),
    [
        ("conformant", "ADMIT"),
        ("expiry_divergence", "REJECT"),
        ("policy_skew", "REJECT"),
        ("obligation_mismatch", "REJECT"),
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
        "sha256:cases/sacmat-case-01.json",
        "sha256:consent/grant-receipt.json",
    )


def test_positive_kernel_delegation_identity() -> None:
    # The SACMAT oracle is a thin, faithful delegate of the audited kernel:
    # same verdict, same reason code, same evidence, oracle_id overridden.
    direct = ok.adjudicate(
        case("conformant", "SACMAT-CASE-DELEGATION"), SACMAT_RULES, oracle_id=ORACLE_ID
    )
    assert adjudicate(case("conformant", "SACMAT-CASE-DELEGATION")) == direct


def test_positive_payload_nested_family_is_honored() -> None:
    # Kernel contract accepts the family declared under `payload` too —
    # ground truth still flows from the case record, not from any arm output.
    result = adjudicate({"case_id": "SACMAT-CASE-02", "payload": {"family": "conformant"}})
    assert result.outcome == "ADMIT"


def test_positive_rule_table_shape_and_oracle_id() -> None:
    assert SACMAT_RULES == {
        "conformant": "ADMIT",
        "expiry_divergence": "REJECT",
        "policy_skew": "REJECT",
        "obligation_mismatch": "REJECT",
    }
    assert ORACLE_ID == "sacmat-conformance-reference"
    assert SACMAT_ORACLE_VERSION == "1.0.0"


def test_positive_deterministic_and_json_serializable() -> None:
    first = adjudicate(case("conformant", "SACMAT-CASE-DET"))
    second = adjudicate(case("conformant", "SACMAT-CASE-DET"))
    assert first == second
    payload = json.dumps(first.to_dict(), sort_keys=True).encode()
    restored = json.loads(payload)
    assert restored["outcome"] == "ADMIT"
    assert restored["oracle_id"] == ORACLE_ID
    assert restored["kernel_version"] == ok.ORACLE_KERNEL_VERSION


def test_positive_evidence_refs_captured_from_case() -> None:
    single = adjudicate(
        {"case_id": "SACMAT-CASE-EV", "family": "policy_skew", "evidence": [{"uri": "ev-1"}]}
    )
    assert single.evidence_refs == ("ev-1",)
    empty = adjudicate({"case_id": "SACMAT-CASE-EV2", "family": "conformant"})
    assert empty.evidence_refs == ()


# ---------------------------------------------------------------------------
# Adversarial controls — truth is NOT candidate reason codes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "candidate_label",
    [
        "CANDIDATE_CLAIMED_ADMIT",
        "CANDIDATE_CLAIMED_REJECT",
        "B3_TEMPORAL_CONFORMANCE_DIVERGENCE",
        "PERMIT",
        "DENY",
    ],
)
def test_adversarial_candidate_reason_codes_never_drive_truth(candidate_label: str) -> None:
    # A case whose ground truth is expiry_divergence stays REJECT even when
    # the candidate claims ADMIT/PERMIT and vice versa — the oracle reads the
    # policy/consent family, never candidate-supplied labels.
    conformant = case("conformant", "SACMAT-CASE-CAND-1", candidate_reason_code=candidate_label)
    assert adjudicate(conformant).outcome == "ADMIT"
    lapsed = case("expiry_divergence", "SACMAT-CASE-CAND-2", candidate_reason_code=candidate_label)
    assert adjudicate(lapsed).outcome == "REJECT"


def test_adversarial_candidate_outcome_fields_ignored() -> None:
    # Even a payload impersonating an arm observation (observed_outcome /
    # candidate verdict block) cannot move the verdict off the ground truth.
    forged = case(
        "expiry_divergence",
        "SACMAT-CASE-FORGED",
        observed_outcome="ADMIT",
        arm={"verdict": "PERMIT", "reason": "everything_fine"},
    )
    verdict = adjudicate(forged)
    assert verdict.outcome == "REJECT"
    assert verdict.reason_code == "RULE_EXPIRY_DIVERGENCE"


def test_adversarial_unknown_family_is_indeterminate() -> None:
    result = adjudicate(case("novel_unmodelled_family", "SACMAT-CASE-UNK"))
    assert result.outcome == "INDETERMINATE"
    assert result.reason_code == "UNMODELLED_FAMILY"
    assert result.oracle_id == ORACLE_ID


def test_adversarial_missing_family_is_indeterminate() -> None:
    result = adjudicate({"case_id": "SACMAT-CASE-NOFAM"})
    assert result.outcome == "INDETERMINATE"
    assert result.reason_code == "NO_FAMILY_DECLARED"


def test_adversarial_missing_case_id_raises_stable_code() -> None:
    with pytest.raises(ok.OracleError) as excinfo:
        adjudicate({"family": "conformant"})
    assert excinfo.value.reason_code == "MISSING_CASE_ID"


# ---------------------------------------------------------------------------
# Adversarial controls — independence from the SACMAT candidate machinery
# ---------------------------------------------------------------------------


def test_adversarial_clean_source_passes_independence() -> None:
    verify_independence()  # live module source: must not raise


@pytest.mark.parametrize(
    "snippet",
    [
        "import evaluation.venue2027.sacmat.baselines",
        "import evaluation.venue2027.sacmat.baselines as bl",
        "from evaluation.venue2027.sacmat.baselines import XacmlPolicyEngine",
        "from evaluation.venue2027.sacmat import baselines",
        "import baselines",
        "from baselines import run_baseline",
        "import evaluation.venue2027.sacmat.policy_trace_dsl",
        "from evaluation.venue2027.sacmat.policy_trace_dsl import evaluate_trace",
        "from evaluation.venue2027.sacmat import policy_trace_dsl",
        "import policy_trace_dsl",
    ],
)
def test_adversarial_candidate_import_refused(snippet: str) -> None:
    with pytest.raises(ok.OracleError) as excinfo:
        verify_independence(f'"""doc"""\n{snippet}\n')
    assert excinfo.value.reason_code == "CANDIDATE_IMPORT"


def test_adversarial_dynamic_import_refused() -> None:
    dynamic = (
        "import importlib\n"
        "m = importlib.import_module('evaluation.venue2027.sacmat.baselines')\n"
    )
    with pytest.raises(ok.OracleError) as excinfo:
        verify_independence(f'"""doc"""\n{dynamic}\n')
    assert excinfo.value.reason_code == "DYNAMIC_IMPORT_UNRESOLVABLE"


def test_adversarial_tampered_live_source_refused() -> None:
    # Tamper control: appending one candidate import to the real oracle source
    # must flip the verdict — the scan really reads the source it is given.
    from evaluation.venue2027.sacmat import independent_oracle

    live = pathlib.Path(independent_oracle.__file__)
    source = live.read_text(encoding="utf-8")
    verify_independence(source)  # unmodified live source stays clean
    tampered = source + "\nimport evaluation.venue2027.sacmat.baselines\n"
    with pytest.raises(ok.OracleError) as excinfo:
        verify_independence(tampered)
    assert excinfo.value.reason_code == "CANDIDATE_IMPORT"


def test_adversarial_unrelated_imports_accepted() -> None:
    # ast matching is exact per dotted component: similar-looking names of
    # OTHER modules must not trip the scanner (no substring over-matching).
    snippet = (
        "import json\n"
        "from evaluation.venue2027._shared import oracle_kernel\n"
        "import my_baselines_tests\n"
        "import sacmat_baseline_helpers\n"
        "from dataclasses import dataclass\n"
    )
    verify_independence(snippet)  # must not raise
