"""Tests for DIMVA-oracle — independent campaign-truth reference oracle.

Positive controls prove the oracle delegates to the shared kernel and returns
the pre-registered DIMVA detection matrix deterministically and JSON-
serializably:

- ``benign_session``         -> ``REJECT`` ("not an attack")
- ``low_and_slow``           -> ``ADMIT`` ("is a probing attack")
- ``cross_tool_obfuscation`` -> ``ADMIT`` ("is a probing attack")
- ``burst_probe``            -> ``ADMIT`` ("is a probing attack")
- unknown family             -> ``INDETERMINATE``

Label-semantics controls prove and DOCUMENT the detection-venue inversion:
for DIMVA, ``ADMIT`` means the campaign IS malicious (it is admitted into the
attack-campaign class, oracle truth label ``ATTACK``) and ``REJECT`` means
"not an attack" (benign session, truth label ``BENIGN``). This is deliberately
inverted relative to the detector arms' harness vocabulary (where a DETECT
alarm is a REJECT outcome); the tests assert the frozen
:data:`~evaluation.venue2027.dimva.independent_oracle.LABEL_SEMANTICS` prose,
the ``CAMPAIGN_TRUTH_LABELS`` mapping and the full outcome matrix so the
semantics cannot silently drift.

Adversarial controls prove independence and fail-closed semantics:

- ``verify_independence`` accepts the clean oracle source but refuses any
  source variant importing the candidate detector module
  (``evaluation.venue2027.dimva.baselines`` / any ``baselines`` module) with
  ``CANDIDATE_IMPORT`` — plain import, from-import, aliased, dotted, relative,
  tampered-live-file and an on-disk *rogue oracle* form — and flags
  unresolvable dynamic imports.
- Candidate-supplied decision fields inside a case cannot flip the verdict
  (no circular label generation): ground truth comes only from the frozen
  family rule table.
- Undeclared/unmodelled families, nested-payload families and missing case
  ids fail closed with stable kernel reason codes; ``INDETERMINATE`` is
  retained (truth label ``PENDING_ADJUDICATION``), never coerced.

The test module imports only the oracle and the shared kernel (independent-
oracle rule): no candidate baseline import, no DB, no network, no clock.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from evaluation.venue2027._shared import oracle_kernel
from evaluation.venue2027._shared.oracle_kernel import OracleError
from evaluation.venue2027.dimva import independent_oracle as oracle
from evaluation.venue2027.dimva.independent_oracle import (
    CAMPAIGN_TRUTH_LABELS,
    DIMVA_DETECTION_RULES,
    LABEL_SEMANTICS,
    ORACLE_ID,
    REGISTERED_FAMILIES,
    adjudicate,
    campaign_truth,
    campaign_truth_label,
    run_self_checks,
    scan_for_candidate_imports,
    self_scan,
    verify_independence,
)

# ---------------------------------------------------------------------------
# Positive controls — pre-registered DIMVA detection matrix
# ---------------------------------------------------------------------------


def test_positive_benign_session_rejects_from_attack_class() -> None:
    result = adjudicate(
        {
            "case_id": "DIMVA-CASE-01",
            "family": "benign_session",
            "evidence": [{"uri": "research/venue2027/VENUES/dimva/CASE_MATRIX.md"}],
        }
    )
    assert result.outcome == "REJECT"  # "not an attack"
    assert result.case_id == "DIMVA-CASE-01"
    assert result.oracle_id == ORACLE_ID == "dimva-campaign-truth-reference"
    assert result.reason_code == "RULE_BENIGN_SESSION"
    assert result.evidence_refs == ("research/venue2027/VENUES/dimva/CASE_MATRIX.md",)
    assert result.to_dict()["kernel_version"] == oracle_kernel.ORACLE_KERNEL_VERSION


@pytest.mark.parametrize(
    ("family", "expected_outcome", "expected_reason"),
    [
        ("benign_session", "REJECT", "RULE_BENIGN_SESSION"),
        ("low_and_slow", "ADMIT", "RULE_LOW_AND_SLOW"),
        ("cross_tool_obfuscation", "ADMIT", "RULE_CROSS_TOOL_OBFUSCATION"),
        ("burst_probe", "ADMIT", "RULE_BURST_PROBE"),
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
    result = adjudicate({"case_id": "case-nested", "payload": {"family": "burst_probe"}})
    assert result.outcome == "ADMIT"
    assert result.reason_code == "RULE_BURST_PROBE"


def test_positive_rule_table_covers_exactly_the_registered_families() -> None:
    assert set(DIMVA_DETECTION_RULES) == set(REGISTERED_FAMILIES)
    assert set(DIMVA_DETECTION_RULES) == {
        "benign_session",
        "low_and_slow",
        "cross_tool_obfuscation",
        "burst_probe",
    }


def test_positive_deterministic_and_json_serializable() -> None:
    case = {"case_id": "case-stable", "family": "low_and_slow", "evidence": []}
    first, second = adjudicate(case), adjudicate(case)
    assert first == second
    payload = json.dumps(first.to_dict(), sort_keys=True)
    assert isinstance(json.loads(payload), dict)


def test_positive_self_checks_match_preregistered_matrix() -> None:
    results = run_self_checks()
    assert [r.outcome for r in results] == [
        "REJECT",
        "ADMIT",
        "ADMIT",
        "ADMIT",
        "INDETERMINATE",
    ]


def test_positive_oracle_matches_manual_canonical_history() -> None:
    # Sentinel parity: the oracle's matrix equals the manually adjudicated
    # canonical history from the CASE_MATRIX (DIMVA-CASE-01 benign;
    # CASE-02/03/05 attack shapes mapped onto the registered families).
    canonical = {
        "benign_session": "REJECT",  # DIMVA-CASE-01 / CASE-04: not an attack
        "low_and_slow": "ADMIT",  # DIMVA-CASE-03: probing attack
        "cross_tool_obfuscation": "ADMIT",  # purpose-hopping / renamed tools
        "burst_probe": "ADMIT",  # DIMVA-CASE-05 pacing family
    }
    observed = {
        family: adjudicate({"case_id": f"parity-{family}", "family": family}).outcome
        for family in canonical
    }
    assert observed == canonical


# ---------------------------------------------------------------------------
# Label semantics — detection venue: ADMIT means "IS a probing attack"
# ---------------------------------------------------------------------------


def test_label_semantics_documented_and_frozen() -> None:
    # The documented semantics exist, state the detection-venue inversion
    # explicitly, and match the implemented table.
    assert "ADMIT" in LABEL_SEMANTICS and "probing attack" in LABEL_SEMANTICS
    assert "REJECT" in LABEL_SEMANTICS and "not an attack" in LABEL_SEMANTICS
    assert DIMVA_DETECTION_RULES["benign_session"] == "REJECT"
    assert DIMVA_DETECTION_RULES["low_and_slow"] == "ADMIT"
    assert DIMVA_DETECTION_RULES["cross_tool_obfuscation"] == "ADMIT"
    assert DIMVA_DETECTION_RULES["burst_probe"] == "ADMIT"


def test_label_semantics_admit_means_campaign_is_malicious() -> None:
    # ADMIT is admission INTO the attack-campaign class (truth label ATTACK),
    # not "the detector lets it pass". REJECT is "not an attack" (BENIGN).
    attack = adjudicate({"case_id": "sem-attack", "family": "low_and_slow"})
    assert attack.outcome == "ADMIT"
    assert campaign_truth(attack) == "ATTACK"
    benign = adjudicate({"case_id": "sem-benign", "family": "benign_session"})
    assert benign.outcome == "REJECT"
    assert campaign_truth(benign) == "BENIGN"


def test_label_semantics_full_mapping_is_frozen() -> None:
    assert dict(CAMPAIGN_TRUTH_LABELS) == {
        "ADMIT": "ATTACK",
        "REJECT": "BENIGN",
        "INDETERMINATE": "PENDING_ADJUDICATION",
    }
    assert campaign_truth_label("ADMIT") == "ATTACK"
    assert campaign_truth_label("REJECT") == "BENIGN"
    assert campaign_truth_label("INDETERMINATE") == "PENDING_ADJUDICATION"
    with pytest.raises(OracleError) as excinfo:
        campaign_truth_label("NOT_RUN_EXTERNAL")
    assert excinfo.value.reason_code == "UNKNOWN_OUTCOME"


def test_label_semantics_inverted_relative_to_detector_arm_vocabulary() -> None:
    # The detector arms record a DETECT alarm as harness outcome REJECT
    # (baselines.run_baseline). The oracle's axis is the truth axis and is
    # deliberately inverted: a true attack campaign is oracle-ADMIT. This test
    # pins the inversion so nobody "fixes" the oracle to match the harness.
    assert DIMVA_DETECTION_RULES["burst_probe"] == "ADMIT"  # attack -> oracle ADMIT
    assert DIMVA_DETECTION_RULES["benign_session"] == "REJECT"  # benign -> oracle REJECT
    assert "never a detector arm" in LABEL_SEMANTICS or "not what a detector" in LABEL_SEMANTICS


# ---------------------------------------------------------------------------
# Adversarial controls — independence from candidate baselines
# ---------------------------------------------------------------------------


def test_adversarial_clean_source_passes_independence() -> None:
    verify_independence()  # live module source: must not raise
    assert scan_for_candidate_imports() == frozenset()


@pytest.mark.parametrize(
    "snippet",
    [
        "import evaluation.venue2027.dimva.baselines",
        "import evaluation.venue2027.dimva.baselines as b",
        "from evaluation.venue2027.dimva.baselines import run_baseline",
        "from evaluation.venue2027.dimva import baselines",
        "import baselines",
        "from baselines import run_baseline",
        "import dimva.baselines",
        "from evaluation.venue2027.acns import baselines",
    ],
)
def test_adversarial_candidate_import_refused(snippet: str) -> None:
    with pytest.raises(OracleError) as excinfo:
        verify_independence(f'"""doc"""\n{snippet}\n')
    assert excinfo.value.reason_code == "CANDIDATE_IMPORT"
    assert "baselines" in excinfo.value.detail


def test_adversarial_similar_names_do_not_trip_the_scan() -> None:
    # Exact component matching: modules whose names merely *contain* a
    # candidate basename are not candidate imports.
    snippet = (
        "import ast\n"
        "import my_baselines_tests\n"
        "from evaluation.venue2027.dimva.independent_oracle import adjudicate\n"
        "from evaluation.venue2027._shared import oracle_kernel\n"
    )
    assert scan_for_candidate_imports(snippet) == frozenset()
    verify_independence(snippet)


def test_adversarial_dynamic_import_flagged() -> None:
    dynamic = 'm = __import__("evaluation.venue2027.dimva.baselines")\n'
    assert scan_for_candidate_imports(dynamic) == frozenset({"__dynamic__"})
    with pytest.raises(OracleError):
        verify_independence(dynamic)
    importlib_snippet = (
        "import importlib\n" 'm = importlib.import_module("evaluation.venue2027.dimva.baselines")\n'
    )
    assert scan_for_candidate_imports(importlib_snippet) == frozenset({"__dynamic__"})
    with pytest.raises(OracleError):
        verify_independence(importlib_snippet)


def test_adversarial_tampered_live_source_refused() -> None:
    # Tamper control: appending one candidate import to the real source must
    # flip the verdict (the scan really reads the source it is given).
    source = oracle.__file__
    assert source is not None
    live = Path(source).read_text(encoding="utf-8")
    with pytest.raises(OracleError) as excinfo:
        verify_independence(live + "\nimport evaluation.venue2027.dimva.baselines\n")
    assert excinfo.value.reason_code == "CANDIDATE_IMPORT"


def test_adversarial_temp_rogue_oracle_refused(tmp_path: Path) -> None:
    # A rogue "independent oracle" written to a temp file that imports the
    # candidate detector module is refused by verify_independence pointing at
    # the file (source-level property, not a property of the live module).
    rogue = tmp_path / "rogue_independent_oracle.py"
    rogue.write_text(
        textwrap.dedent(
            """
            '''Rogue oracle pretending to be independent.'''
            from evaluation.venue2027.dimva.baselines import run_baseline

            def adjudicate(case):
                return run_baseline("B3", case, None)
            """
        ),
        encoding="utf-8",
    )
    with pytest.raises(OracleError) as excinfo:
        verify_independence(oracle_path=str(rogue))
    assert excinfo.value.reason_code == "CANDIDATE_IMPORT"
    assert "baselines" in excinfo.value.detail


def test_adversarial_kernel_ast_guard_also_clean() -> None:
    # The audited kernel guard accepts this oracle's live file as well.
    source_path = oracle.__file__
    assert source_path is not None
    oracle_kernel.assert_oracle_independence(source_path, ("dimva.baselines", "baselines"))


def test_adversarial_self_scan_reports_clean_independence() -> None:
    summary = self_scan()
    assert summary["oracle_id"] == ORACLE_ID
    assert summary["independence"] == "CLEAN"
    assert summary["llm_calls"] == 0 and summary["model_imports"] == 0
    json.dumps(summary, sort_keys=True)  # audit summary is JSON-serializable


# ---------------------------------------------------------------------------
# Adversarial controls — fail-closed adjudication semantics
# ---------------------------------------------------------------------------


def test_adversarial_unmodelled_family_is_indeterminate_not_reject() -> None:
    result = adjudicate({"case_id": "case-unknown", "family": "novel_campaign_family"})
    assert result.outcome == "INDETERMINATE"
    assert result.reason_code == "UNMODELLED_FAMILY"
    assert campaign_truth(result) == "PENDING_ADJUDICATION"


def test_adversarial_missing_family_is_indeterminate() -> None:
    result = adjudicate({"case_id": "case-nofamily"})
    assert result.outcome == "INDETERMINATE"
    assert result.reason_code == "NO_FAMILY_DECLARED"
    assert campaign_truth(result) == "PENDING_ADJUDICATION"


def test_adversarial_missing_case_id_fails_closed() -> None:
    with pytest.raises(OracleError) as excinfo:
        adjudicate({"family": "low_and_slow"})
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
        "family": "benign_session",
        "observed_decision": "DETECT",
        "decision": "REJECT",
        "verdict": "ATTACK",
        "reason_code": "CAMPAIGN_LINKAGE_PROBING",
        "score": 999.0,
        "payload": {"family": "benign_session", "expected": "ATTACK"},
    }
    result = adjudicate(poisoned)
    assert result.outcome == "REJECT"  # still "not an attack"
    assert campaign_truth(result) == "BENIGN"
    # Symmetrically, a true campaign cannot be talked out of the attack class.
    poisoned_attack = {
        "case_id": "case-poisoned-clean",
        "family": "cross_tool_obfuscation",
        "observed_decision": "NO_DETECT",
        "verdict": "BENIGN",
        "score": 0.0,
    }
    result = adjudicate(poisoned_attack)
    assert result.outcome == "ADMIT"  # still "is a probing attack"
    assert campaign_truth(result) == "ATTACK"


def test_adversarial_evidence_refs_survive_tampering_of_other_fields() -> None:
    case = {
        "case_id": "case-refs",
        "family": "burst_probe",
        "evidence": [
            {"uri": "research/venue2027/VENUES/dimva/CASE_MATRIX.md"},
            "not-a-dict",  # non-dict entries are dropped by the kernel, not fatal
            {"no_uri": True},  # kernel keeps dict entries as their (empty) uri
        ],
    }
    result = adjudicate(case)
    assert result.outcome == "ADMIT"
    assert result.evidence_refs == (
        "research/venue2027/VENUES/dimva/CASE_MATRIX.md",
        "",
    )


def test_adversarial_no_indeterminate_coercion_into_safe_verdict() -> None:
    # INDETERMINATE is first-class: it is neither ADMIT nor REJECT, and on a
    # detection venue it must NOT be silently downgraded to "not an attack".
    for family in (None, "", "unmodelled"):
        case = {"case_id": "case-ind", "family": family}
        result = adjudicate(case)
        assert result.outcome == "INDETERMINATE"
        assert result.outcome not in ("ADMIT", "REJECT")
        assert campaign_truth(result) == "PENDING_ADJUDICATION"
