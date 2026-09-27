"""Schedule grammar for the E04 randomized TOCTOU campaign.

Defines the vocabulary of governance mutations, timing modes, entity
configurations, and composition rules that the generator uses to produce
unique logical schedules.  Every schedule is a product of:

  mutation_set  x  timing_mode  x  entity_config  x  modifiers

The grammar is deliberately over-generating: the generator filters
infeasible or duplicate combinations after expansion.

Architecture (Role A) design decisions:

1. **Mutation vocabulary** covers all governance dimensions that the GLHS
   gateway can observe between snapshot compilation and transition commit:
   consent (grant/revoke/regrant), role (promote/demote), policy epoch
   (advance), snapshot expiry (time-based staleness), state version
   (advance by unrelated writer), entity partition (same-profile vs
   cross-profile), evidence (withdraw/replace), and multi-entity
   dependency changes.

2. **Timing modes** capture the ordering relationships the TOCTOU window
   can exhibit: mutation-before-commit, commit-before-mutation,
   simultaneous release, read-before/write-after interleaving, delayed
   commit, and partial overlap.

3. **Modifiers** introduce fault injection: transaction abort, retry after
   rollback, deadlock provocation, and competing-lock contention.

4. **Entity configurations** vary the identity relationship between
   mutation target and commit subject: same user, delegated user,
   unrelated entity, and cross-profile.

This module holds no mutable state and never opens a database connection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, unique
from typing import FrozenSet, Sequence


# ---------------------------------------------------------------------------
# Mutation vocabulary
# ---------------------------------------------------------------------------

@unique
class MutationKind(Enum):
    """A single governance mutation that can race with a transition commit."""

    CONSENT_REVOKE = "consent_revoke"
    CONSENT_GRANT = "consent_grant"
    CONSENT_REGRANT = "consent_regrant"
    ROLE_DEMOTE = "role_demote"
    ROLE_PROMOTE = "role_promote"
    POLICY_EPOCH_ADVANCE = "policy_epoch_advance"
    SNAPSHOT_EXPIRY = "snapshot_expiry"
    STATE_VERSION_ADVANCE = "state_version_advance"
    ENTITY_PARTITION_SAME = "entity_partition_same_profile"
    ENTITY_PARTITION_CROSS = "entity_partition_cross_profile"
    UNRELATED_ENTITY_UPDATE = "unrelated_entity_update"
    EVIDENCE_WITHDRAW = "evidence_withdraw"
    EVIDENCE_REPLACE = "evidence_replace"
    MULTI_ENTITY_DEPENDENCY = "multi_entity_dependency_change"


# ---------------------------------------------------------------------------
# Timing modes
# ---------------------------------------------------------------------------

@unique
class TimingMode(Enum):
    """The temporal ordering between the governance mutation and the commit."""

    MUTATION_BEFORE_COMMIT = "mutation_before_commit"
    COMMIT_BEFORE_MUTATION = "commit_before_mutation"
    SIMULTANEOUS_RELEASE = "simultaneous_release"
    READ_BEFORE_WRITE_AFTER = "read_before_write_after"
    DELAYED_COMMIT = "delayed_commit"
    PARTIAL_OVERLAP = "partial_overlap"


# ---------------------------------------------------------------------------
# Modifiers (fault injection and concurrency stress)
# ---------------------------------------------------------------------------

@unique
class Modifier(Enum):
    """Optional schedule modifiers for fault injection."""

    NONE = "none"
    TRANSACTION_ABORT = "transaction_abort"
    RETRY_AFTER_ROLLBACK = "retry_after_rollback"
    DEADLOCK_PROVOCATION = "deadlock_provocation"
    COMPETING_LOCK = "competing_lock"
    SIMULTANEOUS_WRITERS = "simultaneous_writers"


# ---------------------------------------------------------------------------
# Entity configurations
# ---------------------------------------------------------------------------

@unique
class EntityConfig(Enum):
    """The identity relationship between the mutation target and the commit subject."""

    OWNER_SELF = "owner_self"
    DELEGATED_ACTOR = "delegated_actor"
    UNRELATED_ENTITY = "unrelated_entity"
    CROSS_PROFILE = "cross_profile"


# ---------------------------------------------------------------------------
# Compound mutations (multi-dimension drift)
# ---------------------------------------------------------------------------

# Pre-defined compound mutation sets that represent realistic multi-coordinate
# drift scenarios.  Each tuple lists 2+ mutation kinds applied atomically before
# the commit attempt.
COMPOUND_MUTATION_SETS: tuple[tuple[MutationKind, ...], ...] = (
    (MutationKind.CONSENT_REVOKE, MutationKind.ROLE_DEMOTE),
    (MutationKind.CONSENT_REVOKE, MutationKind.POLICY_EPOCH_ADVANCE),
    (MutationKind.ROLE_DEMOTE, MutationKind.POLICY_EPOCH_ADVANCE),
    (MutationKind.CONSENT_REVOKE, MutationKind.ROLE_DEMOTE, MutationKind.POLICY_EPOCH_ADVANCE),
    (MutationKind.CONSENT_REVOKE, MutationKind.STATE_VERSION_ADVANCE),
    (MutationKind.ROLE_DEMOTE, MutationKind.STATE_VERSION_ADVANCE),
    (MutationKind.EVIDENCE_WITHDRAW, MutationKind.CONSENT_REVOKE),
    (MutationKind.EVIDENCE_REPLACE, MutationKind.ROLE_DEMOTE),
    (MutationKind.MULTI_ENTITY_DEPENDENCY, MutationKind.CONSENT_REVOKE),
    (MutationKind.SNAPSHOT_EXPIRY, MutationKind.CONSENT_REVOKE),
)


# ---------------------------------------------------------------------------
# Schedule descriptor
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScheduleDescriptor:
    """A fully specified logical schedule before PostgreSQL execution.

    The ``canonical_key`` is a deterministic deduplication key derived from
    the sorted mutation set, timing mode, entity config, and modifier.
    Two descriptors with the same canonical key are logically identical
    regardless of generation order.
    """

    schedule_id: str
    mutations: tuple[MutationKind, ...]
    timing: TimingMode
    entity: EntityConfig
    modifier: Modifier
    compound: bool = False
    expected_outcome: str = "REJECT"
    barrier_phases: tuple[str, ...] = ("release",)
    writer_count: int = 2

    @property
    def canonical_key(self) -> str:
        """Deterministic deduplication key for the schedule."""
        mutations_key = "+".join(sorted(m.value for m in self.mutations))
        return f"{mutations_key}|{self.timing.value}|{self.entity.value}|{self.modifier.value}"

    @property
    def mutation_set(self) -> frozenset[MutationKind]:
        return frozenset(self.mutations)

    @property
    def is_positive_control(self) -> bool:
        """True when the schedule is a valid-commit positive control."""
        return self.expected_outcome == "ADMIT"

    @property
    def persisted_writers(self) -> tuple[str, ...]:
        return tuple(m.value for m in self.mutations)

    @property
    def interleaving_coverage(self) -> tuple[str, ...]:
        """Interleaving coverage tags contributed by this schedule."""
        tags = [self.timing.value]
        if self.modifier == Modifier.COMPETING_LOCK:
            tags.append("competing_lock")
        if self.modifier == Modifier.RETRY_AFTER_ROLLBACK:
            tags.append("rollback_retry")
        if self.modifier == Modifier.SIMULTANEOUS_WRITERS:
            tags.append("simultaneous_writers")
        if self.compound:
            tags.append("compound_drift")
        return tuple(sorted(set(tags)))

    @property
    def ast_root(self) -> ASTScheduleNode:
        """Derive the AST schedule node representation for this descriptor."""
        return lower_descriptor_to_ast(self)

    @property
    def steps(self) -> tuple[ScheduleStep, ...]:
        """Derive the sequence of executable schedule steps mapped to PostgreSQL primitives."""
        return lower_ast_to_steps(self.ast_root)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.schedule_id,
            "mutations": [m.value for m in self.mutations],
            "timing": self.timing.value,
            "entity": self.entity.value,
            "modifier": self.modifier.value,
            "compound": self.compound,
            "expected_outcome": self.expected_outcome,
            "barrier_phases": list(self.barrier_phases),
            "writer_count": self.writer_count,
            "canonical_key": self.canonical_key,
            "persisted_writers": list(self.persisted_writers),
            "interleaving_coverage": list(self.interleaving_coverage),
            "steps": [s.to_dict() for s in self.steps],
        }


# ---------------------------------------------------------------------------
# Feasibility rules
# ---------------------------------------------------------------------------

# Infeasible combinations that the generator must exclude.
_INFEASIBLE: set[tuple[str, str]] = {
    # Consent grant racing commit-before-mutation is a no-op (consent was
    # already present when the snapshot was compiled).
    ("consent_grant", "commit_before_mutation"),
    # Cross-profile entity + same-profile entity partition is contradictory.
    ("entity_partition_same_profile", "cross_profile"),
    # Unrelated entity update + owner_self is a no-op.
    ("unrelated_entity_update", "owner_self"),
}


def is_feasible(desc: ScheduleDescriptor) -> bool:
    """Return True if the schedule combination is logically feasible."""
    for mutation in desc.mutations:
        key = (mutation.value, desc.timing.value)
        if key in _INFEASIBLE:
            return False
        entity_key = (mutation.value, desc.entity.value)
        if entity_key in _INFEASIBLE:
            return False
    # Deadlock provocation requires >= 2 writers.
    if desc.modifier == Modifier.DEADLOCK_PROVOCATION and desc.writer_count < 2:
        return False
    # Simultaneous writers requires >= 2 writers.
    if desc.modifier == Modifier.SIMULTANEOUS_WRITERS and desc.writer_count < 2:
        return False
    return True


# ---------------------------------------------------------------------------
# Outcome classification rules
# ---------------------------------------------------------------------------

# Mutations that MUST cause rejection when they precede a commit attempt.
SAFETY_CRITICAL_MUTATIONS: frozenset[MutationKind] = frozenset({
    MutationKind.CONSENT_REVOKE,
    MutationKind.ROLE_DEMOTE,
    MutationKind.POLICY_EPOCH_ADVANCE,
    MutationKind.EVIDENCE_WITHDRAW,
})

# Mutations that are benign (commit may proceed).
BENIGN_MUTATIONS: frozenset[MutationKind] = frozenset({
    MutationKind.CONSENT_GRANT,
    MutationKind.CONSENT_REGRANT,
    MutationKind.ROLE_PROMOTE,
    MutationKind.UNRELATED_ENTITY_UPDATE,
})

# Mutations that cause rejection via state-version staleness.
STALENESS_MUTATIONS: frozenset[MutationKind] = frozenset({
    MutationKind.STATE_VERSION_ADVANCE,
    MutationKind.ENTITY_PARTITION_SAME,
    MutationKind.MULTI_ENTITY_DEPENDENCY,
    MutationKind.EVIDENCE_REPLACE,
})

# Snapshot expiry is a time-dependent rejection.
EXPIRY_MUTATIONS: frozenset[MutationKind] = frozenset({
    MutationKind.SNAPSHOT_EXPIRY,
})


def expected_outcome_for(desc: ScheduleDescriptor) -> str:
    """Derive the expected outcome classification for a schedule.

    Rules:
    - If ANY safety-critical mutation precedes the commit in the timing
      model, the commit MUST be rejected (REJECT).
    - If the timing is commit-before-mutation and mutations are all
      safety-critical, the commit is ADMIT (it completed before the
      mutation took effect).
    - Staleness mutations always cause rejection (REJECT).
    - Benign-only mutation sets are ADMIT.
    - Modifiers that inject faults (abort, deadlock) produce OPERATIONAL.
    - Cross-profile + unrelated entity is ADMIT (isolation boundary).
    """
    # Fault-injection modifiers produce operational outcomes.
    if desc.modifier in (Modifier.TRANSACTION_ABORT, Modifier.DEADLOCK_PROVOCATION):
        return "OPERATIONAL"

    mutation_set = desc.mutation_set

    # If any staleness or expiry mutation is present, always reject.
    if mutation_set & (STALENESS_MUTATIONS | EXPIRY_MUTATIONS):
        return "REJECT"

    # Cross-profile + unrelated entity: commit is isolated.
    if desc.entity == EntityConfig.CROSS_PROFILE and mutation_set <= {
        MutationKind.ENTITY_PARTITION_CROSS,
        MutationKind.UNRELATED_ENTITY_UPDATE,
    }:
        return "ADMIT"

    # Commit-before-mutation: if timing proves commit completed first.
    if desc.timing == TimingMode.COMMIT_BEFORE_MUTATION:
        if mutation_set <= (SAFETY_CRITICAL_MUTATIONS | BENIGN_MUTATIONS):
            return "ADMIT"

    # If any safety-critical mutation is in the set and timing is not
    # commit-before-mutation, the commit must be rejected.
    if mutation_set & SAFETY_CRITICAL_MUTATIONS:
        if desc.timing != TimingMode.COMMIT_BEFORE_MUTATION:
            return "REJECT"

    # Benign-only mutations: commit is admitted.
    if mutation_set <= BENIGN_MUTATIONS:
        return "ADMIT"

    # Simultaneous release or partial overlap with safety-critical: indeterminate.
    if desc.timing in (TimingMode.SIMULTANEOUS_RELEASE, TimingMode.PARTIAL_OVERLAP):
        return "INDETERMINATE"

    return "REJECT"


# ---------------------------------------------------------------------------
# AST Node definitions & Schedule Step representations
# ---------------------------------------------------------------------------

@unique
class ActionType(Enum):
    """Atomic action types comprising PostgreSQL schedule steps."""

    BEGIN_TRANSACTION = "begin_transaction"
    LOAD_TARGET = "load_target"
    ACQUIRE_LOCK = "acquire_lock"
    WRITE_MUTATION = "write_mutation"
    BARRIER_WAIT = "barrier_wait"
    COMMIT_TRANSACTION = "commit_transaction"
    ROLLBACK_TRANSACTION = "rollback_transaction"
    INJECT_DELAY = "inject_delay"
    RETRY_TRANSACTION = "retry_transaction"
    APPLY_TRANSITION = "apply_transition"


@dataclass(frozen=True)
class ScheduleStep:
    """A concrete executable schedule step mapped to PostgreSQL primitives."""

    step_index: int
    tx_id: str
    action: ActionType
    target: str
    parameters: dict[str, object] = field(default_factory=dict)
    barrier_phase: str | None = None
    pg_primitive: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "step_index": self.step_index,
            "tx_id": self.tx_id,
            "action": self.action.value,
            "target": self.target,
            "parameters": self.parameters,
            "barrier_phase": self.barrier_phase,
            "pg_primitive": self.pg_primitive,
        }


@dataclass(frozen=True)
class ASTNode:
    """Base class for schedule Abstract Syntax Tree (AST) nodes."""

    def to_dict(self) -> dict[str, object]:
        return {"node_type": self.__class__.__name__}


@dataclass(frozen=True)
class ASTOpNode(ASTNode):
    """AST node for a single governance or state operation."""

    mutation_kind: MutationKind
    target_entity: EntityConfig
    parameters: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "node_type": self.__class__.__name__,
            "mutation_kind": self.mutation_kind.value,
            "target_entity": self.target_entity.value,
            "parameters": self.parameters,
        }


@dataclass(frozen=True)
class ASTTxNode(ASTNode):
    """AST node representing a transactional scope."""

    tx_id: str
    operations: tuple[ASTOpNode, ...]
    isolation_level: str = "READ COMMITTED"
    is_writer: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "node_type": self.__class__.__name__,
            "tx_id": self.tx_id,
            "operations": [op.to_dict() for op in self.operations],
            "isolation_level": self.isolation_level,
            "is_writer": self.is_writer,
        }


@dataclass(frozen=True)
class ASTTimingNode(ASTNode):
    """AST node representing temporal interleaving and synchronization."""

    mode: TimingMode
    barrier_phase: str = "release"
    barrier_parties: int = 2
    delay_ms: float = 0.0

    def to_dict(self) -> dict[str, object]:
        return {
            "node_type": self.__class__.__name__,
            "mode": self.mode.value,
            "barrier_phase": self.barrier_phase,
            "barrier_parties": self.barrier_parties,
            "delay_ms": self.delay_ms,
        }


@dataclass(frozen=True)
class ASTModifierNode(ASTNode):
    """AST node representing fault injection or concurrency stress."""

    modifier: Modifier
    retry_count: int = 0
    competing_locks: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "node_type": self.__class__.__name__,
            "modifier": self.modifier.value,
            "retry_count": self.retry_count,
            "competing_locks": list(self.competing_locks),
        }


@dataclass(frozen=True)
class ASTScheduleNode(ASTNode):
    """Root AST node representing a complete logical schedule program."""

    schedule_id: str
    transactions: tuple[ASTTxNode, ...]
    timing: ASTTimingNode
    modifier: ASTModifierNode
    entity_config: EntityConfig

    def to_dict(self) -> dict[str, object]:
        return {
            "node_type": self.__class__.__name__,
            "schedule_id": self.schedule_id,
            "transactions": [tx.to_dict() for tx in self.transactions],
            "timing": self.timing.to_dict(),
            "modifier": self.modifier.to_dict(),
            "entity_config": self.entity_config.value,
        }


# ---------------------------------------------------------------------------
# PostgreSQL Primitive Mapping Matrix
# ---------------------------------------------------------------------------

PG_PRIMITIVE_MAPPING: dict[str, str] = {
    "consent_revoke": "evaluation.glhs_postgres_toctou.governance_writers.consent_revoke",
    "consent_grant": "evaluation.glhs_postgres_toctou.governance_writers.consent_revoke",
    "consent_regrant": "evaluation.glhs_postgres_toctou.governance_writers.consent_revoke",
    "role_demote": "evaluation.glhs_postgres_toctou.governance_writers.role_change",
    "role_promote": "evaluation.glhs_postgres_toctou.governance_writers.role_change",
    "policy_epoch_advance": "evaluation.glhs_postgres_toctou.governance_writers.advance_governance_policy_epoch",
    "snapshot_expiry": "evaluation.glhs_postgres_toctou.executor_v2.compile_thss",
    "state_version_advance": "evaluation.glhs_postgres_toctou.executor_v2.apply_transition",
    "entity_partition_same_profile": "evaluation.glhs_postgres_toctou.executor_v2.apply_transition",
    "entity_partition_cross_profile": "evaluation.glhs_postgres_toctou.executor_v2._seed_delegated_scope",
    "unrelated_entity_update": "evaluation.glhs_postgres_toctou.governance_writers.purpose_or_authorization_change",
    "evidence_withdraw": "evaluation.glhs_postgres_toctou.executor_v2.record_evidence",
    "evidence_replace": "evaluation.glhs_postgres_toctou.executor_v2.record_evidence",
    "multi_entity_dependency_change": "evaluation.glhs_postgres_toctou.executor_v2.apply_transition",
    "barrier_wait": "evaluation.glhs_postgres_toctou.barrier.PhasedBarrier.wait",
    "competing_lock": "evaluation.glhs_postgres_toctou.barrier.CompetingLock",
    "apply_transition": "evaluation.glhs_postgres_toctou.executor_v2.apply_transition",
    "trace_begin": "evaluation.glhs_postgres_toctou.schedule_primitives.TransactionTrace.begin",
    "trace_commit": "evaluation.glhs_postgres_toctou.schedule_primitives.TransactionTrace.commit",
    "trace_rollback": "evaluation.glhs_postgres_toctou.schedule_primitives.TransactionTrace.rollback",
}


# ---------------------------------------------------------------------------
# Lowering functions (Descriptor -> AST -> Schedule Steps)
# ---------------------------------------------------------------------------

def lower_descriptor_to_ast(desc: ScheduleDescriptor) -> ASTScheduleNode:
    """Lower a ScheduleDescriptor into an ASTScheduleNode program representation."""
    op_nodes = tuple(
        ASTOpNode(mutation_kind=m, target_entity=desc.entity)
        for m in desc.mutations
    )
    gov_tx = ASTTxNode(
        tx_id="tx_governance_writer",
        operations=op_nodes,
        isolation_level="READ COMMITTED",
        is_writer=True,
    )

    commit_op = ASTOpNode(
        mutation_kind=MutationKind.STATE_VERSION_ADVANCE,
        target_entity=desc.entity,
    )
    commit_tx = ASTTxNode(
        tx_id="tx_transition_commit",
        operations=(commit_op,),
        isolation_level="READ COMMITTED",
        is_writer=True,
    )

    txs: list[ASTTxNode] = [gov_tx, commit_tx]
    if desc.modifier == Modifier.SIMULTANEOUS_WRITERS or desc.writer_count > 2:
        competing_tx = ASTTxNode(
            tx_id="tx_competing_writer",
            operations=(commit_op,),
            isolation_level="READ COMMITTED",
            is_writer=True,
        )
        txs.append(competing_tx)

    timing_node = ASTTimingNode(
        mode=desc.timing,
        barrier_phase=desc.barrier_phases[0] if desc.barrier_phases else "release",
        barrier_parties=desc.writer_count,
        delay_ms=50.0 if desc.timing == TimingMode.DELAYED_COMMIT else 0.0,
    )

    competing_locks = ("competing_governance_lock",) if desc.modifier == Modifier.COMPETING_LOCK else ()
    modifier_node = ASTModifierNode(
        modifier=desc.modifier,
        retry_count=1 if desc.modifier == Modifier.RETRY_AFTER_ROLLBACK else 0,
        competing_locks=competing_locks,
    )

    return ASTScheduleNode(
        schedule_id=desc.schedule_id,
        transactions=tuple(txs),
        timing=timing_node,
        modifier=modifier_node,
        entity_config=desc.entity,
    )


def lower_ast_to_steps(ast_root: ASTScheduleNode) -> tuple[ScheduleStep, ...]:
    """Lower an ASTScheduleNode into a sequential tuple of executable ScheduleSteps."""
    steps: list[ScheduleStep] = []
    idx = 0

    # 1. Setup phase / barriers
    if ast_root.timing.mode in (TimingMode.SIMULTANEOUS_RELEASE, TimingMode.PARTIAL_OVERLAP, TimingMode.READ_BEFORE_WRITE_AFTER):
        steps.append(
            ScheduleStep(
                step_index=idx,
                tx_id="system",
                action=ActionType.BARRIER_WAIT,
                target="barrier",
                parameters={"parties": ast_root.timing.barrier_parties},
                barrier_phase=ast_root.timing.barrier_phase,
                pg_primitive=PG_PRIMITIVE_MAPPING["barrier_wait"],
            )
        )
        idx += 1

    # 2. Lock acquiring for competing lock modifier
    if ast_root.modifier.modifier in (Modifier.COMPETING_LOCK, Modifier.DEADLOCK_PROVOCATION):
        for lock in ast_root.modifier.competing_locks:
            steps.append(
                ScheduleStep(
                    step_index=idx,
                    tx_id="tx_governance_writer",
                    action=ActionType.ACQUIRE_LOCK,
                    target=lock,
                    parameters={"lock_name": lock},
                    pg_primitive=PG_PRIMITIVE_MAPPING["competing_lock"],
                )
            )
            idx += 1

    # 3. Governance transaction operations
    gov_tx = ast_root.transactions[0]
    steps.append(
        ScheduleStep(
            step_index=idx,
            tx_id=gov_tx.tx_id,
            action=ActionType.BEGIN_TRANSACTION,
            target="pg_session",
            pg_primitive=PG_PRIMITIVE_MAPPING["trace_begin"],
        )
    )
    idx += 1

    for op in gov_tx.operations:
        m_val = op.mutation_kind.value
        steps.append(
            ScheduleStep(
                step_index=idx,
                tx_id=gov_tx.tx_id,
                action=ActionType.LOAD_TARGET,
                target=m_val,
                parameters={"entity": op.target_entity.value},
                pg_primitive=PG_PRIMITIVE_MAPPING.get(m_val, "load_target"),
            )
        )
        idx += 1
        steps.append(
            ScheduleStep(
                step_index=idx,
                tx_id=gov_tx.tx_id,
                action=ActionType.WRITE_MUTATION,
                target=m_val,
                parameters={"mutation": m_val},
                pg_primitive=PG_PRIMITIVE_MAPPING.get(m_val, "write_mutation"),
            )
        )
        idx += 1

    if ast_root.modifier.modifier == Modifier.TRANSACTION_ABORT:
        steps.append(
            ScheduleStep(
                step_index=idx,
                tx_id=gov_tx.tx_id,
                action=ActionType.ROLLBACK_TRANSACTION,
                target="pg_session",
                pg_primitive=PG_PRIMITIVE_MAPPING["trace_rollback"],
            )
        )
        idx += 1
    else:
        steps.append(
            ScheduleStep(
                step_index=idx,
                tx_id=gov_tx.tx_id,
                action=ActionType.COMMIT_TRANSACTION,
                target="pg_session",
                pg_primitive=PG_PRIMITIVE_MAPPING["trace_commit"],
            )
        )
        idx += 1

    # 4. Optional delay injection
    if ast_root.timing.delay_ms > 0:
        steps.append(
            ScheduleStep(
                step_index=idx,
                tx_id="system",
                action=ActionType.INJECT_DELAY,
                target="timer",
                parameters={"delay_ms": ast_root.timing.delay_ms},
            )
        )
        idx += 1

    # 5. Transition commit transaction
    commit_tx = ast_root.transactions[1]
    steps.append(
        ScheduleStep(
            step_index=idx,
            tx_id=commit_tx.tx_id,
            action=ActionType.BEGIN_TRANSACTION,
            target="pg_session",
            pg_primitive=PG_PRIMITIVE_MAPPING["trace_begin"],
        )
    )
    idx += 1

    steps.append(
        ScheduleStep(
            step_index=idx,
            tx_id=commit_tx.tx_id,
            action=ActionType.APPLY_TRANSITION,
            target="glhs_assertion",
            parameters={"entity": ast_root.entity_config.value},
            pg_primitive=PG_PRIMITIVE_MAPPING["apply_transition"],
        )
    )
    idx += 1

    if ast_root.modifier.modifier == Modifier.RETRY_AFTER_ROLLBACK:
        steps.append(
            ScheduleStep(
                step_index=idx,
                tx_id=commit_tx.tx_id,
                action=ActionType.ROLLBACK_TRANSACTION,
                target="pg_session",
                pg_primitive=PG_PRIMITIVE_MAPPING["trace_rollback"],
            )
        )
        idx += 1
        steps.append(
            ScheduleStep(
                step_index=idx,
                tx_id=commit_tx.tx_id,
                action=ActionType.RETRY_TRANSACTION,
                target="pg_session",
                parameters={"retry": 1},
                pg_primitive=PG_PRIMITIVE_MAPPING["apply_transition"],
            )
        )
        idx += 1

    steps.append(
        ScheduleStep(
            step_index=idx,
            tx_id=commit_tx.tx_id,
            action=ActionType.COMMIT_TRANSACTION,
            target="pg_session",
            pg_primitive=PG_PRIMITIVE_MAPPING["trace_commit"],
        )
    )

    return tuple(steps)


def descriptor_to_steps(desc: ScheduleDescriptor) -> tuple[ScheduleStep, ...]:
    """Helper to convert a ScheduleDescriptor directly to ScheduleSteps via AST."""
    ast_root = lower_descriptor_to_ast(desc)
    return lower_ast_to_steps(ast_root)
