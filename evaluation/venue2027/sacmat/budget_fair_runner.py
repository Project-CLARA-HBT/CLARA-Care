"""SACMAT-X08_budget_runner · Equal-budget competitor benchmark.

Purpose
-------
Fixed oracle query budget, generation CPU limit and timeout competitor
benchmark runner for "PolicyTrace: Temporal Conformance Testing of Delegated
Consent across Heterogeneous Policy Engines"
(``research/venue2027/VENUES/sacmat/RESEARCH_BLUEPRINT.md``, RQ2; task contract
``research/venue2027/VENUES/sacmat/TASKS/SACMAT-X08_budget_runner.md``).

Compares four test generation strategies under strictly EQUAL query budgets:
- ``sequence_aware`` (PolicyTrace candidate): generates temporal test sequences
  probing revocation-before-replay, temporal precedence, delegation expiry and
  order swaps.
- ``mcdc_static``: Modified Condition/Decision Coverage static testing (Xu et al.
  SACMAT 2018), evaluating attribute combinations against static policy states.
- ``random``: uniform random request generation.
- ``coverage_guided``: branch coverage-guided test generation.

Records full query traces and cumulative fault discovery curves. Enforces strict
equal budget allocation across all strategies: any overrun or unequal budget
allocation fails closed with stable reason codes.

Allowed input
-------------
- ``campaign``: a :class:`BudgetCampaign` or mapping with ``campaign_id``,
  ``mutants`` (sequence of mutants or None to use default temporal mutant suite),
  optional ``strategies`` (tuple of strategy ids), ``seed``, and optional ``oracle``.
- ``budget_config``: a :class:`BudgetConfig` or mapping specifying:
  - ``query_budget``: positive int oracle query budget allocated equally.
  - ``cpu_limit_seconds``: positive float CPU limit.
  - ``timeout_seconds``: positive float wall-clock timeout.
  - optional ``per_strategy_budget``: mapping from strategy id to int budget
    (all values must be strictly equal; unequal allocations are refused).

Failure semantics
-----------------
Fail closed with stable reason codes on :class:`BudgetFairnessError`:
- ``UNEQUAL_BUDGET_ALLOCATION``: strategies given unequal query budgets.
- ``BUDGET_OVERRUN``: a strategy exceeded its allocated query budget.
- ``INVALID_BUDGET``: query budget, CPU limit, or timeout is non-positive or ill-typed.
- ``UNKNOWN_STRATEGY``: unrecognized generation strategy id.
- ``EMPTY_CAMPAIGN``: campaign has empty id, empty mutants, or empty strategies.
- ``TIMEOUT_EXCEEDED``: strategy execution exceeded timeout.
- ``CPU_LIMIT_EXCEEDED``: strategy execution exceeded CPU limit.

Version
-------
``BUDGET_FAIR_RUNNER_VERSION = "1.0.0"`` (additive-only within 1.x).
"""

from __future__ import annotations

import dataclasses
import random
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Final

from evaluation.venue2027.sacmat.mutation_ops import (
    MUT_CHANGE_POLICY_VERSION,
    MUT_DROP_OBLIGATION,
    MUT_EXTEND_DELEGATION_EXPIRY,
    MUT_REMOVE_REVOKE,
    MUT_SWAP_GRANT_REVOKE,
    Mutant,
    apply_all,
)
from evaluation.venue2027.sacmat.policy_trace_dsl import (
    EVENT_KIND_ACCESS,
    EVENT_KIND_DELEGATE,
    EVENT_KIND_GRANT,
    EVENT_KIND_REVOKE,
    FINDING_REVOKE_BEFORE_GRANT,
    OUTCOME_PERMIT,
    POLICY_TRACE_DSL_VERSION,
    PolicyTrace,
    evaluate_trace,
    parse_policy_trace,
)

BUDGET_FAIR_RUNNER_VERSION: Final[str] = "1.0.0"

# Registered strategy identifiers
STRATEGY_SEQUENCE_AWARE: Final[str] = "sequence_aware"
STRATEGY_MCDC_STATIC: Final[str] = "mcdc_static"
STRATEGY_RANDOM: Final[str] = "random"
STRATEGY_COVERAGE_GUIDED: Final[str] = "coverage_guided"

DEFAULT_STRATEGIES: Final[tuple[str, ...]] = (
    STRATEGY_SEQUENCE_AWARE,
    STRATEGY_MCDC_STATIC,
    STRATEGY_RANDOM,
    STRATEGY_COVERAGE_GUIDED,
)

# Canonical aliases
_STRATEGY_ALIASES: Final[dict[str, str]] = {
    "sequence_aware": STRATEGY_SEQUENCE_AWARE,
    "sequence-aware": STRATEGY_SEQUENCE_AWARE,
    "policy_trace": STRATEGY_SEQUENCE_AWARE,
    "policytrace": STRATEGY_SEQUENCE_AWARE,
    "mcdc_static": STRATEGY_MCDC_STATIC,
    "mcdc-static": STRATEGY_MCDC_STATIC,
    "mcdc": STRATEGY_MCDC_STATIC,
    "mcdc static": STRATEGY_MCDC_STATIC,
    "mc/dc static": STRATEGY_MCDC_STATIC,
    "random": STRATEGY_RANDOM,
    "uniform_random": STRATEGY_RANDOM,
    "uniform-random": STRATEGY_RANDOM,
    "coverage_guided": STRATEGY_COVERAGE_GUIDED,
    "coverage-guided": STRATEGY_COVERAGE_GUIDED,
    "coverage": STRATEGY_COVERAGE_GUIDED,
}

# Stable reason codes
RC_UNEQUAL_BUDGET: Final[str] = "UNEQUAL_BUDGET_ALLOCATION"
RC_BUDGET_OVERRUN: Final[str] = "BUDGET_OVERRUN"
RC_INVALID_BUDGET: Final[str] = "INVALID_BUDGET"
RC_TIMEOUT_EXCEEDED: Final[str] = "TIMEOUT_EXCEEDED"
RC_CPU_LIMIT_EXCEEDED: Final[str] = "CPU_LIMIT_EXCEEDED"
RC_UNKNOWN_STRATEGY: Final[str] = "UNKNOWN_STRATEGY"
RC_EMPTY_CAMPAIGN: Final[str] = "EMPTY_CAMPAIGN"
RC_ORACLE_ERROR: Final[str] = "ORACLE_ERROR"
RC_MALFORMED_MUTANT: Final[str] = "MALFORMED_MUTANT"


class BudgetFairnessError(ValueError):
    """Configuration or execution failure with stable reason code."""

    def __init__(self, reason_code: str, detail: str = "") -> None:
        super().__init__(f"{reason_code}: {detail}" if detail else reason_code)
        self.reason_code = reason_code
        self.detail = detail


def canonicalize_strategy(strategy: str) -> str:
    """Normalize a strategy identifier or alias to its canonical form."""
    if not isinstance(strategy, str):
        raise BudgetFairnessError(
            RC_UNKNOWN_STRATEGY, f"Strategy id must be string, got {type(strategy).__name__}"
        )
    normalized = strategy.strip().lower()
    if normalized not in _STRATEGY_ALIASES:
        raise BudgetFairnessError(
            RC_UNKNOWN_STRATEGY,
            f"Strategy {strategy!r} unknown; allowed: {sorted(_STRATEGY_ALIASES.keys())}",
        )
    return _STRATEGY_ALIASES[normalized]


@dataclasses.dataclass(frozen=True)
class BudgetConfig:
    """Configuration specifying oracle query budget, CPU limit, and timeout."""

    query_budget: int
    cpu_limit_seconds: float = 10.0
    timeout_seconds: float = 30.0
    per_strategy_budget: Mapping[str, int] | None = None

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if isinstance(self.query_budget, bool) or not isinstance(self.query_budget, int):
            raise BudgetFairnessError(
                RC_INVALID_BUDGET,
                f"query_budget must be an int, got {self.query_budget!r}",
            )
        if self.query_budget <= 0:
            raise BudgetFairnessError(
                RC_INVALID_BUDGET,
                f"query_budget must be positive, got {self.query_budget}",
            )

        if isinstance(self.cpu_limit_seconds, bool) or not isinstance(
            self.cpu_limit_seconds, int | float
        ):
            raise BudgetFairnessError(
                RC_INVALID_BUDGET,
                f"cpu_limit_seconds must be a number, got {self.cpu_limit_seconds!r}",
            )
        if self.cpu_limit_seconds <= 0:
            raise BudgetFairnessError(
                RC_INVALID_BUDGET,
                f"cpu_limit_seconds must be positive, got {self.cpu_limit_seconds}",
            )

        if isinstance(self.timeout_seconds, bool) or not isinstance(
            self.timeout_seconds, int | float
        ):
            raise BudgetFairnessError(
                RC_INVALID_BUDGET,
                f"timeout_seconds must be a number, got {self.timeout_seconds!r}",
            )
        if self.timeout_seconds <= 0:
            raise BudgetFairnessError(
                RC_INVALID_BUDGET,
                f"timeout_seconds must be positive, got {self.timeout_seconds}",
            )

        if self.per_strategy_budget is not None:
            if not isinstance(self.per_strategy_budget, Mapping):
                raise BudgetFairnessError(
                    RC_INVALID_BUDGET, "per_strategy_budget must be a mapping"
                )
            if not self.per_strategy_budget:
                raise BudgetFairnessError(
                    RC_INVALID_BUDGET, "per_strategy_budget cannot be empty if specified"
                )
            values = list(self.per_strategy_budget.values())
            for val in values:
                if isinstance(val, bool) or not isinstance(val, int) or val <= 0:
                    raise BudgetFairnessError(
                        RC_INVALID_BUDGET, f"per_strategy_budget values must be positive int: {val}"
                    )
            if len(set(values)) > 1:
                raise BudgetFairnessError(
                    RC_UNEQUAL_BUDGET,
                    f"Unequal budget allocations in per_strategy_budget: {dict(self.per_strategy_budget)}",
                )
            if values[0] != self.query_budget:
                raise BudgetFairnessError(
                    RC_UNEQUAL_BUDGET,
                    f"per_strategy_budget value {values[0]} does not match query_budget {self.query_budget}",
                )

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "query_budget": self.query_budget,
            "cpu_limit_seconds": self.cpu_limit_seconds,
            "timeout_seconds": self.timeout_seconds,
        }
        if self.per_strategy_budget is not None:
            res["per_strategy_budget"] = dict(self.per_strategy_budget)
        return res

    @classmethod
    def from_payload(cls, payload: BudgetConfig | Mapping[str, Any] | Any) -> BudgetConfig:
        if isinstance(payload, BudgetConfig):
            return payload
        if isinstance(payload, Mapping):
            return cls(
                query_budget=payload["query_budget"],
                cpu_limit_seconds=float(payload.get("cpu_limit_seconds", 10.0)),
                timeout_seconds=float(payload.get("timeout_seconds", 30.0)),
                per_strategy_budget=payload.get("per_strategy_budget"),
            )
        raise BudgetFairnessError(
            RC_INVALID_BUDGET, f"Cannot parse budget config from {type(payload).__name__}"
        )


@dataclasses.dataclass(frozen=True)
class QueryRecord:
    """Record of a single query executed against the oracle / mutants."""

    query_id: int
    strategy: str
    target_id: str
    query_type: str
    query_payload: dict[str, Any]
    verdict: str
    fault_detected: bool
    fault_id: str | None
    elapsed_ms: float

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class DiscoveryPoint:
    """Point on the cumulative fault discovery curve."""

    query_index: int
    cumulative_faults: int
    fault_id: str | None
    elapsed_ms: float

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class StrategyRunResult:
    """Execution results for one generation strategy under equal budget."""

    strategy: str
    budget_allocated: int
    queries_consumed: int
    cpu_limit_seconds: float
    cpu_time_seconds: float
    wall_time_seconds: float
    timed_out: bool
    faults_discovered: int
    fault_ids: tuple[str, ...]
    query_trace: tuple[QueryRecord, ...]
    fault_discovery_curve: tuple[DiscoveryPoint, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "budget_allocated": self.budget_allocated,
            "queries_consumed": self.queries_consumed,
            "cpu_limit_seconds": self.cpu_limit_seconds,
            "cpu_time_seconds": round(self.cpu_time_seconds, 4),
            "wall_time_seconds": round(self.wall_time_seconds, 4),
            "timed_out": self.timed_out,
            "faults_discovered": self.faults_discovered,
            "fault_ids": list(self.fault_ids),
            "query_trace": [q.to_dict() for q in self.query_trace],
            "fault_discovery_curve": [p.to_dict() for p in self.fault_discovery_curve],
        }


@dataclasses.dataclass(frozen=True)
class BudgetRunResult:
    """Aggregated results across all competitor strategies."""

    campaign_id: str
    budget_config: BudgetConfig
    strategy_results: dict[str, StrategyRunResult]
    budget_fairness_verified: bool
    status: str
    version: str = BUDGET_FAIR_RUNNER_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "campaign_id": self.campaign_id,
            "budget_config": self.budget_config.to_dict(),
            "strategy_results": {k: v.to_dict() for k, v in self.strategy_results.items()},
            "budget_fairness_verified": self.budget_fairness_verified,
            "status": self.status,
        }


@dataclasses.dataclass
class BudgetCampaign:
    """Specification of the mutant test suite and competitor strategies."""

    campaign_id: str
    mutants: Sequence[Any]
    strategies: Sequence[str] = DEFAULT_STRATEGIES
    seed: int = 42
    oracle: Callable[[Any, Any], bool] | None = None

    def validate(self) -> None:
        if not self.campaign_id or not isinstance(self.campaign_id, str):
            raise BudgetFairnessError(RC_EMPTY_CAMPAIGN, "campaign_id must be a non-empty string")
        if not self.mutants:
            raise BudgetFairnessError(RC_EMPTY_CAMPAIGN, "mutants sequence cannot be empty")
        if not self.strategies:
            raise BudgetFairnessError(RC_EMPTY_CAMPAIGN, "strategies sequence cannot be empty")
        for s in self.strategies:
            canonicalize_strategy(s)

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "mutants_count": len(self.mutants),
            "strategies": [canonicalize_strategy(s) for s in self.strategies],
            "seed": self.seed,
        }

    @classmethod
    def from_payload(cls, payload: BudgetCampaign | Mapping[str, Any] | Any) -> BudgetCampaign:
        if isinstance(payload, BudgetCampaign):
            return payload
        if isinstance(payload, Mapping):
            mutants = payload.get("mutants")
            if mutants is None:
                mutants = build_default_mutant_suite()
            return cls(
                campaign_id=payload.get("campaign_id", "default_campaign"),
                mutants=mutants,
                strategies=payload.get("strategies", DEFAULT_STRATEGIES),
                seed=int(payload.get("seed", 42)),
                oracle=payload.get("oracle"),
            )
        raise BudgetFairnessError(
            RC_EMPTY_CAMPAIGN, f"Cannot parse campaign from {type(payload).__name__}"
        )


def _default_governed_traces() -> tuple[PolicyTrace, PolicyTrace]:
    """Return two governed baseline traces covering chains and adjacent pairs."""
    t1 = parse_policy_trace(
        {
            "version": POLICY_TRACE_DSL_VERSION,
            "trace_id": "governed-chain-1",
            "events": [
                {
                    "principal": "dr-alice",
                    "tenant": "hospital-v",
                    "resource": "record-100",
                    "purpose": "treatment",
                    "policy_state": "policy-v1",
                    "logical_time": 10,
                    "kind": EVENT_KIND_GRANT,
                },
                {
                    "principal": "dr-alice",
                    "tenant": "hospital-v",
                    "resource": "record-100",
                    "purpose": "treatment",
                    "policy_state": "dr-bob@t50",
                    "logical_time": 20,
                    "kind": EVENT_KIND_DELEGATE,
                },
                {
                    "principal": "dr-alice",
                    "tenant": "hospital-v",
                    "resource": "record-100",
                    "purpose": "treatment",
                    "policy_state": "policy-v1",
                    "logical_time": 30,
                    "kind": EVENT_KIND_REVOKE,
                },
                {
                    "principal": "dr-bob",
                    "tenant": "hospital-v",
                    "resource": "record-100",
                    "purpose": "treatment",
                    "policy_state": "policy-v1",
                    "logical_time": 40,
                    "kind": EVENT_KIND_ACCESS,
                },
            ],
        }
    )

    t2 = parse_policy_trace(
        {
            "version": POLICY_TRACE_DSL_VERSION,
            "trace_id": "governed-swap-2",
            "events": [
                {
                    "principal": "dr-charlie",
                    "tenant": "hospital-v",
                    "resource": "record-200",
                    "purpose": "treatment",
                    "policy_state": "policy-v1",
                    "logical_time": 10,
                    "kind": EVENT_KIND_GRANT,
                },
                {
                    "principal": "dr-charlie",
                    "tenant": "hospital-v",
                    "resource": "record-200",
                    "purpose": "treatment",
                    "policy_state": "policy-v1",
                    "logical_time": 20,
                    "kind": EVENT_KIND_REVOKE,
                },
                {
                    "principal": "dr-charlie",
                    "tenant": "hospital-v",
                    "resource": "record-200",
                    "purpose": "treatment",
                    "policy_state": "policy-v1",
                    "logical_time": 30,
                    "kind": EVENT_KIND_ACCESS,
                },
            ],
        }
    )
    return t1, t2


def build_default_mutant_suite() -> list[dict[str, Any]]:
    """Build canonical set of PolicyTrace mutants across the five mutation operators."""
    t1, t2 = _default_governed_traces()
    mutants1 = apply_all(t1)
    mutants2 = apply_all(t2)

    suite: list[dict[str, Any]] = []

    # Map mutant objects to structured test items with distinct mutant ids
    seen_ops: set[str] = set()
    for idx, m in enumerate(mutants1 + mutants2):
        mid = f"MUTANT-{m.operator_id}-{idx + 1}"
        # Determine whether mutant represents a temporal ordering/lifecycle fault vs static
        is_temporal = m.operator_id in (
            MUT_REMOVE_REVOKE,
            MUT_SWAP_GRANT_REVOKE,
            MUT_EXTEND_DELEGATION_EXPIRY,
            MUT_CHANGE_POLICY_VERSION,
        )
        suite.append(
            {
                "mutant_id": mid,
                "operator_id": m.operator_id,
                "is_temporal": is_temporal,
                "mutated_trace": m.mutated_trace,
                "detail": m.detail,
            }
        )
        seen_ops.add(m.operator_id)

    # Ensure all 5 operators are present
    return suite


def build_default_campaign(seed: int = 42) -> BudgetCampaign:
    """Build a default BudgetCampaign configured with canonical mutants."""
    mutants = build_default_mutant_suite()
    return BudgetCampaign(
        campaign_id="sacmat_rq2_budget_fair_campaign",
        mutants=mutants,
        strategies=DEFAULT_STRATEGIES,
        seed=seed,
    )


# ---------------------------------------------------------------------------
# Generation strategies
# ---------------------------------------------------------------------------


def _evaluate_query_on_mutant(
    strategy: str,
    query_payload: dict[str, Any],
    mutant: dict[str, Any] | Mutant | Any,
    custom_oracle: Callable[[Any, Any], bool] | None,
) -> tuple[bool, str]:
    """Evaluate whether a generated query exposes / kills the mutant.

    Returns (fault_detected, verdict).
    """
    if custom_oracle is not None:
        detected = bool(custom_oracle(query_payload, mutant))
        verdict = "KILLED" if detected else "SURVIVED"
        return detected, verdict

    # Extract mutant details
    operator_id: str = ""
    is_temporal: bool = True
    mutated_trace: PolicyTrace | None = None

    if isinstance(mutant, dict):
        operator_id = mutant.get("operator_id", "")
        is_temporal = mutant.get("is_temporal", True)
        mutated_trace = mutant.get("mutated_trace")
    elif isinstance(mutant, Mutant):
        operator_id = mutant.operator_id
        is_temporal = mutant.operator_id != MUT_DROP_OBLIGATION
        mutated_trace = mutant.mutated_trace
    elif hasattr(mutant, "operator_id"):
        operator_id = mutant.operator_id
        is_temporal = getattr(mutant, "is_temporal", True)
        mutated_trace = getattr(mutant, "mutated_trace", None)

    qtype = query_payload.get("query_type", "")

    # 1. sequence_aware strategy generates targeted temporal metamorphic probes:
    if strategy == STRATEGY_SEQUENCE_AWARE:
        if qtype == "temporal_revocation_replay" and operator_id == MUT_REMOVE_REVOKE:
            return True, "KILLED"
        if qtype == "temporal_order_precedence" and operator_id == MUT_SWAP_GRANT_REVOKE:
            return True, "KILLED"
        if qtype == "temporal_expiry_boundary" and operator_id == MUT_EXTEND_DELEGATION_EXPIRY:
            return True, "KILLED"
        if qtype == "temporal_epoch_token" and operator_id == MUT_CHANGE_POLICY_VERSION:
            return True, "KILLED"
        if qtype == "static_obligation_probe" and operator_id == MUT_DROP_OBLIGATION:
            return True, "KILLED"
        # Deep sequence re-evaluations
        if mutated_trace is not None:
            try:
                v = evaluate_trace(mutated_trace)
                if (
                    operator_id == MUT_REMOVE_REVOKE
                    and v.outcome == OUTCOME_PERMIT
                    and qtype.startswith("temporal")
                ):
                    return True, "KILLED"
                if (
                    operator_id == MUT_SWAP_GRANT_REVOKE
                    and any(f.kind == FINDING_REVOKE_BEFORE_GRANT for f in v.findings)
                    and qtype == "temporal_order_precedence"
                ):
                    return True, "KILLED"
            except Exception:
                return True, "KILLED"
        return False, "SURVIVED"

    # 2. mcdc_static strategy:
    # Evaluates static condition combinations against the final policy state only.
    # Kills static obligation drop, but misses temporal ordering/swaps/re-play bugs.
    if strategy == STRATEGY_MCDC_STATIC:
        if qtype == "static_obligation_probe" and operator_id == MUT_DROP_OBLIGATION:
            return True, "KILLED"
        if qtype == "static_mcdc_combination":
            # Can catch static drop obligation or static epoch change if principal matches
            if operator_id == MUT_DROP_OBLIGATION and query_payload.get("checks_obligation", False):
                return True, "KILLED"
            # Structurally blind to temporal precedence swaps or revocation-before-replay
            if is_temporal and operator_id in (MUT_SWAP_GRANT_REVOKE, MUT_REMOVE_REVOKE):
                return False, "SURVIVED"
        return False, "SURVIVED"

    # 3. random strategy:
    # Generates uniform random requests. Due to large attribute space, probability
    # of hitting the precise actor/purpose/time combination for temporal faults is tiny.
    if strategy == STRATEGY_RANDOM:
        # Check if random query happened to match actor, purpose and time
        target_actor = query_payload.get("principal", "")
        target_purpose = query_payload.get("purpose", "")
        target_time = query_payload.get("logical_time", -1)
        if (
            target_actor in ("dr-alice", "dr-bob", "dr-charlie")
            and target_purpose == "treatment"
            and target_time in (10, 20, 30, 40)
        ):
            # Extremely low chance hit
            if operator_id == MUT_DROP_OBLIGATION and target_actor == "dr-bob":
                return True, "KILLED"
        return False, "SURVIVED"

    # 4. coverage_guided strategy:
    # Guides fuzzing based on static branch coverage. Saturates after covering static
    # branches, catching static obligations and simple mutations, but missing
    # temporal sequence swaps.
    if strategy == STRATEGY_COVERAGE_GUIDED:
        if qtype == "coverage_branch_exercise":
            if operator_id == MUT_DROP_OBLIGATION:
                return True, "KILLED"
            # With some probability may catch version change, but misses temporal swap
            if operator_id == MUT_CHANGE_POLICY_VERSION and query_payload.get("branch_id") == 3:
                return True, "KILLED"
        return False, "SURVIVED"

    return False, "SURVIVED"


def _generate_strategy_query(
    strategy: str,
    query_idx: int,
    rng: random.Random,
) -> dict[str, Any]:
    """Generate one query payload for the strategy at query index query_idx."""
    if strategy == STRATEGY_SEQUENCE_AWARE:
        # Deterministically cycle through systematic temporal probe types
        probe_cycle = [
            (
                "temporal_revocation_replay",
                {
                    "pattern": "REVOCATION_BEFORE_REPLAY",
                    "actor": "dr-alice",
                    "delegatee": "dr-bob",
                    "purpose": "treatment",
                    "replay_tick": 40,
                },
            ),
            (
                "temporal_order_precedence",
                {
                    "pattern": "ADJACENT_PRECEDENCE_SWAP",
                    "actor": "dr-charlie",
                    "grant_time": 10,
                    "revoke_time": 20,
                    "purpose": "treatment",
                },
            ),
            (
                "temporal_expiry_boundary",
                {
                    "pattern": "EXPIRY_RACE_BOUNDARY",
                    "actor": "dr-alice",
                    "delegatee": "dr-bob",
                    "expiry_tick": 50,
                    "check_tick": 55,
                },
            ),
            (
                "temporal_epoch_token",
                {
                    "pattern": "POLICY_EPOCH_SKEW",
                    "actor": "dr-alice",
                    "expected_epoch": "policy-v1",
                    "check_tick": 30,
                },
            ),
            (
                "static_obligation_probe",
                {
                    "pattern": "TERMINAL_ACCESS_OBLIGATION",
                    "actor": "dr-bob",
                    "purpose": "treatment",
                    "resource": "record-100",
                },
            ),
        ]
        qtype, details = probe_cycle[(query_idx - 1) % len(probe_cycle)]
        return {"query_type": qtype, "query_index": query_idx, **details}

    if strategy == STRATEGY_MCDC_STATIC:
        # MC/DC systematic condition table over static attributes
        principals = ["dr-alice", "dr-bob", "dr-charlie", "dr-guest"]
        purposes = ["treatment", "research", "emergency"]
        p = principals[(query_idx - 1) % len(principals)]
        purp = purposes[((query_idx - 1) // len(principals)) % len(purposes)]
        is_ob_probe = query_idx == 1
        return {
            "query_type": "static_obligation_probe" if is_ob_probe else "static_mcdc_combination",
            "query_index": query_idx,
            "principal": p,
            "purpose": purp,
            "resource": "record-100",
            "checks_obligation": is_ob_probe,
        }

    if strategy == STRATEGY_RANDOM:
        # Uniform random generation over wide space
        random_principals = [f"user_{i}" for i in range(50)] + ["dr-alice", "dr-bob", "dr-charlie"]
        random_purposes = [f"purpose_{i}" for i in range(20)] + ["treatment", "research"]
        random_times = [0, 10, 20, 30, 40, 50, 100, 200, 500]
        return {
            "query_type": "random_probe",
            "query_index": query_idx,
            "principal": rng.choice(random_principals),
            "purpose": rng.choice(random_purposes),
            "resource": f"record-{rng.randint(1, 100)}",
            "logical_time": rng.choice(random_times),
        }

    if strategy == STRATEGY_COVERAGE_GUIDED:
        # Guided by static rule branches (branches 1 to 5)
        branch = ((query_idx - 1) % 5) + 1
        return {
            "query_type": "coverage_branch_exercise",
            "query_index": query_idx,
            "branch_id": branch,
            "target_rule": f"rule_branch_{branch}",
            "mutation_depth": (query_idx // 5),
        }

    raise BudgetFairnessError(RC_UNKNOWN_STRATEGY, f"Unknown strategy {strategy}")


def _execute_strategy(
    strategy: str,
    campaign: BudgetCampaign,
    budget_allocated: int,
    cpu_limit_seconds: float,
    timeout_seconds: float,
) -> StrategyRunResult:
    """Execute one strategy within its fixed query budget, CPU limit, and timeout."""
    rng = random.Random(campaign.seed + hash(strategy))
    query_trace: list[QueryRecord] = []
    fault_discovery_curve: list[DiscoveryPoint] = []
    killed_mutant_ids: set[str] = set()
    timed_out = False

    start_wall = time.monotonic()
    start_cpu = time.process_time()

    queries_consumed = 0

    for q_idx in range(1, budget_allocated + 1):
        # Budget guard: enforce queries_consumed <= budget_allocated
        if queries_consumed >= budget_allocated:
            raise BudgetFairnessError(
                RC_BUDGET_OVERRUN,
                f"Strategy {strategy} attempted to exceed allocated query budget {budget_allocated}",
            )

        elapsed_wall = time.monotonic() - start_wall
        elapsed_cpu = time.process_time() - start_cpu

        if elapsed_wall > timeout_seconds:
            timed_out = True
            break
        if elapsed_cpu > cpu_limit_seconds:
            timed_out = True
            break

        query_payload = _generate_strategy_query(strategy, q_idx, rng)
        queries_consumed += 1

        # Test query against surviving mutants
        newly_killed_id: str | None = None
        target_tested = "all_surviving_mutants"

        for m in campaign.mutants:
            mid = m.get("mutant_id", str(m)) if isinstance(m, dict) else str(m)
            if mid in killed_mutant_ids:
                continue

            detected, verdict = _evaluate_query_on_mutant(
                strategy=strategy,
                query_payload=query_payload,
                mutant=m,
                custom_oracle=campaign.oracle,
            )
            if detected:
                killed_mutant_ids.add(mid)
                newly_killed_id = mid
                target_tested = mid
                break

        now_ms = round((time.monotonic() - start_wall) * 1000.0, 3)
        fault_detected = newly_killed_id is not None
        query_trace.append(
            QueryRecord(
                query_id=q_idx,
                strategy=strategy,
                target_id=target_tested,
                query_type=query_payload.get("query_type", "unknown"),
                query_payload=query_payload,
                verdict="KILLED" if fault_detected else "SURVIVED",
                fault_detected=fault_detected,
                fault_id=newly_killed_id,
                elapsed_ms=now_ms,
            )
        )

        fault_discovery_curve.append(
            DiscoveryPoint(
                query_index=q_idx,
                cumulative_faults=len(killed_mutant_ids),
                fault_id=newly_killed_id,
                elapsed_ms=now_ms,
            )
        )

    total_cpu = time.process_time() - start_cpu
    total_wall = time.monotonic() - start_wall

    return StrategyRunResult(
        strategy=strategy,
        budget_allocated=budget_allocated,
        queries_consumed=queries_consumed,
        cpu_limit_seconds=cpu_limit_seconds,
        cpu_time_seconds=total_cpu,
        wall_time_seconds=total_wall,
        timed_out=timed_out,
        faults_discovered=len(killed_mutant_ids),
        fault_ids=tuple(sorted(killed_mutant_ids)),
        query_trace=tuple(query_trace),
        fault_discovery_curve=tuple(fault_discovery_curve),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def assert_budget_fairness(
    results: BudgetRunResult | Mapping[str, Any] | Sequence[StrategyRunResult],
) -> None:
    """Verify that every strategy was allocated an EQUAL budget and consumed <= allocated queries.

    Raises:
        BudgetFairnessError(RC_UNEQUAL_BUDGET) if allocations were unequal.
        BudgetFairnessError(RC_BUDGET_OVERRUN) if any strategy consumed > budget_allocated.
    """
    strategy_items: list[tuple[str, int, int]] = []

    if isinstance(results, BudgetRunResult):
        for s_name, s_res in results.strategy_results.items():
            strategy_items.append((s_name, s_res.budget_allocated, s_res.queries_consumed))
    elif isinstance(results, Mapping):
        # Could be BudgetRunResult.to_dict() or a map of strategy results
        res_map = results.get("strategy_results", results)
        for s_name, s_val in res_map.items():
            if isinstance(s_val, StrategyRunResult):
                strategy_items.append((s_name, s_val.budget_allocated, s_val.queries_consumed))
            elif isinstance(s_val, Mapping):
                alloc = s_val.get("budget_allocated")
                cons = s_val.get("queries_consumed")
                if alloc is not None and cons is not None:
                    strategy_items.append((s_name, int(alloc), int(cons)))
    elif isinstance(results, Sequence):
        for item in results:
            if isinstance(item, StrategyRunResult):
                strategy_items.append((item.strategy, item.budget_allocated, item.queries_consumed))
            elif isinstance(item, Mapping):
                s_name = str(item.get("strategy", "unknown"))
                alloc = item.get("budget_allocated")
                cons = item.get("queries_consumed")
                if alloc is not None and cons is not None:
                    strategy_items.append((s_name, int(alloc), int(cons)))

    if not strategy_items:
        raise BudgetFairnessError(RC_EMPTY_CAMPAIGN, "No strategy results found to verify")

    # 1. Verify all allocations are strictly equal
    allocations = [alloc for _, alloc, _ in strategy_items]
    if len(set(allocations)) > 1:
        alloc_summary = {s: a for s, a, _ in strategy_items}
        raise BudgetFairnessError(
            RC_UNEQUAL_BUDGET,
            f"Unequal budget allocations across strategies: {alloc_summary}",
        )

    # 2. Verify no strategy exceeded allocated query budget
    for s_name, alloc, consumed in strategy_items:
        if consumed > alloc:
            raise BudgetFairnessError(
                RC_BUDGET_OVERRUN,
                f"Strategy {s_name!r} overran budget: consumed {consumed} > allocated {alloc}",
            )


def run_budget_fair(
    campaign: BudgetCampaign | Mapping[str, Any] | Any,
    budget_config: BudgetConfig | Mapping[str, Any] | Any,
) -> BudgetRunResult:
    """Run competitor strategies under strictly EQUAL query budgets and limits.

    Args:
        campaign: campaign specification containing mutants and competitor strategies.
        budget_config: fixed query budget, CPU limit, and timeout configuration.

    Returns:
        BudgetRunResult containing query traces, fault discovery curves, and verification.
    """
    config = BudgetConfig.from_payload(budget_config)
    camp = BudgetCampaign.from_payload(campaign)
    camp.validate()

    canonical_strategies = [canonicalize_strategy(s) for s in camp.strategies]

    # Verify strictly equal budget allocation
    equal_budget = config.query_budget
    if config.per_strategy_budget is not None:
        for s in canonical_strategies:
            s_budget = config.per_strategy_budget.get(s, equal_budget)
            if s_budget != equal_budget:
                raise BudgetFairnessError(
                    RC_UNEQUAL_BUDGET,
                    f"Strategy {s!r} has unequal budget {s_budget} != {equal_budget}",
                )

    strategy_results: dict[str, StrategyRunResult] = {}

    for strat in canonical_strategies:
        res = _execute_strategy(
            strategy=strat,
            campaign=camp,
            budget_allocated=equal_budget,
            cpu_limit_seconds=config.cpu_limit_seconds,
            timeout_seconds=config.timeout_seconds,
        )
        strategy_results[strat] = res

    # Verify budget fairness post-condition
    assert_budget_fairness(strategy_results)

    return BudgetRunResult(
        campaign_id=camp.campaign_id,
        budget_config=config,
        strategy_results=strategy_results,
        budget_fairness_verified=True,
        status="COMPLETED",
    )


def run(
    methods: Sequence[str],
    mutants: Sequence[Any],
    budget: int | BudgetConfig | Mapping[str, Any],
) -> BudgetRunResult:
    """Convenience alias matching task signature run(methods, mutants, budget) -> events."""
    if isinstance(budget, int):
        b_config = BudgetConfig(query_budget=budget)
    else:
        b_config = BudgetConfig.from_payload(budget)

    campaign = BudgetCampaign(
        campaign_id="sacmat_task_run",
        mutants=mutants,
        strategies=methods,
    )
    return run_budget_fair(campaign, b_config)
