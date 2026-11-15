"""Tests for IFIP_SEC-oracle — independent per-case truth oracle.

Positive controls prove the kernel-delegating oracle maps the frozen IFIP
reference rule table to the CASE_MATRIX.md labels (fresh accept ADMITs,
cross-purpose/delegation replays and lineage splices REJECT) and returns
INDETERMINATE for unmodelled/undeclared families, with evidence pointers,
oracle id, determinism and JSON-serializability.

Adversarial controls prove independence (GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md
item 2): ``verify_independence`` accepts the clean oracle source but refuses
any source variant that imports a candidate module (``ifip_sec.baselines``,
``baselines``, ``consistency_token_adapter``) with ``CANDIDATE_IMPORT`` —
covering plain import, from-import, aliased import, dotted paths, and an
injected import appended to the real source (tamper control) — plus a
temp-on-disk oracle module importing the candidate that is refused at
verification time. The test module imports only the oracle: no candidate
module, no baseline adapter, no DB, no model, no clock/randomness.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from evaluation.venue2027._shared.oracle_kernel import ORACLE_KERNEL_VERSION
from evaluation.venue2027.ifip_sec.independent_oracle import (
    CANDIDATE_MODULE_NAMES,
    IFIP_INDEPENDENT_ORACLE_VERSION,
    IFIP_REFERENCE_RULES,
    ORACLE_ID,
    OracleError,
    OracleResult,
    adjudicate,
    adjudicate_case,
    run_self_checks,
    scan_source_for_candidate_imports,
    verify_independence,
)


def _case(family: str | None, case_id: str = "IFIP-SC-001") -> dict[str, object]:
    case: dict[str, object] = {"case_id": case_id}
    if family is not None:
        case["family"] = family
    return case


# ---------------------------------------------------------------------------
# Positive controls — frozen rule table adjudicates CASE_MATRIX.md labels
# ---------------------------------------------------------------------------


def test_positive_fresh_accept_admits_with_evidence() -> None:
    result = adjudicate(
        {
            "case_id": "IFIP_SEC-CASE-01",
            "family": "fresh_accept",
            "evidence": [{"uri": "research/venue2027/ifip_sec/cases/sample_cases.json"}],
        }
    )
    assert isinstance(result, OracleResult)
    assert result.outcome == "ADMIT"
    assert result.reason_code == "RULE_FRESH_ACCEPT"
    assert result.case_id == "IFIP_SEC-CASE-01"
    assert result.oracle_id == ORACLE_ID == "ifip-sec-reference"
    assert result.evidence_refs == ("research/venue2027/ifip_sec/cases/sample_cases.json",)


@pytest.mark.parametrize(
    ("family", "outcome"),
    [
        ("cross_purpose_replay", "REJECT"),
        ("delegation_replay", "REJECT"),
        ("lineage_splice", "REJECT"),
    ],
)
def test_positive_replay_and_lineage_families_reject(family: str, outcome: str) -> None:
    result = adjudicate(_case(family))
    assert result.outcome == outcome
    assert result.reason_code == f"RULE_{family.upper()}"
    assert result.evidence_refs == ()


def test_positive_unknown_and_undeclared_families_indeterminate() -> None:
    unmodelled = adjudicate(_case("key_rotation", "IFIP_SEC-CASE-08"))
    assert unmodelled.outcome == "INDETERMINATE"
    assert unmodelled.reason_code == "UNMODELLED_FAMILY"
    no_family = adjudicate(_case(None))
    assert no_family.outcome == "INDETERMINATE"
    assert no_family.reason_code == "NO_FAMILY_DECLARED"
    payload_family = adjudicate({"case_id": "c-payload", "payload": {"family": "ghost"}})
    assert payload_family.outcome == "INDETERMINATE"
    assert payload_family.reason_code == "UNMODELLED_FAMILY"


def test_positive_missing_case_id_refused() -> None:
    with pytest.raises(OracleError) as excinfo:
        adjudicate({"family": "fresh_accept"})
    assert excinfo.value.reason_code == "MISSING_CASE_ID"


def test_positive_deterministic_json_serializable_and_self_checks() -> None:
    first = adjudicate(_case("fresh_accept"))
    second = adjudicate(_case("fresh_accept"))
    assert first == second
    payload = json.dumps(first.to_dict(), sort_keys=True)
    restored = json.loads(payload)
    assert restored["outcome"] == "ADMIT"
    assert restored["oracle_id"] == ORACLE_ID
    assert restored["kernel_version"] == ORACLE_KERNEL_VERSION
    assert IFIP_REFERENCE_RULES == {
        "fresh_accept": "ADMIT",
        "cross_purpose_replay": "REJECT",
        "delegation_replay": "REJECT",
        "lineage_splice": "REJECT",
    }
    assert adjudicate_case is adjudicate
    self_checks = run_self_checks()
    assert [r.outcome for r in self_checks] == [
        "ADMIT",
        "REJECT",
        "REJECT",
        "REJECT",
        "INDETERMINATE",
    ]
    assert IFIP_INDEPENDENT_ORACLE_VERSION.startswith("clara.ifip_sec.independent-oracle")


# ---------------------------------------------------------------------------
# Adversarial controls — independence from candidate modules
# ---------------------------------------------------------------------------


def test_adversarial_clean_source_passes_independence() -> None:
    verify_independence()  # live module source: must not raise
    assert scan_source_for_candidate_imports() == frozenset()


@pytest.mark.parametrize(
    "snippet",
    [
        "import ifip_sec.baselines",
        "import ifip_sec.baselines as b",
        "from ifip_sec.baselines import BaselineContext",
        "from evaluation.venue2027.ifip_sec import baselines",
        "import baselines",
        "from baselines import parity_check",
        "import consistency_token_adapter",
        "from consistency_token_adapter import check_with_revision",
        "from evaluation.venue2027.ifip_sec import consistency_token_adapter",
        "import evaluation.venue2027.ifip_sec.baselines",
    ],
)
def test_adversarial_candidate_import_refused(snippet: str) -> None:
    with pytest.raises(OracleError) as excinfo:
        verify_independence(f'"""doc"""\n{snippet}\n')
    assert excinfo.value.reason_code == "CANDIDATE_IMPORT"


def test_adversarial_unrelated_imports_accepted() -> None:
    # ast matching is per dotted component (never substring): look-alike names
    # of OTHER modules must not trip the scan.
    snippet = (
        "import ast\n"
        "from evaluation.venue2027._shared.oracle_kernel import adjudicate\n"
        "import my_baseline_labels\n"
        "from dataclasses import dataclass\n"
        "import evaluation.venue2027.ifip_sec.independent_oracle\n"
    )
    assert scan_source_for_candidate_imports(snippet) == frozenset()
    verify_independence(snippet)


def test_adversarial_dynamic_import_flagged() -> None:
    dynamic = 'x = __import__("evaluation.venue2027.ifip_sec.baselines")\n'
    assert scan_source_for_candidate_imports(dynamic) == frozenset({"__dynamic__"})
    with pytest.raises(OracleError) as excinfo:
        verify_independence(dynamic)
    assert excinfo.value.reason_code == "CANDIDATE_IMPORT"
    importlib_snippet = (
        "import importlib\n" 'm = importlib.import_module("consistency_token_adapter")\n'
    )
    assert scan_source_for_candidate_imports(importlib_snippet) == frozenset({"__dynamic__"})
    with pytest.raises(OracleError):
        verify_independence(importlib_snippet)


def test_adversarial_temp_oracle_importing_candidate_refused(tmp_path: pathlib.Path) -> None:
    # A candidate-importing "oracle" written to a temp file must be refused by
    # the kernel's audited AST guard (the negative/adversarial control of the
    # SH-independent_oracle contract), at import-verification time.
    rogue = tmp_path / "rogue_oracle.py"
    rogue.write_text(
        "import baselines\n" "def adjudicate(case):\n" "    return baselines.parity_check(case)\n",
        encoding="utf-8",
    )
    from evaluation.venue2027._shared.oracle_kernel import (
        assert_oracle_independence as kernel_guard,
    )

    with pytest.raises(OracleError) as excinfo:
        kernel_guard(str(rogue), CANDIDATE_MODULE_NAMES)
    assert excinfo.value.reason_code == "CANDIDATE_IMPORT"
    with pytest.raises(OracleError):
        verify_independence(rogue.read_text(encoding="utf-8"))


def test_adversarial_tampered_live_source_refused() -> None:
    # Tamper control: appending one candidate import to the real source must
    # flip the verdict (the scan really reads the source it is given).
    source = pathlib.Path(__file__).with_name("independent_oracle.py").read_text(encoding="utf-8")
    with pytest.raises(OracleError) as excinfo:
        verify_independence(source + "\nimport ifip_sec.baselines\n")
    assert excinfo.value.reason_code == "CANDIDATE_IMPORT"
    assert "ifip_sec.baselines" in excinfo.value.detail
