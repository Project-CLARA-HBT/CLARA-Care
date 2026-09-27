"""Unit tests for E04 TOCTOU schedule grammar, AST node lowering, and step mapping."""

from __future__ import annotations

import pytest

from evaluation.glhs_toctou_r2.generator import generate_schedules
from evaluation.glhs_toctou_r2.grammar import (
    ActionType,
    ASTModifierNode,
    ASTNode,
    ASTOpNode,
    ASTScheduleNode,
    ASTTimingNode,
    ASTTxNode,
    EntityConfig,
    Modifier,
    MutationKind,
    PG_PRIMITIVE_MAPPING,
    ScheduleDescriptor,
    ScheduleStep,
    TimingMode,
    descriptor_to_steps,
    lower_ast_to_steps,
    lower_descriptor_to_ast,
)


def test_grammar_15_dimensions_coverage() -> None:
    """Verify all 15 operation and interleaving dimensions are covered by enums."""
    # Operation dimensions (12)
    mutations = {m.value for m in MutationKind}
    expected_mutations = {
        "consent_grant",
        "consent_revoke",
        "consent_regrant",
        "role_demote",
        "role_promote",
        "policy_epoch_advance",
        "snapshot_expiry",
        "state_version_advance",
        "entity_partition_same_profile",
        "entity_partition_cross_profile",
        "unrelated_entity_update",
        "evidence_withdraw",
        "evidence_replace",
        "multi_entity_dependency_change",
    }
    assert expected_mutations.issubset(mutations)

    # Interleaving dimensions (3: aborts/retries/delays, partial/simultaneous, read-before/write-after)
    timings = {t.value for t in TimingMode}
    expected_timings = {
        "mutation_before_commit",
        "commit_before_mutation",
        "simultaneous_release",
        "read_before_write_after",
        "delayed_commit",
        "partial_overlap",
    }
    assert expected_timings == timings

    modifiers = {m.value for m in Modifier}
    expected_modifiers = {
        "none",
        "transaction_abort",
        "retry_after_rollback",
        "deadlock_provocation",
        "competing_lock",
        "simultaneous_writers",
    }
    assert expected_modifiers == modifiers


def test_ast_node_types_and_serialization() -> None:
    """Test AST node construction and serialization to dictionary."""
    op = ASTOpNode(
        mutation_kind=MutationKind.CONSENT_REVOKE,
        target_entity=EntityConfig.OWNER_SELF,
    )
    tx = ASTTxNode(
        tx_id="tx_test_1",
        operations=(op,),
        isolation_level="READ COMMITTED",
        is_writer=True,
    )
    timing = ASTTimingNode(
        mode=TimingMode.MUTATION_BEFORE_COMMIT,
        barrier_phase="release",
        barrier_parties=2,
        delay_ms=0.0,
    )
    modifier = ASTModifierNode(
        modifier=Modifier.NONE,
        retry_count=0,
    )
    schedule_ast = ASTScheduleNode(
        schedule_id="E04-TEST-00001",
        transactions=(tx,),
        timing=timing,
        modifier=modifier,
        entity_config=EntityConfig.OWNER_SELF,
    )

    ast_dict = schedule_ast.to_dict()
    assert ast_dict["node_type"] == "ASTScheduleNode"
    assert ast_dict["schedule_id"] == "E04-TEST-00001"
    assert len(ast_dict["transactions"]) == 1
    assert ast_dict["transactions"][0]["operations"][0]["mutation_kind"] == "consent_revoke"


def test_lowering_descriptor_to_ast() -> None:
    """Test lowering a ScheduleDescriptor into AST nodes."""
    desc = ScheduleDescriptor(
        schedule_id="E04-TEST-00002",
        mutations=(MutationKind.CONSENT_REVOKE, MutationKind.ROLE_DEMOTE),
        timing=TimingMode.SIMULTANEOUS_RELEASE,
        entity=EntityConfig.DELEGATED_ACTOR,
        modifier=Modifier.COMPETING_LOCK,
        compound=True,
    )

    ast_root = lower_descriptor_to_ast(desc)
    assert isinstance(ast_root, ASTScheduleNode)
    assert ast_root.schedule_id == "E04-TEST-00002"
    assert ast_root.timing.mode == TimingMode.SIMULTANEOUS_RELEASE
    assert ast_root.modifier.modifier == Modifier.COMPETING_LOCK
    assert len(ast_root.transactions[0].operations) == 2


def test_lowering_ast_to_steps_and_primitives() -> None:
    """Test lowering AST to concrete ScheduleStep tuple mapped to PostgreSQL primitives."""
    desc = ScheduleDescriptor(
        schedule_id="E04-TEST-00003",
        mutations=(MutationKind.CONSENT_REVOKE,),
        timing=TimingMode.MUTATION_BEFORE_COMMIT,
        entity=EntityConfig.OWNER_SELF,
        modifier=Modifier.NONE,
    )

    steps = descriptor_to_steps(desc)
    assert isinstance(steps, tuple)
    assert len(steps) > 0

    actions = [s.action for s in steps]
    assert ActionType.BEGIN_TRANSACTION in actions
    assert ActionType.COMMIT_TRANSACTION in actions
    assert ActionType.APPLY_TRANSITION in actions

    # Check PostgreSQL primitive mappings
    for step in steps:
        assert isinstance(step, ScheduleStep)
        if step.action == ActionType.WRITE_MUTATION and step.target == "consent_revoke":
            assert step.pg_primitive == PG_PRIMITIVE_MAPPING["consent_revoke"]
        if step.action == ActionType.APPLY_TRANSITION:
            assert step.pg_primitive == PG_PRIMITIVE_MAPPING["apply_transition"]


def test_descriptor_ast_and_step_properties() -> None:
    """Test the ast_root and steps properties on ScheduleDescriptor."""
    desc = ScheduleDescriptor(
        schedule_id="E04-TEST-00004",
        mutations=(MutationKind.POLICY_EPOCH_ADVANCE,),
        timing=TimingMode.DELAYED_COMMIT,
        entity=EntityConfig.OWNER_SELF,
        modifier=Modifier.RETRY_AFTER_ROLLBACK,
    )

    ast_root = desc.ast_root
    steps = desc.steps

    assert isinstance(ast_root, ASTScheduleNode)
    assert isinstance(steps, tuple)
    assert desc.to_dict()["steps"] is not None
    assert len(desc.to_dict()["steps"]) == len(steps)


def test_generator_schedules_ast_compilation() -> None:
    """Verify all generated schedules compile cleanly to AST and steps."""
    schedules = generate_schedules(minimum=64)
    for desc in schedules:
        ast_node = desc.ast_root
        steps = desc.steps
        assert ast_node.schedule_id == desc.schedule_id
        assert len(steps) > 0
