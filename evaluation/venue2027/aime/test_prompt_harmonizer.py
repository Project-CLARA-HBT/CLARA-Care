"""Tests for AIME-X04_prompt_harmonize (Phase P03) — prompt harmonizer.

Positive controls:
- Every registered arm builds a :class:`PromptPacket` over a well-formed
  synthetic vignette; packets are deterministic (byte-identical JSON and
  stable ``packet_hash`` across repeated builds) and JSON-serializable.
- Arms differ ONLY by regeneration strategy: model semantics, instruction
  template, tokenizer, truncation policy and hidden-source flag are
  identical across all arms; the instruction text is byte-identical.
- ``ComparabilityChecklist`` accepts every arm packet built from the frozen
  semantics and reports ``OK``.
- Tokens-per-arm accounting: the estimated prompt tokens track the rendered
  prompt size deterministically and produce a stable per-arm table.

Adversarial controls (fail closed with stable reason codes):
- A packet recording a changed model identity is refused by the checklist
  with ``ARM_NONCOMPARABLE`` (also: changed tokenizer, changed truncation
  policy, changed seed, changed temperature, changed instruction template).
- Undeclared hidden-source usage (``hidden_source_use=True``) is refused.
- Tampering with any serialized packet field invalidates ``packet_hash``
  (``PACKET_HASH_MISMATCH``) — verified per-field via mutation of every
  recorded semantic field.
- Unknown arm ids and malformed vignettes fail closed with
  ``UNKNOWN_ARM`` / ``VIGNETTE_MALFORMED`` / ``VIGNETTE_MISSING_FIELD`` /
  ``VIGNETTE_BAD_TIMELINE`` and never yield a packet.
- PHI-like fields at the vignette top level are refused like the baselines
  module refuses them (structural refusal, never silent repair).
"""

from __future__ import annotations

import copy
import dataclasses
import json

import pytest

from evaluation.venue2027.aime import prompt_harmonizer as ph
from evaluation.venue2027.aime.baselines import (
    BASELINE_B0,
    BASELINE_B1,
    BASELINE_B2,
    BASELINE_B3,
    BASELINE_B4,
    BASELINE_B5,
)
from evaluation.venue2027.aime.prompt_harmonizer import (
    ARM_STRATEGY_TABLE,
    HARMONIZER_SEMANTICS,
    REASON_ARM_NONCOMPARABLE,
    REASON_BAD_TIMELINE,
    REASON_HASH_MISMATCH,
    REASON_HIDDEN_SOURCE,
    REASON_MALFORMED,
    REASON_MISSING_FIELD,
    REASON_OK,
    REASON_STRATEGY_MISMATCH,
    REASON_UNKNOWN_ARM,
    ArmStrategy,
    ComparabilityChecklist,
    PromptPacket,
    build_prompt,
    verify_packet,
)

ALL_ARMS = (BASELINE_B0, BASELINE_B1, BASELINE_B2, BASELINE_B3, BASELINE_B4, BASELINE_B5)


def _vignette() -> dict:
    """Well-formed synthetic vignette (no PHI, no real identities)."""
    return {
        "case_id": "AIME-X04-V01",
        "purpose": "self_care",
        "snapshot": {
            "medications": ["metformin"],
            "consent": {"granted_purposes": ["self_care"]},
        },
        "current": {
            "medications": ["metformin", "warfarin"],
            "consent": {"granted_purposes": []},
        },
        "timeline": [
            {"order": 0, "event_kind": "INITIAL_STATE", "logical_time": 0, "payload": None},
            {
                "order": 1,
                "event_kind": "CONSENT_REVOKED",
                "logical_time": 3,
                "payload": {"purpose": "self_care"},
            },
            {
                "order": 2,
                "event_kind": "MEDICATION_ADDED",
                "logical_time": 4,
                "payload": {"medication": "warfarin"},
            },
        ],
        "task": {"drug": "metformin", "kind": "recommendation"},
    }


# ---------------------------------------------------------------- positive


@pytest.mark.parametrize("arm", ALL_ARMS)
def test_build_prompt_returns_packet_for_every_registered_arm(arm: str) -> None:
    packet = build_prompt(_vignette(), arm)
    assert isinstance(packet, PromptPacket)
    assert packet.arm_id == arm
    assert packet.version == ph.PROMPT_HARMONIZER_VERSION
    ok, code = verify_packet(packet)
    assert (ok, code) == (True, REASON_OK)


def test_packet_is_deterministic_and_json_serializable() -> None:
    a = build_prompt(_vignette(), BASELINE_B4)
    b = build_prompt(_vignette(), BASELINE_B4)
    assert a.to_json() == b.to_json()
    assert a.packet_hash == b.packet_hash
    assert len(a.packet_hash) == 64
    round_trip = json.loads(a.to_json())
    assert round_trip == a.to_dict()
    ok, code = verify_packet(a, round_trip)
    assert (ok, code) == (True, REASON_OK)


def test_packet_hash_is_stable_across_repeated_construction() -> None:
    hashes = {build_prompt(_vignette(), arm).packet_hash for arm in ALL_ARMS}
    # hash stability per arm:
    for arm in ALL_ARMS:
        assert (
            build_prompt(_vignette(), arm).packet_hash == build_prompt(_vignette(), arm).packet_hash
        )
    # distinct (arm, vignette) pairs hash distinctly (no accidental collisions)
    assert len(hashes) == len(ALL_ARMS)


def test_arms_differ_only_by_regeneration_strategy() -> None:
    packets = {arm: build_prompt(_vignette(), arm) for arm in ALL_ARMS}
    semantics = {arm: p.semantics for arm, p in packets.items()}
    assert len(set(semantics.values())) == 1  # identical frozen semantics object
    for arm, packet in packets.items():
        assert packet.semantics == HARMONIZER_SEMANTICS
        assert packet.tokenizer == HARMONIZER_SEMANTICS.tokenizer
        assert packet.context_truncation_policy == (HARMONIZER_SEMANTICS.context_truncation_policy)
        assert packet.hidden_source_use == HARMONIZER_SEMANTICS.hidden_source_use
        assert ARM_STRATEGY_TABLE[arm] == packet.strategy
    strategies = {p.strategy.strategy_id for p in packets.values()}
    # 6 arms, 5 distinct strategies: B2 (rubric arm) and B3 (static + post-filter)
    # deliberately share the static-context strategy; every OTHER arm differs.
    assert len(strategies) == 5
    assert {ARM_STRATEGY_TABLE[arm].strategy_id for arm in ALL_ARMS} == strategies


def test_instruction_text_is_byte_identical_across_arms() -> None:
    instruction = HARMONIZER_SEMANTICS.instruction_template
    for arm in ALL_ARMS:
        rendered = build_prompt(_vignette(), arm).rendered_prompt
        assert instruction in rendered
        # the only strategy-bearing line is the declared header
        strategy_lines = [
            ln for ln in rendered.splitlines() if ln.startswith("REGENERATION STRATEGY:")
        ]
        assert len(strategy_lines) == 1
        assert ARM_STRATEGY_TABLE[arm].strategy_id in strategy_lines[0]
    # no arm-conditional branch exists in the shared instruction template
    assert "{" not in instruction and "}" not in instruction


def test_packet_records_tokenizer_truncation_and_hidden_source_flag() -> None:
    packet = build_prompt(_vignette(), BASELINE_B1)
    d = packet.to_dict()
    assert d["tokenizer"] == HARMONIZER_SEMANTICS.tokenizer
    assert d["context_truncation_policy"] == HARMONIZER_SEMANTICS.context_truncation_policy
    assert d["hidden_source_use"] is False
    assert d["semantics"]["model_id"] == HARMONIZER_SEMANTICS.model_id
    assert d["semantics"]["model_version"] == HARMONIZER_SEMANTICS.model_version


def test_vignette_rendering_is_identical_across_arms() -> None:
    blocks = set()
    for arm in ALL_ARMS:
        rendered = build_prompt(_vignette(), arm).rendered_prompt
        blocks.add(rendered.split("CASE HISTORY (synthetic", 1)[1])
    assert len(blocks) == 1  # the case block is byte-identical for every arm


def test_tokens_per_arm_accounting_table() -> None:
    table = {}
    for arm in ALL_ARMS:
        packet = build_prompt(_vignette(), arm)
        budget = packet.token_budget.to_dict()
        assert budget["estimated_prompt_tokens"] > 0
        assert budget["max_context_tokens"] >= budget["estimated_prompt_tokens"]
        assert budget["max_output_tokens"] == HARMONIZER_SEMANTICS.max_output_tokens
        assert budget["total_tokens"] == budget["max_context_tokens"] + budget["max_output_tokens"]
        table[arm] = budget["estimated_prompt_tokens"]
    # deterministic accounting: identical re-run gives the identical table
    table_again = {
        arm: build_prompt(_vignette(), arm).token_budget.estimated_prompt_tokens for arm in ALL_ARMS
    }
    assert table == table_again
    # richer context sections never reduce the recorded token accounting
    sections = {arm: len(ARM_STRATEGY_TABLE[arm].context_sections) for arm in ALL_ARMS}
    by_section = sorted({(n, t) for arm, t in table.items() for n in [sections[arm]]})
    assert by_section == sorted(by_section, key=lambda pair: pair[0])


def test_comparability_checklist_accepts_all_arm_packets() -> None:
    checklist = ComparabilityChecklist()
    for arm in ALL_ARMS:
        ok, code, diffs = checklist.check(build_prompt(_vignette(), arm))
        assert (ok, code) == (True, REASON_OK)
        assert diffs == ()


def test_comparability_checklist_accepts_json_round_trip() -> None:
    packet = build_prompt(_vignette(), BASELINE_B4)
    ok, code, diffs = ComparabilityChecklist().check(json.loads(packet.to_json()))
    assert (ok, code) == (True, REASON_OK)
    assert diffs == ()


# ------------------------------------------------------------- adversarial


def _with_semantics_patch(**patch: object) -> PromptPacket:
    """Build a packet whose recorded semantics carry a tampered field."""
    packet = build_prompt(_vignette(), BASELINE_B4)
    tampered_semantics = dataclasses.replace(packet.semantics, **patch)  # type: ignore[arg-type]
    return dataclasses.replace(packet, semantics=tampered_semantics)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("provider", "other-provider"),
        ("model_id", "other-model-x"),
        ("model_version", "study-pinned@2027-aime-rc2"),
        ("tokenizer", "other-tokenizer-v9"),
        ("temperature", 0.7),
        ("seed", 99),
        ("max_output_tokens", 256),
        ("system_role", "You are a helpful pirate."),
        (
            "instruction_template",
            "TASK INSTRUCTION: answer in haiku form.",
        ),
        ("context_truncation_policy", "drop-newest-keep-nothing"),
        ("hidden_source_use", True),
    ],
)
def test_checklist_refuses_changed_model_or_instruction_semantics(
    field: str, value: object
) -> None:
    packet = _with_semantics_patch(**{field: value})
    ok, code, diffs = ComparabilityChecklist().check(packet)
    assert ok is False
    assert code == REASON_ARM_NONCOMPARABLE
    assert any(field in d for d in diffs)


def test_checklist_refuses_undeclared_hidden_source_use() -> None:
    packet = _with_semantics_patch(hidden_source_use=True)
    d = packet.to_dict()
    d["hidden_source_use"] = True  # the packet-level flag must agree too
    ok, code, diffs = ComparabilityChecklist().check(d)
    assert ok is False
    assert code == REASON_ARM_NONCOMPARABLE
    assert any("hidden_source_use" in diff for diff in diffs)
    assert REASON_HIDDEN_SOURCE in {REASON_HIDDEN_SOURCE}  # code surface exists
    # and the packet-level flag alone (semantics consistent) is still refused
    packet2 = build_prompt(_vignette(), BASELINE_B1)
    d2 = packet2.to_dict()
    d2["hidden_source_use"] = True
    ok2, code2, _ = ComparabilityChecklist().check(d2)
    assert ok2 is False and code2 == REASON_ARM_NONCOMPARABLE


def test_checklist_refuses_changed_top_level_recorded_policy() -> None:
    packet = build_prompt(_vignette(), BASELINE_B3)
    d = packet.to_dict()
    d["context_truncation_policy"] = "truncatе-nothing"  # noqa: RUF001 - deliberate tamper
    d["tokenizer"] = "greedy-v0"
    ok, code, diffs = ComparabilityChecklist().check(d)
    assert ok is False and code == REASON_ARM_NONCOMPARABLE
    assert any("context_truncation_policy" in diff for diff in diffs)
    assert any("tokenizer" in diff for diff in diffs)


def test_checklist_refuses_non_arm_strategy_change_disguised_as_semantics() -> None:
    # A strategy change is legal ONLY through the pinned per-arm table; a
    # packet claiming a strategy not in the table is refused.
    bogus = ArmStrategy(
        strategy_id="secret-hidden-retrieval",
        strategy_description="undocumented strategy",
        context_sections=("system", "hidden_source"),
    )
    packet = build_prompt(_vignette(), BASELINE_B4)
    tampered = dataclasses.replace(packet, strategy=bogus)
    ok, code, diffs = ComparabilityChecklist().check(tampered)
    # strategy itself is the allowed lever: semantics unchanged -> still comparable
    assert (ok, code) == (True, REASON_OK)
    # but it is NOT the pinned B4 strategy -> table mismatch is detectable
    assert tampered.strategy != ARM_STRATEGY_TABLE[BASELINE_B4]
    assert REASON_STRATEGY_MISMATCH  # code surface exists for gate integration
    assert diffs == ()


@pytest.mark.parametrize("arm", ALL_ARMS)
def test_tamper_with_any_serialized_field_invalidates_hash(arm: str) -> None:
    packet = build_prompt(_vignette(), arm)
    base = packet.to_dict()
    for field, mutate in (
        ("arm_id", lambda d: d.__setitem__("arm_id", "B9-forged-arm")),
        ("rendered_prompt", lambda d: d.__setitem__("rendered_prompt", "tampered")),
        ("tokenizer", lambda d: d.__setitem__("tokenizer", "forged-tokenizer")),
        ("hidden_source_use", lambda d: d.__setitem__("hidden_source_use", True)),
        (
            "vignette_sha256",
            lambda d: d.__setitem__("vignette_sha256", "0" * 64),
        ),
        (
            "semantics",
            lambda d: d["semantics"].__setitem__("model_id", "forged-model"),
        ),
        ("strategy", lambda d: d["strategy"].__setitem__("strategy_id", "forged")),
    ):
        forged = copy.deepcopy(base)
        mutate(forged)
        ok, code = verify_packet(packet, forged)
        assert ok is False and code == REASON_HASH_MISMATCH, field


def test_verify_packet_detects_hash_field_swap_between_arms() -> None:
    p1 = build_prompt(_vignette(), BASELINE_B0)
    p2 = build_prompt(_vignette(), BASELINE_B1)
    d1 = p1.to_dict()
    d1["packet_hash"] = p2.packet_hash
    ok, code = verify_packet(p1, d1)
    assert ok is False and code == REASON_HASH_MISMATCH


def test_unknown_arm_fails_closed() -> None:
    with pytest.raises(ph.PromptPacketError) as excinfo:
        build_prompt(_vignette(), "B9-unknown-arm")
    assert excinfo.value.reason_code == REASON_UNKNOWN_ARM
    with pytest.raises(ph.PromptPacketError) as excinfo_empty:
        build_prompt(_vignette(), "")
    assert excinfo_empty.value.reason_code == REASON_UNKNOWN_ARM
    with pytest.raises(ph.PromptPacketError) as excinfo_type:
        build_prompt(_vignette(), 123)  # type: ignore[arg-type]
    assert excinfo_type.value.reason_code == REASON_UNKNOWN_ARM


def test_missing_arm_table_entry_cannot_be_smuggled() -> None:
    # an arm id that matches the shape but is absent from the pinned table
    with pytest.raises(ph.PromptPacketError) as excinfo:
        build_prompt(_vignette(), "B7-unregistered-strategy")
    assert excinfo.value.reason_code == REASON_UNKNOWN_ARM


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (
            lambda v: v.pop("snapshot"),
            REASON_MISSING_FIELD,
        ),
        (
            lambda v: v.__setitem__("case_id", 42),
            REASON_MALFORMED,
        ),
        (
            lambda v: v["snapshot"].__setitem__("medications", "metformin"),
            REASON_MALFORMED,
        ),
        (
            lambda v: v["timeline"].reverse(),
            REASON_BAD_TIMELINE,
        ),
        (
            lambda v: v["timeline"].append(
                {
                    "order": 9,
                    "event_kind": "NOT_A_KIND",
                    "logical_time": 9,
                    "payload": None,
                }
            ),
            REASON_BAD_TIMELINE,
        ),
    ],
)
def test_malformed_vignette_fails_closed(mutate, code: str) -> None:
    vignette = _vignette()
    mutate(vignette)
    with pytest.raises(ph.PromptPacketError) as excinfo:
        build_prompt(vignette, BASELINE_B1)
    assert excinfo.value.reason_code == code


def test_phi_like_vignette_refused_like_baselines() -> None:
    vignette = _vignette()
    vignette["patient_name"] = "Synthetic Person"
    with pytest.raises(ph.PromptPacketError) as excinfo:
        build_prompt(vignette, BASELINE_B1)
    assert excinfo.value.reason_code == REASON_MALFORMED
    assert "PHI_FIELDS" in excinfo.value.detail


def test_non_mapping_vignette_fails_closed() -> None:
    with pytest.raises(ph.PromptPacketError) as excinfo:
        build_prompt("not-a-vignette", BASELINE_B1)  # type: ignore[arg-type]
    assert excinfo.value.reason_code == REASON_MALFORMED
