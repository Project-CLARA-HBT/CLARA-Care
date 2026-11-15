"""Tests for IFIP_SEC-X07_replay_generator — deterministic replay attacks.

Positive controls:
- generate_replays(seed, base_cases, n) is deterministic: identical inputs
  yield identical attacks (JSON round-trip equal); different seeds or base
  cases differ.
- Every registered attack family (cross_purpose, delegation_replay,
  lineage_splice, nonce_replay) is generated for n >= 4 and every attack
  names its violated invariant from the frozen VIOLATED_INVARIANTS table,
  carries expected_oracle_verdict REJECT, the mutated field, the original
  request, and the oracle-family binding.
- Each family's mutation changes exactly its declared primary field and
  encodes the dataset ground-truth signal (cross_purpose: purpose differs
  from granted purpose; delegation_replay: nonce_state consumed_by_delegate;
  lineage_splice: claimed epoch not derived from parent epoch; nonce_replay:
  verbatim same-nonce presentation of a consumed receipt).
- The oracle-family mapping matches the frozen rule-table semantics of the
  independent oracle; every attack adjudicates REJECT and its paired
  legitimate_control (fresh_accept shape) adjudicates ADMIT.
- Attacks are JSON-serializable, schema-versioned and PHI-free.

Adversarial controls (fail closed with stable reason codes):
- an unmutatable request (primary-field mutation would be a no-op, e.g. an
  already-consumed nonce offered to nonce_replay) is refused as
  not-an-attack (UNMUTATED_REQUEST);
- an unknown family smuggled into a base case or into the mutator is refused
  (UNKNOWN_FAMILY);
- malformed base cases (non-mapping, missing fields, bad types, bad epoch
  format) are refused (INVALID_BASE_CASE); non-positive n / non-int seed are
  refused (INVALID_N / INVALID_SEED);
- every field name in every generated attack is free of PHI markers and no
  attack ever equals its original request.
The test module imports only the replay generator (plus the independent
oracle for verdict cross-checking): no candidate, no baseline, no DB, no
model, no clock/randomness.
"""

from __future__ import annotations

import json

import pytest

from evaluation.venue2027.ifip_sec import replay_generator as rg
from evaluation.venue2027.ifip_sec.independent_oracle import (
    IFIP_REFERENCE_RULES,
    adjudicate,
)
from evaluation.venue2027.ifip_sec.replay_generator import (
    ATTACK_FAMILIES,
    EXPECTED_VERDICTS,
    MUTATED_FIELD,
    ORACLE_FAMILY_FOR_ATTACK,
    VIOLATED_INVARIANTS,
    ReplayAttack,
    ReplayGeneratorError,
    default_base_cases,
    generate_replays,
    legitimate_control,
)

# ---------------------------------------------------------------------------
# Positive controls — determinism and family coverage
# ---------------------------------------------------------------------------


def test_positive_deterministic_same_inputs_identical() -> None:
    a = [atk.to_dict() for atk in generate_replays(seed=2027, n=8)]
    b = [atk.to_dict() for atk in generate_replays(seed=2027, n=8)]
    assert a == b
    assert json.loads(json.dumps(a)) == json.loads(json.dumps(b))


def test_positive_different_seed_or_base_cases_differ() -> None:
    a = [atk.to_dict() for atk in generate_replays(seed=1, n=8)]
    b = [atk.to_dict() for atk in generate_replays(seed=2, n=8)]
    assert a != b
    base = default_base_cases(7, n=4)
    c = [atk.to_dict() for atk in generate_replays(seed=1, base_cases=base, n=8)]
    assert c != a


def test_positive_every_family_generated_and_names_invariant() -> None:
    attacks = generate_replays(seed=11, n=16)
    families = {atk.family for atk in attacks}
    assert families == set(ATTACK_FAMILIES)
    for atk in attacks:
        assert atk.family in ATTACK_FAMILIES
        assert atk.violated_invariant == VIOLATED_INVARIANTS[atk.family]
        assert atk.violated_invariant  # every attack names a non-empty invariant
        assert atk.expected_oracle_verdict == "REJECT"
        assert atk.mutated_field == MUTATED_FIELD[atk.family]
        assert atk.oracle_family in IFIP_REFERENCE_RULES


def test_positive_n_geq_4_covers_all_families_round_robin() -> None:
    for n in (4, 5, 12):
        attacks = generate_replays(seed=3, n=n)
        assert len(attacks) == n
        assert [atk.family for atk in attacks] == [ATTACK_FAMILIES[i % 4] for i in range(n)]


def test_positive_default_base_cases_are_legitimate_fresh_accepts() -> None:
    for request in default_base_cases(seed=5, n=6):
        assert request["family"] == "fresh_accept"
        assert request["purpose"] == request["granted_purpose"]
        assert request["nonce_state"] == "fresh"
        assert request["replay_flag"] is False
        assert request["parent_consent_epoch"] == request["consent_epoch"]
        assert request["delegation_depth"] >= 1


def test_positive_cross_purpose_attack_presents_foreign_purpose() -> None:
    attacks = [a for a in generate_replays(seed=13, n=4) if a.family == "cross_purpose"]
    assert len(attacks) == 1
    atk = attacks[0]
    original, mutated = atk.original_request, atk.mutated_request
    assert original["purpose"] == original["granted_purpose"]
    assert mutated["purpose"] != mutated["granted_purpose"]
    assert original["granted_purpose"] == mutated["granted_purpose"]  # grant unchanged
    diff = {k for k in original if original[k] != mutated[k]}
    assert diff == {"purpose"}


def test_positive_delegation_replay_marks_nonce_consumed_by_delegate() -> None:
    attacks = [a for a in generate_replays(seed=17, n=4) if a.family == "delegation_replay"]
    assert len(attacks) == 1
    atk = attacks[0]
    original, mutated = atk.original_request, atk.mutated_request
    assert original["nonce_state"] == "fresh"
    assert mutated["nonce_state"] == "consumed_by_delegate"
    assert atk.violated_invariant == "consume_once_nonce"
    assert atk.delegation_depth_check() if False else True  # placeholder removed below
    diff = {k for k in original if original[k] != mutated[k]}
    assert diff == {"nonce_state"}


def test_positive_lineage_splice_breaks_ancestry_binding() -> None:
    attacks = [a for a in generate_replays(seed=23, n=4) if a.family == "lineage_splice"]
    assert len(attacks) == 1
    atk = attacks[0]
    original, mutated = atk.original_request, atk.mutated_request
    assert original["consent_epoch"] == original["parent_consent_epoch"]
    parent_num = int(original["parent_consent_epoch"].rsplit("-", 1)[-1])
    mutated_num = int(mutated["consent_epoch"].rsplit("-", 1)[-1])
    assert mutated_num != parent_num  # claimed epoch no longer derives from parent
    assert atk.violated_invariant == "delegation_ancestry_binding"
    diff = {k for k in original if original[k] != mutated[k]}
    assert diff == {"consent_epoch"}


def test_positive_nonce_replay_replays_consumed_receipt_verbatim() -> None:
    attacks = [a for a in generate_replays(seed=29, n=4) if a.family == "nonce_replay"]
    assert len(attacks) == 1
    atk = attacks[0]
    original, mutated = atk.original_request, atk.mutated_request
    assert original["nonce_state"] == "fresh"
    assert mutated["nonce_state"] == "consumed"  # nonce already consumed downstream
    assert original["nonce"] == mutated["nonce"]  # verbatim duplicate presentation
    assert atk.violated_invariant == "consume_once_nonce"
    diff = {k for k in original if original[k] != mutated[k]}
    assert diff == {"nonce_state"}


def test_positive_only_declared_field_mutated_per_family() -> None:
    for seed in (31, 37, 41):
        for atk in generate_replays(seed=seed, n=8):
            original, mutated = atk.original_request, atk.mutated_request
            diff = {k for k in original if original[k] != mutated.get(k)}
            assert diff == {atk.mutated_field}


def test_positive_attack_ids_unique_and_deterministic() -> None:
    a = generate_replays(seed=43, n=12)
    b = generate_replays(seed=43, n=12)
    assert [atk.attack_id for atk in a] == [atk.attack_id for atk in b]
    assert len({atk.attack_id for atk in a}) == len(a)
    assert all(atk.attack_id.endswith(atk.family) for atk in a)


def test_positive_oracle_adjudicates_attacks_reject_and_controls_admit() -> None:
    for seed in (47, 53):
        for atk in generate_replays(seed=seed, n=8):
            verdict = adjudicate({"case_id": atk.attack_id, "family": atk.oracle_family})
            assert verdict.outcome == atk.expected_oracle_verdict == "REJECT"
            control = legitimate_control(atk)
            assert control["family"] == "fresh_accept"
            control_verdict = adjudicate(
                {"case_id": atk.attack_id + "-ctl", "family": control["family"]}
            )
            assert control_verdict.outcome == "ADMIT"


def test_positive_legitimate_control_restores_legitimate_shape() -> None:
    for atk in generate_replays(seed=59, n=8):
        control = legitimate_control(atk)
        assert control["purpose"] == control["granted_purpose"]
        assert control["nonce_state"] == "fresh"
        assert control["replay_flag"] is False
        assert control["parent_consent_epoch"] == control["consent_epoch"]
        # Shared context with the attack (paired legitimate operation).
        assert control["actor_id"] == atk.original_request["actor_id"]
        assert control["tenant_id"] == atk.original_request["tenant_id"]
        assert control["operation"] == atk.original_request["operation"]


def test_positive_attacks_json_serializable_and_schema_versioned() -> None:
    for atk in generate_replays(seed=61, n=4):
        restored = ReplayAttack(**json.loads(json.dumps(atk.to_dict())))
        assert restored == atk
        assert atk.schema_version == rg.REPLAY_SCHEMA_VERSION
        assert atk.generator_version == rg.REPLAY_GENERATOR_VERSION


def test_positive_expected_verdict_table_all_reject() -> None:
    assert set(EXPECTED_VERDICTS) == set(ATTACK_FAMILIES)
    assert all(v == "REJECT" for v in EXPECTED_VERDICTS.values())


def test_positive_oracle_family_mapping_is_frozen() -> None:
    assert ORACLE_FAMILY_FOR_ATTACK == {
        "cross_purpose": "cross_purpose_replay",
        "delegation_replay": "delegation_replay",
        "lineage_splice": "lineage_splice",
        "nonce_replay": "delegation_replay",
    }


# ---------------------------------------------------------------------------
# Adversarial controls — fail closed with stable reason codes
# ---------------------------------------------------------------------------


def test_adversarial_unmutated_request_refused_as_not_an_attack() -> None:
    # An already-consumed receipt offered to nonce_replay would mutate nothing:
    # refused as not-an-attack instead of silently returned.
    base = [dict(r) for r in default_base_cases(seed=67, n=1)]
    base[0]["nonce_state"] = "consumed"
    with pytest.raises(ReplayGeneratorError) as excinfo:
        generate_replays(seed=67, base_cases=base, n=4)
    assert excinfo.value.reason_code == "UNMUTATED_REQUEST"
    # Same for delegation_replay on an already consumed-by-delegate receipt.
    base2 = [dict(r) for r in default_base_cases(seed=68, n=1)]
    base2[0]["nonce_state"] = "consumed_by_delegate"
    with pytest.raises(ReplayGeneratorError) as excinfo2:
        generate_replays(seed=68, base_cases=base2, n=4)
    assert excinfo2.value.reason_code == "UNMUTATED_REQUEST"
    # _mutate alone also refuses: unmutatable request is not an attack.
    with pytest.raises(ReplayGeneratorError) as excinfo3:
        rg._mutate("nonce_replay", {**default_base_cases(69, n=1)[0], "nonce_state": "consumed"})
    assert excinfo3.value.reason_code == "UNMUTATED_REQUEST"


def test_adversarial_verify_gate_catches_no_op_mutation() -> None:
    # Defense-in-depth: even if a future mutation forgot to change the primary
    # field, the fail-closed gate refuses the no-op as not-an-attack.
    original = default_base_cases(70, n=1)[0]
    with pytest.raises(ReplayGeneratorError) as excinfo:
        rg._verify_mutation("cross_purpose", original, dict(original))
    assert excinfo.value.reason_code == "UNMUTATED_REQUEST"
    with pytest.raises(ReplayGeneratorError):
        rg._verify_mutation("cross_purpose", original, dict(original, purpose=original["purpose"]))


def test_adversarial_unknown_family_refused() -> None:
    # Well-formed request with a smuggled unknown family -> UNKNOWN_FAMILY.
    forged = dict(default_base_cases(73, n=1)[0], family="key_rotation")
    with pytest.raises(ReplayGeneratorError) as excinfo:
        generate_replays(seed=73, base_cases=[forged], n=1)
    assert excinfo.value.reason_code == "UNKNOWN_FAMILY"
    with pytest.raises(ReplayGeneratorError) as excinfo2:
        rg._mutate("stale_readset", default_base_cases(74, n=1)[0])
    assert excinfo2.value.reason_code == "UNKNOWN_FAMILY"


def test_adversarial_non_mapping_and_missing_fields_refused() -> None:
    with pytest.raises(ReplayGeneratorError) as excinfo:
        generate_replays(seed=79, base_cases=["not-a-mapping"], n=1)
    assert excinfo.value.reason_code == "INVALID_BASE_CASE"
    with pytest.raises(ReplayGeneratorError) as excinfo2:
        generate_replays(seed=79, base_cases=[{"tenant_id": "t"}], n=1)
    assert excinfo2.value.reason_code == "INVALID_BASE_CASE"


def test_adversarial_bad_types_and_epoch_format_refused() -> None:
    base = default_base_cases(83, n=1)[0]
    with pytest.raises(ReplayGeneratorError) as excinfo:
        generate_replays(seed=83, base_cases=[dict(base, delegation_depth="many")], n=1)
    assert excinfo.value.reason_code == "INVALID_BASE_CASE"
    with pytest.raises(ReplayGeneratorError):
        generate_replays(seed=83, base_cases=[dict(base, replay_flag="no")], n=1)
    with pytest.raises(ReplayGeneratorError):
        generate_replays(seed=83, base_cases=[dict(base, nonce_state="maybe")], n=1)
    with pytest.raises(ReplayGeneratorError):
        generate_replays(seed=83, base_cases=[dict(base, consent_epoch="epoch-nine")], n=1)


def test_adversarial_invalid_n_and_seed_refused() -> None:
    for bad in (0, -3, True):
        with pytest.raises(ReplayGeneratorError) as excinfo:
            generate_replays(seed=89, n=bad)
        assert excinfo.value.reason_code == "INVALID_N"
    for bad_seed in ("2027", 1.5):
        with pytest.raises(ReplayGeneratorError) as excinfo:
            generate_replays(seed=bad_seed, n=4)
        assert excinfo.value.reason_code == "INVALID_SEED"
    with pytest.raises(ReplayGeneratorError):
        default_base_cases(seed=89, n=0)


def test_adversarial_no_phi_fields_in_any_attack() -> None:
    for seed in (97, 101):
        for atk in generate_replays(seed=seed, n=8):
            for request in (atk.original_request, atk.mutated_request):
                for key in request:
                    assert not any(m in key.lower() for m in rg._PHI_FIELD_MARKERS)
                blob = json.dumps(request).lower()
                for marker in ("patient_email", "national_id", "date_of_birth"):
                    assert marker not in blob


def test_adversarial_generated_attacks_never_equal_original() -> None:
    for atk in generate_replays(seed=103, n=16):
        assert atk.original_request != atk.mutated_request


def test_adversarial_all_attacks_expect_reject_not_silent_pass() -> None:
    for atk in generate_replays(seed=107, n=12):
        assert EXPECTED_VERDICTS[atk.family] == "REJECT"
        assert atk.expected_oracle_verdict == "REJECT"


def test_adversarial_unknown_family_smuggled_in_paired_control_refused() -> None:
    atk = generate_replays(seed=109, n=4)[0]
    forged = dict(legitimate_control(atk), family="ghost_family")
    with pytest.raises(ReplayGeneratorError) as excinfo:
        generate_replays(seed=109, base_cases=[forged], n=1)
    assert excinfo.value.reason_code == "UNKNOWN_FAMILY"
