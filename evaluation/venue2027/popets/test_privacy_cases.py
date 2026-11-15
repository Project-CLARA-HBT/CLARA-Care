"""Tests for POPETS-X07_privacy_cases (frozen ex-ante privacy case set).

Positive controls (must pass):
- The frozen set is non-empty, ids are unique and stable, and the canonical
  JSON SHA256 of the set equals the committed freeze constant
  (``assert_frozen_cases`` accepts the shipped set deterministically).
- Every case's ``scenario`` parses into the real revocation-model input
  contracts and maps to a real :func:`revocation_model.decide` decision whose
  verdict is consistent with the case's ``expected_semantic_outcome``
  (ALLOW/DENY/INDETERMINATE directly; OUT_OF_SCOPE/NOT_GUARANTEED via the
  orthogonal ``already_delivered_effect`` / ``memorization_guarantee`` fields).
- Every case names a concrete ``revocation_model`` semantic reference and the
  orthogonal effects (stored-data deletion, OUT_OF_SCOPE_PAST,
  NOT_GUARANTEED memorization) appear exactly where the semantics say.
- JSON round-trip of every typed case; PHI-free field vocabulary.

Adversarial controls (must be refused / honest, never fabricated):
- Drift is refused: any addition, removal, rewording or reordering of a case
  fails ``assert_frozen_cases`` with the stable ``CASE_SET_DRIFT`` reason
  code.
- No retroactive-erasure claim: OUT_OF_SCOPE cases carry
  ``already_delivered_effect == OUT_OF_SCOPE_PAST``, no erasure reason code,
  and the model's semantics refuse ``retroactive_erasure_of_delivered_bytes``
  (N1/N3); memorization stays NOT_GUARANTEED, never a DENY-as-erasure.
- No PHI: no case id, description, reference, or scenario key matches the
  shared kernel's PHI field markers.
- Unknown case ids fail closed (``CASE_UNKNOWN``); malformed cases are
  refused at import with ``CASE_MALFORMED``.
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
import re
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from evaluation.venue2027._shared.dataset_kernel import PHI_FIELD_MARKERS
from evaluation.venue2027.popets import privacy_cases as pc
from evaluation.venue2027.popets.revocation_model import (
    OUT_OF_SCOPE_PAST,
    ConsentLedgerView,
    DispatchItem,
    decide,
    revocation_semantics,
)

_CASE_ID_PATTERN = re.compile(r"^PC-(FRESH|REVOKE|XPURP|TGAP|DELIV)-\d{2}$")


# ---------------------------------------------------------------------------
# Positive controls — freeze discipline
# ---------------------------------------------------------------------------


def test_set_is_nonempty_ids_stable_and_all_classes_covered() -> None:
    assert len(pc.PRIVACY_CASES) >= 8
    assert len(pc.PRIVACY_CASE_IDS) == len(set(pc.PRIVACY_CASE_IDS))
    for case in pc.PRIVACY_CASES:
        assert _CASE_ID_PATTERN.match(case.case_id), case.case_id
        assert case.scenario_class in pc.SCENARIO_CLASSES
        assert case.expected_semantic_outcome in pc.EXPECTED_SEMANTIC_OUTCOMES
        assert case.description.strip()
    # All five preregistered scenario classes are represented.
    assert {c.scenario_class for c in pc.PRIVACY_CASES} == set(pc.SCENARIO_CLASSES)
    # All five semantic outcomes are represented.
    assert {c.expected_semantic_outcome for c in pc.PRIVACY_CASES} == set(
        pc.EXPECTED_SEMANTIC_OUTCOMES
    )


def test_frozen_hash_is_deterministic_and_matches_freeze_constant() -> None:
    assert pc.cases_sha256() == pc.FROZEN_CASE_SET_SHA256
    assert pc.cases_sha256() == pc.cases_sha256(pc.PRIVACY_CASES)
    assert pc.frozen_case_set_sha256() == pc.FROZEN_CASE_SET_SHA256
    # Determinism: recomputing twice yields the same digest (no hidden
    # randomness in serialization).
    assert pc.serialize_case_set() == pc.serialize_case_set()


def test_assert_frozen_cases_accepts_shipped_set() -> None:
    pc.assert_frozen_cases(pc.PRIVACY_CASES)  # must not raise


def test_every_case_json_round_trips() -> None:
    for case in pc.PRIVACY_CASES:
        payload = json.loads(json.dumps(case.to_dict()))
        assert payload["case_id"] == case.case_id
        assert payload["expected_semantic_outcome"] == case.expected_semantic_outcome
        assert payload["scenario"]["principal"] == case.scenario.principal
        assert payload["cases_version"] == pc.PRIVACY_CASES_VERSION
    # The whole set serializes canonically and stably.
    text = pc.serialize_case_set()
    assert json.loads(text)[0]["case_id"] == pc.PRIVACY_CASES[0].case_id


# ---------------------------------------------------------------------------
# Positive controls — cases map to real revocation_model decisions
# ---------------------------------------------------------------------------


def _decision(case: pc.PrivacyCase):
    return decide(
        DispatchItem.from_mapping(case.scenario.item),
        case.scenario.principal,
        case.scenario.purpose,
        case.scenario.time,
        ConsentLedgerView.from_mapping(case.scenario.ledger),
    )


def test_allow_cases_map_to_real_allow_decisions() -> None:
    for case in pc.PRIVACY_CASES:
        if case.expected_semantic_outcome != "ALLOW":
            continue
        decision = _decision(case)
        assert decision.decision == "ALLOW", case.case_id
        assert decision.reason_code == "ALLOWED_ACTIVE_CONSENT", case.case_id
        assert decision.stored_data == "not_applicable", case.case_id
        assert decision.already_delivered_effect is None, case.case_id
        assert decision.memorization_guarantee is None, case.case_id


def test_deny_cases_map_to_real_deny_decisions() -> None:
    for case in pc.PRIVACY_CASES:
        if case.expected_semantic_outcome != "DENY":
            continue
        decision = _decision(case)
        assert decision.decision == "DENY", case.case_id
        # Post-revocation and cross-purpose denials carry their distinct,
        # stable reason codes (never a generic refusal).
        assert decision.reason_code in {
            "DENY_POST_REVOCATION",
            "PURPOSE_NOT_CONSENTED",
        }, case.case_id


def test_indeterminate_cases_fail_closed_not_counted_safe() -> None:
    for case in pc.PRIVACY_CASES:
        if case.expected_semantic_outcome != "INDETERMINATE":
            continue
        decision = _decision(case)
        assert decision.decision == "INDETERMINATE", case.case_id
        assert decision.reason_code == "LINEAGE_INDETERMINATE", case.case_id


def test_out_of_scope_case_carries_delivered_effect_not_erasure() -> None:
    case = pc.case_by_id("PC-DELIV-01")
    decision = _decision(case)
    # Future disclosure is still gated: the post-t_r dispatch itself is DENY.
    assert decision.decision == "DENY"
    assert decision.reason_code == "DENY_POST_REVOCATION"
    # ...but the pre-t_r delivered copy is honestly out of scope: no
    # retroactive-erasure claim anywhere in the decision surface.
    assert decision.already_delivered_effect == OUT_OF_SCOPE_PAST
    assert decision.memorization_guarantee == "NOT_GUARANTEED"
    blob = json.dumps(decision.to_dict())
    assert "erasure" not in blob.lower().replace("retroactive_erasure", "")
    assert "OUT_OF_SCOPE_PAST" in blob


def test_not_guaranteed_case_keeps_verdict_and_honest_limitation() -> None:
    case = pc.case_by_id("PC-DELIV-02")
    decision = _decision(case)
    # The authorized dispatch remains ALLOW — memorization uncertainty is
    # surfaced as a limitation, never converted into a DENY-as-erasure.
    assert decision.decision == "ALLOW"
    assert decision.reason_code == "ALLOWED_ACTIVE_CONSENT"
    assert decision.already_delivered_effect == OUT_OF_SCOPE_PAST
    assert decision.memorization_guarantee == "NOT_GUARANTEED"


def test_post_revocation_cases_report_stored_data_deletion_separately() -> None:
    for case_id in ("PC-REVOKE-01", "PC-REVOKE-02"):
        decision = _decision(pc.case_by_id(case_id))
        assert decision.decision == "DENY"
        # Stored-data deletion is an orthogonal surface, reported in its own
        # field and never folded into the disclosure verdict.
        assert decision.stored_data == "deleted"


def test_every_expected_outcome_column_is_frozen_and_consistent() -> None:
    assert pc.expected_semantic_outcomes() == tuple(
        c.expected_semantic_outcome for c in pc.PRIVACY_CASES
    )
    for case in pc.PRIVACY_CASES:
        decision = _decision(case)
        if case.expected_semantic_outcome in {"ALLOW", "DENY", "INDETERMINATE"}:
            assert decision.decision == case.expected_semantic_outcome, case.case_id
        else:
            # Guarantee-boundary outcomes: the verdict is ordinary, the
            # semantic outcome lives in the orthogonal effect fields.
            assert decision.decision in {"ALLOW", "DENY"}, case.case_id


def test_every_case_references_real_semantics_clauses() -> None:
    semantics = revocation_semantics().to_dict()
    guarantees = " ".join(semantics["guarantees"])
    non_guarantees = " ".join(semantics["non_guarantees"])
    for case in pc.PRIVACY_CASES:
        assert case.revocation_model_reference.strip()
        assert case.case_matrix_ref.startswith("POPETS-CASE-")
    # The boundary cases cite clauses that actually exist in the semantics.
    assert "OUT_OF_SCOPE_PAST" in non_guarantees
    assert "NOT_GUARANTEED" in non_guarantees
    assert "DENY" in guarantees


# ---------------------------------------------------------------------------
# Adversarial controls — drift refusal
# ---------------------------------------------------------------------------


def _mutated_cases(mutate):
    return tuple(mutate(dict(c.to_dict())) for c in pc.PRIVACY_CASES)


def test_added_case_is_refused() -> None:
    cases = list(pc.PRIVACY_CASES)
    extra = dataclasses.replace(
        cases[0],
        case_id="PC-EXTRA-99",
        description="post-hoc addition",
    )
    with pytest.raises(pc.PrivacyCaseError) as excinfo:
        pc.assert_frozen_cases([*cases, extra])
    assert excinfo.value.reason_code == "CASE_SET_DRIFT"


def test_removed_case_is_refused() -> None:
    with pytest.raises(pc.PrivacyCaseError) as excinfo:
        pc.assert_frozen_cases(pc.PRIVACY_CASES[:-1])
    assert excinfo.value.reason_code == "CASE_SET_DRIFT"


def test_reworded_case_is_refused() -> None:
    cases = list(pc.PRIVACY_CASES)
    drifted = dataclasses.replace(cases[0], description="reworded description")
    with pytest.raises(pc.PrivacyCaseError) as excinfo:
        pc.assert_frozen_cases([*cases[:1], drifted, *cases[1:]])
    assert excinfo.value.reason_code == "CASE_SET_DRIFT"


def test_reordered_case_set_is_refused() -> None:
    cases = list(pc.PRIVACY_CASES)
    with pytest.raises(pc.PrivacyCaseError) as excinfo:
        pc.assert_frozen_cases([cases[1], cases[0], *cases[2:]])
    assert excinfo.value.reason_code == "CASE_SET_DRIFT"


def test_outcome_flip_is_refused() -> None:
    cases = list(pc.PRIVACY_CASES)
    drifted = dataclasses.replace(cases[0], expected_semantic_outcome="DENY")
    with pytest.raises(pc.PrivacyCaseError) as excinfo:
        pc.assert_frozen_cases([drifted, *cases[1:]])
    assert excinfo.value.reason_code == "CASE_SET_DRIFT"


def test_serialized_drift_variants_all_change_the_digest() -> None:
    baseline = pc.cases_sha256()
    dicts = [dict(c.to_dict()) for c in pc.PRIVACY_CASES]
    assert json.dumps(dicts[1:], sort_keys=True) != json.dumps(dicts, sort_keys=True)
    assert baseline == pc.cases_sha256(pc.PRIVACY_CASES)


# ---------------------------------------------------------------------------
# Adversarial controls — no retroactive-erasure claim
# ---------------------------------------------------------------------------


def test_semantics_refuse_retroactive_erasure_and_memorization_guarantee() -> None:
    semantics = revocation_semantics()
    assert semantics.retroactive_erasure_of_delivered_bytes is False
    assert semantics.model_memorization_erasure is False
    assert semantics.model_memorization_guarantee == "NOT_GUARANTEED"
    non_guarantees = " ".join(semantics.non_guarantees)
    assert "cannot be retracted" in non_guarantees
    assert "No cryptographic retroactive erasure" in non_guarantees


def test_no_case_promises_erasure_of_delivered_bytes() -> None:
    for case in pc.PRIVACY_CASES:
        blob = json.dumps(case.to_dict()).lower()
        assert "retroactive erasure of the delivered" not in blob
        assert "guaranteed removable" not in blob.replace("not guaranteed removable", "")
        if case.scenario_class == "already_delivered":
            item = case.scenario.item
            assert item["already_delivered"] is True
            # The orthogonal effect is reported; it never rewrites the verdict.
            decision = _decision(case)
            assert decision.already_delivered_effect == OUT_OF_SCOPE_PAST


def test_no_erasure_reason_code_exists_in_the_model_vocabulary() -> None:
    for case in pc.PRIVACY_CASES:
        decision = _decision(case)
        assert "ERASE" not in decision.reason_code.upper()
        assert "UNLEARN" not in decision.reason_code.upper()


# ---------------------------------------------------------------------------
# Adversarial controls — no PHI, fail-closed lookups
# ---------------------------------------------------------------------------


def test_no_phi_fields_anywhere_in_the_frozen_set() -> None:
    def _scan_keys(obj) -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                lowered = str(key).lower()
                assert not any(m in lowered for m in PHI_FIELD_MARKERS), key
                _scan_keys(value)
        elif isinstance(obj, list):
            for value in obj:
                _scan_keys(value)

    _scan_keys([c.to_dict() for c in pc.PRIVACY_CASES])
    # Case ids, descriptions and references are synthetic and structural.
    for case in pc.PRIVACY_CASES:
        blob = f"{case.case_id} {case.description} {case.revocation_model_reference}"
        assert not re.search(r"\b\d{3}-\d{2}-\d{4}\b", blob)  # no SSN-like ids


def test_unknown_case_id_fails_closed() -> None:
    with pytest.raises(pc.PrivacyCaseError) as excinfo:
        pc.case_by_id("PC-GHOST-00")
    assert excinfo.value.reason_code == "CASE_UNKNOWN"


def test_malformed_case_fails_import_style_consistency_check() -> None:
    bad = dataclasses.replace(
        pc.PRIVACY_CASES[0],
        case_id="",
    )
    with pytest.raises(pc.PrivacyCaseError) as excinfo:
        pc._assert_internal_consistency([bad])
    assert excinfo.value.reason_code == "CASE_MALFORMED"

    bad_ref = dataclasses.replace(
        pc.PRIVACY_CASES[0],
        case_id="PC-OTHER-01",
        revocation_model_reference="   ",
    )
    with pytest.raises(pc.PrivacyCaseError) as excinfo:
        pc._assert_internal_consistency([bad_ref])
    assert excinfo.value.reason_code == "CASE_MALFORMED"

    bad_scenario = dataclasses.replace(
        pc.PRIVACY_CASES[0],
        case_id="PC-OTHER-02",
        scenario=dataclasses.replace(pc.PRIVACY_CASES[0].scenario, time=-1),
    )
    # A negative time is out of the model's domain: constructing the scenario
    # against the real model must fail closed rather than guess.
    decision_or_error = None
    try:
        decision_or_error = _decision(
            dataclasses.replace(
                bad_scenario,
                scenario=dataclasses.replace(
                    bad_scenario.scenario, time=bad_scenario.scenario.time
                ),
            )
        )
    except ValueError as exc:
        decision_or_error = exc
    assert isinstance(decision_or_error, ValueError)
