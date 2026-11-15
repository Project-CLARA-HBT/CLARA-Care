"""SACMAT-runner · Uniform arm executor for SACMAT 2027.

Purpose
-------
Uniform multi-arm execution runner for "PolicyTrace: Temporal Conformance
Testing of Delegated Consent across Heterogeneous Policy Engines"
(``research/venue2027/VENUES/sacmat/RESEARCH_BLUEPRINT.md``, RQ1-RQ3; task
contract ``research/venue2027/VENUES/sacmat/TASKS/SACMAT-runner.md``).

Executes all candidate and baseline policy-engine arms over the temporal trace
corpus with equal configuration, balanced paired case/seed plan, and strict
per-pair time limit. Reuses the audited shared deterministic harness
(:mod:`evaluation.venue2027._shared.harness`).

Records every (arm, case) cell:
- No silent dropping: crashes/exceptions become ``EXECUTION_ERROR`` rows.
- Timeouts become ``TIMEOUT`` rows.
- Mutually exclusive outcomes per ``GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md`` rule 4.
- Refuses unequal configuration, seed drift, or missing arms.

Allowed input
-------------
A :class:`CampaignConfig` or JSON-serializable mapping specifying:
- ``campaign_id``: unique identifier string.
- ``source_commit``: 40-hex git commit SHA.
- ``seeds``: tuple/sequence of ints, or single int expanded uniformly.
- ``arm_ids``: optional sequence of arm IDs (defaults to registered engine arms).
- ``cases``: optional sequence of trace case mappings or paths.
- ``per_pair_timeout_seconds``: positive float timeout per execution cell.

Failure semantics
-----------------
Fail closed with stable reason codes on :class:`RunnerError`:
- ``CONFIG_NOT_A_MAPPING`` — config is not a dict or CampaignConfig.
- ``UNEQUAL_CONFIG_REFUSED`` — seed drift or mismatched parameters between arms.
- ``EMPTY_CASES`` — no cases provided or corpus empty.
- ``EMPTY_ARMS`` — no arms requested or registered.
- ``UNKNOWN_ARM`` — arm requested is not registered.
- ``INVALID_TIMEOUT`` — timeout is non-positive or not a number.

Version
-------
``RUNNER_VERSION = "1.0.0"`` (additive-only within 1.x).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from evaluation.venue2027._shared import harness
from evaluation.venue2027._shared.harness import (
    ArmAdapter,
    Campaign,
    HarnessError,
    Outcome,
    RunBundle,
    RunContext,
)
from evaluation.venue2027.sacmat import ablations, candidate, temporal_trace_generator

RUNNER_VERSION: Final[str] = "1.0.0"

# Registered default engine arms for SACMAT campaign execution
ARM_CANDIDATE: Final[str] = "candidate"
ARM_CEDAR: Final[str] = "cedar"
ARM_OPENFGA: Final[str] = "openfga"
ARM_OPA: Final[str] = "opa"
ARM_STATIC_ONLY: Final[str] = "ablation_static_only"
ARM_NO_DIFFERENTIAL: Final[str] = "ablation_no_differential"
ARM_NO_EXPIRY_CHECK: Final[str] = "ablation_no_expiry_check"
ARM_COMMON_SAFETY_GATE: Final[str] = "ablation_common_safety_gate"

REGISTERED_ARMS: Final[tuple[str, ...]] = (
    ARM_CANDIDATE,
    ARM_CEDAR,
    ARM_OPENFGA,
    ARM_OPA,
    ARM_STATIC_ONLY,
    ARM_NO_DIFFERENTIAL,
    ARM_NO_EXPIRY_CHECK,
    ARM_COMMON_SAFETY_GATE,
)

CORE_ENGINE_ARMS: Final[tuple[str, ...]] = (
    ARM_CANDIDATE,
    ARM_CEDAR,
    ARM_OPENFGA,
    ARM_OPA,
)


class RunnerError(ValueError):
    """Configuration or execution failure with stable reason code."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


@dataclasses.dataclass(frozen=True)
class CampaignConfig:
    """Configuration for running a SACMAT experimental campaign."""

    campaign_id: str
    source_commit: str
    seed: int
    arm_ids: tuple[str, ...] = CORE_ENGINE_ARMS
    per_pair_timeout_seconds: float = 60.0
    cases: tuple[Mapping[str, Any], ...] | None = None
    workers: int = 1
    journal_path: Path | str | None = None

    def validate(self) -> None:
        if not self.campaign_id:
            raise RunnerError("EMPTY_SCOPE", "campaign_id must be non-empty")
        if (
            len(self.source_commit) != 40
            or any(c not in "0123456789abcdef" for c in self.source_commit)
        ):
            raise RunnerError(
                "MISSING_SOURCE_SHA", "source_commit must be a 40-hex git SHA"
            )
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise RunnerError("INVALID_SEED", "seed must be an int")
        if not self.arm_ids:
            raise RunnerError("EMPTY_ARMS", "arm_ids must not be empty")
        if len(set(self.arm_ids)) != len(self.arm_ids):
            raise RunnerError("DUPLICATE_ARM", "arm_ids must be unique")
        for arm_id in self.arm_ids:
            if arm_id not in REGISTERED_ARMS:
                raise RunnerError(
                    "UNKNOWN_ARM",
                    f"arm_id {arm_id!r} not in registered arms {REGISTERED_ARMS}",
                )
        if (
            isinstance(self.per_pair_timeout_seconds, bool)
            or not isinstance(self.per_pair_timeout_seconds, int | float)
            or self.per_pair_timeout_seconds <= 0
        ):
            raise RunnerError(
                "INVALID_TIMEOUT", "per_pair_timeout_seconds must be positive"
            )


def build_default_corpus(seed: int = 2027) -> list[dict[str, Any]]:
    """Build or load the default temporal trace corpus cases."""
    traces = temporal_trace_generator.generate_traces(
        seed=seed, depth=8, hops=3, mutation_points=4
    )
    cases: list[dict[str, Any]] = []
    for t in traces:
        cases.append(
            {
                "case_id": str(t["trace_id"]),
                "trace": dict(t),
                "expected_outcome": t.get("expected_outcome", "PERMIT"),
                "expected_findings": list(t.get("expected_findings", [])),
                "bug_class": t.get("bug_class"),
                "role": t.get("role", "valid"),
            }
        )
    return cases


def build_oracle(cases_by_id: Mapping[str, Mapping[str, Any]]) -> harness.Oracle:
    """Return an independent adjudicator callable for the harness."""

    def adjudicate(
        case_id: str, arm_id: str, observed: str, detail: str
    ) -> dict[str, Any]:
        case = cases_by_id.get(case_id, {})
        expected_dsl = case.get("expected_outcome", "PERMIT")
        findings = case.get("expected_findings", [])
        expected_outcome = (
            "ADMIT" if expected_dsl == "PERMIT" and not findings else "REJECT"
        )
        return {
            "oracle_id": "sacmat-temporal-oracle-v1",
            "expected_outcome": expected_outcome,
            "decision": "PASS" if observed == expected_outcome else "FAIL",
            "candidate_reason_code_ignored": True,
        }

    return adjudicate


def _make_candidate_arm() -> ArmAdapter:
    def arm(case_ctx: Mapping[str, Any], ctx: RunContext) -> Outcome:
        return candidate.run_candidate(case_ctx, ctx)

    return arm


def _make_single_engine_arm(engine_id: str) -> ArmAdapter:
    def arm(case_ctx: Mapping[str, Any], ctx: RunContext) -> Outcome:
        trace_payload = case_ctx.get("trace", case_ctx)
        res = candidate.ablation_single_engine(trace_payload, engine=engine_id)
        if not res.timeline:
            return Outcome(
                observed_outcome="INDETERMINATE",
                counted_as_success=False,
                detail=f"{engine_id}|no_access_events",
            )
        dec = res.timeline[-1]["decisions"].get(engine_id, "NOT_APPLICABLE")
        observed = "ADMIT" if dec == "PERMIT" else "REJECT"
        return Outcome(
            observed_outcome=observed,
            counted_as_success=True,
            detail=f"{engine_id}|decision={dec}|status={res.status}",
        )

    return arm


def _make_ablation_arm(variant_id: str) -> ArmAdapter:
    def arm(case_ctx: Mapping[str, Any], ctx: RunContext) -> Outcome:
        return ablations.run_ablation(variant_id, case_ctx)

    return arm


def build_arm_registry() -> dict[str, ArmAdapter]:
    """Return the map of registered arm IDs to executable adapter callables."""
    registry: dict[str, ArmAdapter] = {
        ARM_CANDIDATE: _make_candidate_arm(),
        ARM_CEDAR: _make_single_engine_arm("cedar"),
        ARM_OPENFGA: _make_single_engine_arm("openfga"),
        ARM_OPA: _make_single_engine_arm("opa"),
        ARM_STATIC_ONLY: _make_ablation_arm(ablations.VARIANT_STATIC_ONLY),
        ARM_NO_DIFFERENTIAL: _make_ablation_arm(ablations.VARIANT_NO_DIFFERENTIAL),
        ARM_NO_EXPIRY_CHECK: _make_ablation_arm(ablations.VARIANT_NO_EXPIRY_CHECK),
        ARM_COMMON_SAFETY_GATE: _make_ablation_arm(
            ablations.VARIANT_COMMON_SAFETY_GATE
        ),
    }
    return registry


def _parse_config(raw_config: Any) -> CampaignConfig:
    if isinstance(raw_config, CampaignConfig):
        return raw_config
    if not isinstance(raw_config, Mapping):
        raise RunnerError(
            "CONFIG_NOT_A_MAPPING",
            f"config must be a mapping or CampaignConfig, got {type(raw_config).__name__}",
        )

    # Check for seed drift or unequal config in raw dictionary
    if "seeds" in raw_config:
        raw_seeds = raw_config["seeds"]
        if isinstance(raw_seeds, Sequence) and not isinstance(raw_seeds, str | bytes):
            if len(set(raw_seeds)) > 1:
                raise RunnerError(
                    "UNEQUAL_CONFIG_REFUSED",
                    f"seed drift detected across arms: {list(raw_seeds)}",
                )
            seed = int(raw_seeds[0]) if raw_seeds else 0
        else:
            seed = int(raw_seeds)
    elif "seed" in raw_config:
        seed = int(raw_config["seed"])
    else:
        seed = 2027

    campaign_id = str(raw_config.get("campaign_id", ""))
    source_commit = str(raw_config.get("source_commit", ""))
    arm_ids_raw = raw_config.get("arm_ids", CORE_ENGINE_ARMS)
    arm_ids = tuple(str(a) for a in arm_ids_raw)
    timeout = float(raw_config.get("per_pair_timeout_seconds", 60.0))
    cases = raw_config.get("cases")
    if cases is not None:
        cases = tuple(dict(c) for c in cases)
    workers = int(raw_config.get("workers", 1))
    journal_path = raw_config.get("journal_path")

    # Guard: per-arm timeouts must not differ
    if "per_arm_timeouts" in raw_config:
        per_arm_timeouts = raw_config["per_arm_timeouts"]
        if len(set(per_arm_timeouts.values())) > 1:
            raise RunnerError(
                "UNEQUAL_CONFIG_REFUSED",
                f"per-arm timeout differences refused: {per_arm_timeouts}",
            )

    return CampaignConfig(
        campaign_id=campaign_id,
        source_commit=source_commit,
        seed=seed,
        arm_ids=arm_ids,
        per_pair_timeout_seconds=timeout,
        cases=cases,
        workers=workers,
        journal_path=journal_path,
    )


def run_campaign(config: Any) -> RunBundle:
    """Execute all engine arms over the temporal trace corpus.

    Parameters
    ----------
    config:
        A :class:`CampaignConfig` or equivalent mapping defining the campaign.

    Returns
    -------
    RunBundle:
        Aggregated, JSON-serializable harness bundle of execution records.
    """
    cfg = _parse_config(config)
    cfg.validate()

    cases = cfg.cases if cfg.cases is not None else build_default_corpus(cfg.seed)
    if not cases:
        raise RunnerError("EMPTY_CASES", "case corpus is empty")

    case_ids = tuple(str(c["case_id"]) for c in cases)
    cases_by_id: dict[str, Mapping[str, Any]] = {
        str(c["case_id"]): c for c in cases
    }

    seeds = tuple(cfg.seed for _ in cfg.arm_ids)

    harness_campaign = Campaign(
        campaign_id=cfg.campaign_id,
        case_ids=case_ids,
        arm_ids=cfg.arm_ids,
        seeds=seeds,
        source_commit=cfg.source_commit,
        per_pair_timeout_seconds=cfg.per_pair_timeout_seconds,
    )

    all_arms = build_arm_registry()
    active_arms: dict[str, ArmAdapter] = {}
    for arm_id in cfg.arm_ids:
        adapter = all_arms[arm_id]

        def wrapped_adapter(
            case_ctx: Mapping[str, Any],
            ctx: RunContext,
            _arm_fn: ArmAdapter = adapter,
        ) -> Outcome | dict[str, Any] | str:
            cid = case_ctx["case_id"]
            full_case = dict(cases_by_id[cid])
            full_case["campaign_id"] = ctx.campaign_id
            full_case["source_commit"] = ctx.source_commit
            return _arm_fn(full_case, ctx)

        active_arms[arm_id] = wrapped_adapter

    oracle_fn = build_oracle(cases_by_id)

    try:
        bundle = harness.execute(
            harness_campaign,
            active_arms,
            oracle_fn,
            workers=cfg.workers,
            journal_path=cfg.journal_path,
        )
    except HarnessError as exc:
        raise RunnerError(exc.reason_code, exc.detail) from exc

    return bundle
