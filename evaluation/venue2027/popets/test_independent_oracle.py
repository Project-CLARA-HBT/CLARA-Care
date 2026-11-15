"""Tests for POPETS-oracle — independent revocation-reference truth oracle.

Positive controls prove the oracle delegates to the shared kernel and returns
the pre-registered future-dispatch noninterference matrix (``fresh`` -> ADMIT,
``revoked_then_dispatch`` / ``cross_purpose`` / ``transitive_gap`` -> REJECT)
deterministically and JSON-serializably, with the revocation verdict content
carried on every verdict (authorized dispatch, refused dispatch, CASE_MATRIX
basis rows, declared observation-model condition).

Verdict-shape controls prove the oracle expresses a *future-dispatch
noninterference verdict* — what may leave the process post-revocation and what
leakage it refuses — and never claims retroactive erasure of already-delivered
bytes (POPETS-CASE-06 ``OUT_OF_SCOPE_PAST`` threat precision): no "erased",
"retracted" or "unlearned" outcome vocabulary exists anywhere in the verdict.

Adversarial controls prove independence and fail-closed semantics:

- ``verify_independence`` accepts the clean oracle source but refuses any
  source variant importing the candidate module (``popets.baselines`` / any
  ``baselines`` module, ``popets.revocation_model`` / any ``revocation_model``
  module) with ``CANDIDATE_IMPORT`` — plain import, from-import, aliased,
  dotted and injected-tamper forms — and flags unresolvable dynamic imports.
- A temp *rogue oracle* file (importing the candidate) is refused by the
  audited kernel guard — independence is a property of any oracle source, not
  just the live one.
- Candidate-supplied decision fields inside a case cannot flip the verdict
  (no circular label generation): ground truth comes only from the frozen
  family rule table.
- Undeclared/unmodelled families, nested-payload families and missing case
  ids fail closed with stable kernel reason codes; ``INDETERMINATE`` is
  retained (with ``basis_cases=PENDING_ADJUDICATION``), never coerced.

The test module imports only the oracle and the shared kernel (independent-
oracle rule): no candidate baseline import, no DB, no network, no clock.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from evaluation.venue2027._shared import oracle_kernel
from evaluation.venue2027._shared.oracle_kernel import OracleError
from evaluation.venue2027.popets import independent_oracle as oracle
from evaluation.venue2027.popets.independent_oracle import (
    NONINTERFERENCE_TABLE,
    ORACLE_ID,
    POPETS_INDEPENDENT_ORACLE_VERSION,
    POPETS_NONINTERFERENCE_RULES,
    NoninterferenceOracleVerdict,
    adjudicate,
    adjudicate_noninterference,
    run_self_checks,
    scan_for_candidate_imports,
    verify_independence,
    verify_rule_table_alignment,
)

# ---------------------------------------------------------------------------
# Positive controls — pre-registered noninterference matrix
# ---------------------------------------------------------------------------


def test_positive_fresh_admits_authorized_dispatch() -> None:
    result = adjudicate(
        {
            "case_id": "POPETS-CASE-01",
            "family": "fresh",
            "evidence": [{"uri": "research/venue2027/VENUES/popets/CASE_MATRIX.md"}],
        }
    )
    assert result.outcome == "ADMIT"
    assert result.case_id == "POPETS-CASE-01"
    assert result.oracle_id == ORACLE_ID == "popets-revocation-reference"
    assert result.reason_code == "RULE_FRESH"
    assert result.evidence_refs == ("research/venue2027/VENUES/popets/CASE_MATRIX.md",)
    assert result.to_dict()["kernel_version"] == oracle_kernel.ORACLE_KERNEL_VERSION


@pytest.mark.parametrize(
    ("family", "expected_outcome", "expected_reason"),
    [
        ("fresh", "ADMIT", "RULE_FRESH"),
        ("revoked_then_dispatch", "REJECT", "RULE_REVOKED_THEN_DISPATCH"),
        ("cross_purpose", "REJECT", "RULE_CROSS_PURPOSE"),
        ("transitive_gap", "REJECT", "RULE_TRANSITIVE_GAP"),
    ],
)
def test_positive_full_rule_matrix_matches_preregistration(
    family: str, expected_outcome: str, expected_reason: str
) -> None:
    result = adjudicate({"case_id": f"case-{family}", "family": family})
    assert result.outcome == expected_outcome
    assert result.reason_code == expected_reason
    assert result.oracle_id == ORACLE_ID


def test_positive_nested_payload_family_adjudicates() -> None:
    result = adjudicate({"case_id": "case-nested", "payload": {"family": "revoked_then_dispatch"}})
    assert result.outcome == "REJECT"
    assert result.reason_code == "RULE_REVOKED_THEN_DISPATCH"


def test_positive_noninterference_verdict_carries_revocation_content() -> None:
    verdict = adjudicate_noninterference(
        {"case_id": "POPETS-CASE-02", "family": "revoked_then_dispatch"}
    )
    assert isinstance(verdict, NoninterferenceOracleVerdict)
    assert verdict.oracle_result.outcome == "REJECT"
    assert verdict.authorized_dispatch == "nothing after the effective revocation time"
    assert "canary" in verdict.refused_dispatch
    assert verdict.basis_cases == "POPETS-CASE-02_RETRY_LEAKAGE"
    assert "reauthorize at every dispatch" in verdict.observation_condition
    payload = json.dumps(verdict.to_dict(), sort_keys=True)
    assert isinstance(json.loads(payload), dict)
    assert verdict.oracle_version == POPETS_INDEPENDENT_ORACLE_VERSION


def test_positive_all_rule_rows_reference_registered_basis() -> None:
    assert set(NONINTERFERENCE_TABLE) == set(POPETS_NONINTERFERENCE_RULES)
    for family, rule in NONINTERFERENCE_TABLE.items():
        assert rule.authorized_dispatch and rule.refused_dispatch
        assert rule.basis_cases and rule.observation_condition
        # The clean control refuses no dispatch beyond its stated scope.
        if family == "fresh":
            assert rule.basis_cases == "none"


def test_positive_deterministic_and_json_serializable() -> None:
    case = {"case_id": "case-stable", "family": "fresh", "evidence": []}
    first, second = adjudicate(case), adjudicate(case)
    assert first == second
    payload = json.dumps(first.to_dict(), sort_keys=True)
    assert isinstance(json.loads(payload), dict)


def test_positive_self_checks_match_preregistered_matrix() -> None:
    verdicts = run_self_checks()
    assert [v.oracle_result.outcome for v in verdicts] == [
        "ADMIT",
        "REJECT",
        "REJECT",
        "REJECT",
        "INDETERMINATE",
    ]
    assert all(v.basis_cases != "" for v in verdicts)


def test_positive_rule_table_matches_dataset_registry() -> None:
    # The locally restated family registry must stay aligned with the shared
    # dataset kernel's POPETS row (checked without importing it: restated).
    verify_rule_table_alignment()  # must not raise
    assert tuple(POPETS_NONINTERFERENCE_RULES) == (
        "fresh",
        "revoked_then_dispatch",
        "cross_purpose",
        "transitive_gap",
    )


def test_positive_independent_oracle_matches_manual_canonical_history() -> None:
    # Sentinel parity: the oracle's matrix equals the manually adjudicated
    # canonical history from the CASE_MATRIX (POPETS-CASE-01..09).
    canonical = {
        "fresh": "ADMIT",  # POPETS-CASE-01/04 authorized utility, no false invalidation
        "revoked_then_dispatch": "REJECT",  # POPETS-CASE-02/08 retry leakage
        "cross_purpose": "REJECT",  # POPETS-CASE-05 purpose binding
        "transitive_gap": "REJECT",  # POPETS-CASE-03/07 lineage completeness
    }
    observed = {
        family: adjudicate({"case_id": f"parity-{family}", "family": family}).outcome
        for family in canonical
    }
    assert observed == canonical


# ---------------------------------------------------------------------------
# Verdict-shape controls — noninterference verdict, never retroactive erasure
# ---------------------------------------------------------------------------


def test_verdicts_express_future_dispatch_not_retroactive_erasure() -> None:
    # The whole verdict vocabulary is future-dispatch language; retroactive
    # erasure claims ("erased", "retracted", "unlearned") are absent by
    # construction (blueprint falsification criterion / POPETS-CASE-06).
    forbidden_tokens = ("erased", "retracted", "unlearned", "retroactively")
    for family, rule in NONINTERFERENCE_TABLE.items():
        blob = " ".join(
            (rule.authorized_dispatch, rule.refused_dispatch, rule.observation_condition)
        ).lower()
        assert not any(token in blob for token in forbidden_tokens), family
        # Every rule names what may leave the process and the leakage it
        # refuses — a dispatch verdict, not a storage claim.
        assert rule.authorized_dispatch and rule.refused_dispatch, family


def test_verdict_revocation_witness_rejects_future_dispatch_not_past_delivery() -> None:
    # POPETS-CASE-02: the verdict refuses the post-revocation *dispatch*;
    # already-delivered bytes are out of scope (no retroactive erasure).
    verdict = adjudicate_noninterference(
        {"case_id": "POPETS-CASE-02", "family": "revoked_then_dispatch"}
    )
    assert verdict.oracle_result.outcome == "REJECT"
    assert verdict.authorized_dispatch == "nothing after the effective revocation time"
    assert "post-revocation" in verdict.refused_dispatch


# ---------------------------------------------------------------------------
# Adversarial controls — independence from candidate modules
# ---------------------------------------------------------------------------


def test_adversarial_clean_source_passes_independence() -> None:
    verify_independence()  # live module source: must not raise
    assert scan_for_candidate_imports() == frozenset()


@pytest.mark.parametrize(
    "snippet",
    [
        "import evaluation.venue2027.popets.baselines",
        "import evaluation.venue2027.popets.baselines as b",
        "from evaluation.venue2027.popets.baselines import run_baseline",
        "from evaluation.venue2027.popets import baselines",
        "import baselines",
        "from baselines import run_baseline",
        "import popets.baselines",
        "from evaluation.venue2027.acns import baselines",
        "import evaluation.venue2027.popets.revocation_model",
        "from evaluation.venue2027.popets.revocation_model import decide",
        "from evaluation.venue2027.popets import revocation_model",
        "import revocation_model",
        "from revocation_model import decide",
        "import popets.revocation_model",
    ],
)
def test_adversarial_candidate_import_refused(snippet: str) -> None:
    with pytest.raises(OracleError) as excinfo:
        verify_independence(f'"""doc"""\n{snippet}\n')
    assert excinfo.value.reason_code == "CANDIDATE_IMPORT"
    assert "baselines" in excinfo.value.detail or "revocation_model" in excinfo.value.detail


def test_adversarial_similar_names_do_not_trip_the_scan() -> None:
    # Exact component matching: modules whose names merely *contain* a
    # candidate basename are not candidate imports.
    snippet = (
        "import ast\n"
        "import my_baselines_tests\n"
        "import revocation_modeling_utils\n"
        "from evaluation.venue2027.popets.independent_oracle import adjudicate\n"
        "from evaluation.venue2027._shared import oracle_kernel\n"
    )
    assert scan_for_candidate_imports(snippet) == frozenset()
    verify_independence(snippet)


def test_adversarial_dynamic_import_flagged() -> None:
    dynamic = 'm = __import__("evaluation.venue2027.popets.baselines")\n'
    assert scan_for_candidate_imports(dynamic) == frozenset({"__dynamic__"})
    with pytest.raises(OracleError):
        verify_independence(dynamic)
    importlib_snippet = (
        "import importlib\n"
        'm = importlib.import_module("evaluation.venue2027.popets.baselines")\n'
    )
    assert scan_for_candidate_imports(importlib_snippet) == frozenset({"__dynamic__"})
    with pytest.raises(OracleError):
        verify_independence(importlib_snippet)
    model_dynamic = (
        "import importlib\n"
        'm = importlib.import_module("evaluation.venue2027.popets.revocation_model")\n'
    )
    assert scan_for_candidate_imports(model_dynamic) == frozenset({"__dynamic__"})
    with pytest.raises(OracleError):
        verify_independence(model_dynamic)


def test_adversarial_temp_rogue_oracle_refused_by_kernel_guard(tmp_path: pathlib.Path) -> None:
    # Independence is a property of any oracle source: a rogue oracle file in
    # a temp directory importing the candidate is refused by the audited
    # kernel guard with CANDIDATE_IMPORT — the live module's cleanliness does
    # not launder it.
    rogue = tmp_path / "rogue_oracle.py"
    rogue.write_text(
        "import baselines\n" "from revocation_model import decide\n",
        encoding="utf-8",
    )
    with pytest.raises(OracleError) as excinfo:
        oracle_kernel.assert_oracle_independence(str(rogue), oracle.CANDIDATE_BASENAMES)
    assert excinfo.value.reason_code == "CANDIDATE_IMPORT"


def test_adversarial_temp_rogue_oracle_refused_by_module_scan(tmp_path: pathlib.Path) -> None:
    rogue = tmp_path / "rogue_oracle_scan.py"
    rogue.write_text("import baselines\n", encoding="utf-8")
    with pytest.raises(OracleError) as excinfo:
        verify_independence(rogue.read_text(encoding="utf-8"))
    assert excinfo.value.reason_code == "CANDIDATE_IMPORT"


def test_adversarial_temp_rogue_dynamic_oracle_refused(tmp_path: pathlib.Path) -> None:
    rogue = tmp_path / "rogue_dynamic_oracle.py"
    rogue.write_text(
        "import importlib\nimportlib.import_module('baselines')\n",
        encoding="utf-8",
    )
    with pytest.raises(OracleError) as excinfo:
        oracle_kernel.assert_oracle_independence(str(rogue), oracle.CANDIDATE_BASENAMES)
    assert excinfo.value.reason_code == "DYNAMIC_IMPORT_UNRESOLVABLE"


def test_adversarial_tampered_live_source_refused() -> None:
    # Tamper control: appending one candidate import to the real source must
    # flip the verdict (the scan really reads the source it is given).
    source = oracle.__file__
    assert source is not None
    live = pathlib.Path(source).read_text(encoding="utf-8")
    with pytest.raises(OracleError) as excinfo:
        verify_independence(live + "\nimport evaluation.venue2027.popets.revocation_model\n")
    assert excinfo.value.reason_code == "CANDIDATE_IMPORT"


def test_adversarial_kernel_ast_guard_also_clean() -> None:
    # The audited kernel guard accepts this oracle's live file as well.
    source_path = oracle.__file__
    assert source_path is not None
    oracle_kernel.assert_oracle_independence(source_path, ())


# ---------------------------------------------------------------------------
# Adversarial controls — fail-closed adjudication semantics
# ---------------------------------------------------------------------------


def test_adversarial_unmodelled_family_is_indeterminate_not_reject() -> None:
    result = adjudicate({"case_id": "case-unknown", "family": "novel_leakage_family"})
    assert result.outcome == "INDETERMINATE"
    assert result.reason_code == "UNMODELLED_FAMILY"
    verdict = adjudicate_noninterference(
        {"case_id": "case-unknown", "family": "novel_leakage_family"}
    )
    assert verdict.basis_cases == "PENDING_ADJUDICATION"
    assert verdict.authorized_dispatch == "" and verdict.refused_dispatch == ""


def test_adversarial_missing_family_is_indeterminate() -> None:
    result = adjudicate({"case_id": "case-nofamily"})
    assert result.outcome == "INDETERMINATE"
    assert result.reason_code == "NO_FAMILY_DECLARED"


def test_adversarial_missing_case_id_fails_closed() -> None:
    with pytest.raises(OracleError) as excinfo:
        adjudicate({"family": "fresh"})
    assert excinfo.value.reason_code == "MISSING_CASE_ID"


def test_adversarial_malformed_case_fails_closed() -> None:
    with pytest.raises(OracleError) as excinfo:
        adjudicate(["not", "a", "mapping"])  # type: ignore[arg-type]
    assert excinfo.value.reason_code == "MALFORMED_CASE"


def test_adversarial_candidate_fields_cannot_flip_the_verdict() -> None:
    # No circular label generation: candidate-supplied decision/reason fields
    # inside the case are ignored; the family rule table is the only truth.
    poisoned: dict[str, object] = {
        "case_id": "case-poisoned",
        "family": "revoked_then_dispatch",
        "observed_decision": "ADMIT",
        "decision": "ADMIT",
        "verdict": "ACCEPT",
        "reason_code": "OK",
        "payload": {"family": "revoked_then_dispatch", "expected": "ADMIT"},
    }
    assert adjudicate(poisoned).outcome == "REJECT"
    assert adjudicate_noninterference(poisoned).basis_cases == "POPETS-CASE-02_RETRY_LEAKAGE"
    # Symmetrically, a clean family cannot be talked into a rejection.
    poisoned_clean = {
        "case_id": "case-poisoned-clean",
        "family": "fresh",
        "observed_decision": "REJECT",
        "verdict": "REJECT",
    }
    assert adjudicate(poisoned_clean).outcome == "ADMIT"


def test_adversarial_evidence_refs_survive_tampering_of_other_fields() -> None:
    case = {
        "case_id": "case-refs",
        "family": "transitive_gap",
        "evidence": [
            {"uri": "research/venue2027/VENUES/popets/RESEARCH_BLUEPRINT.md"},
            "not-a-dict",  # non-dict entries are dropped by the kernel, not fatal
            {"no_uri": True},  # kernel keeps dict entries as their (empty) uri
        ],
    }
    result = adjudicate(case)
    assert result.outcome == "REJECT"
    assert result.evidence_refs == (
        "research/venue2027/VENUES/popets/RESEARCH_BLUEPRINT.md",
        "",
    )


def test_adversarial_no_indeterminate_coercion_into_safe_verdict() -> None:
    # INDETERMINATE is first-class: it is neither ADMIT nor REJECT, and the
    # noninterference verdict marks it pending adjudication rather than
    # counting it as a safe rejection or a completion (false-zero ban).
    for family in (None, "", "unmodelled"):
        case = {"case_id": "case-ind", "family": family}
        result = adjudicate(case)
        assert result.outcome == "INDETERMINATE"
        assert result.outcome not in ("ADMIT", "REJECT")
