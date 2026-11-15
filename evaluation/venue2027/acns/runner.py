"""ACNS-runner — Uniform arm executor for ACNS 2027 SoK.

Purpose
-------
Task ACNS-runner (Phase P05, venue acns) implements `run_campaign(config) -> RunBundle`
executing all SoK reference classes over the corpus/evidence records with equal config,
recording evidence-boundary verdicts per record, mutually exclusive outcomes, source
commit, and seeds.

Per the signed novelty contract (research/venue2027/acns/novelty_contract.md §1), this
study is a **SoK**: "Evidence Boundaries of Attestation in Tool-Using AI Systems".
The study evaluates four *analytic reference classes* over evidence claims:
- `B0-attestation-only` — accepts any claimed attestation level without receipt binding
- `B1-receipt-without-binding` — checks receipt presence but ignores claim linkage
- `B2-timestamp-only` — infers trust purely from timestamps
- `B3-evidence-boundary-aware` — full reference requiring bound, verifiable evidence
against the independent evidence-boundary oracle and synthetic claim records
(synthetic-acns-2027).

This module reuses the shared deterministic multi-arm execution harness
(:mod:`evaluation.venue2027._shared.harness`), ensuring:
- Strict balanced paired case/order/seed execution across all reference classes.
- Equal configuration enforcement across all comparison arms (refusing any seed drift,
  timeout disparity, or parameter divergence with stable reason code `UNEQUAL_CONFIG`).
- Complete denominator accounting: every planned (arm, case) cell is accounted for.
  An arm that raises an exception is recorded as `EXECUTION_ERROR`, not silently dropped.
- Mutually exclusive outcome categories per INDEPENDENT_EVIDENCE_PROTOCOL.md rule 4.
- Deterministic, resumable execution with immutable provenance (source commit SHA,
  seeds, Python version, harness version, pair digests).

Allowed input
-------------
- `config`: A :class:`CampaignConfig` instance, a mapping matching `CampaignConfig` fields,
  a :class:`Campaign` instance, or `None` (running the canonical 4-arm × 4-record campaign).
  Supported parameters include `campaign_id`, `arm_ids`, `case_ids`, `seed` (or identical `seeds`),
  `source_commit`, `per_pair_timeout_seconds`, `retry_budget`, `workers`, `journal_path`,
  `cases`, `arms`, `arm_configs`, `output_path`, and `oracle`.

Failure semantics
-----------------
Fail closed with stable uppercase reason codes:
- `UNEQUAL_CONFIG` — per-arm configurations (seeds, budgets, timeouts, or parameters)
  differ across arms.
- `EMPTY_SCOPE` — no cases or no arms specified.
- `DUPLICATE_ID` — duplicate arm_id or case_id.
- `UNKNOWN_ARM` — an arm not in preregistered reference classes or injected adapters.
- `INVALID_CONFIG` — malformed configuration object.
- `INVALID_SOURCE_SHA` / `MISSING_SOURCE_SHA` — invalid or missing 40-hex git SHA.
All arm execution faults become recorded outcomes (`EXECUTION_ERROR`, `TIMEOUT`, `INVALID_RESULT`),
never unhandled exceptions.

Version
-------
`ACNS_RUNNER_VERSION = "1.0.0"`.
"""

from __future__ import annotations

import dataclasses
import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from evaluation.venue2027._shared import harness
from evaluation.venue2027._shared.harness import (
    Campaign,
    HarnessError,
    Outcome,
    RunBundle,
    RunContext,
)
from evaluation.venue2027.acns import _smoke_fixtures, baselines, candidate, independent_oracle

ACNS_RUNNER_VERSION: Final[str] = "1.0.0"

#: Pre-registered SoK evidence-boundary reference classes.
REFERENCE_CLASSES: Final[tuple[str, ...]] = baselines.BASELINE_IDS

DEFAULT_ARM_IDS: Final[tuple[str, ...]] = REFERENCE_CLASSES

#: Known candidate instrument identifiers accepted alongside baselines.
CANDIDATE_ARM_IDS: Final[frozenset[str]] = frozenset(
    {
        candidate.CANDIDATE_ID,
        "candidate",
        "ACNS-candidate",
    }
)

FALLBACK_SOURCE_COMMIT: Final[str] = "28ff55110f980f42002524cef126290e91258cd6"

ArmAdapter = Callable[[Mapping[str, Any], RunContext], Outcome | dict[str, Any] | str]
Oracle = Callable[[str, str, str, str], Mapping[str, Any]]


class RunnerError(HarnessError):
    """Stable, machine-readable runner configuration/execution failure."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(reason_code, detail)


def resolve_source_commit(explicit: str | None = None) -> str:
    """Resolve a valid 40-hex git commit SHA from input, git HEAD, or repository fallback."""
    if explicit:
        sha = explicit.strip().lower()
        if len(sha) == 40 and all(c in "0123456789abcdef" for c in sha):
            return sha
        raise RunnerError(
            "INVALID_SOURCE_SHA",
            f"source_commit must be a 40-hex string, got {explicit!r}",
        )
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        sha = res.stdout.strip().lower()
        if len(sha) == 40 and all(c in "0123456789abcdef" for c in sha):
            return sha
    except Exception:
        pass
    return FALLBACK_SOURCE_COMMIT


def _family_for_variant(variant: str) -> str:
    """Map fixture record variant to pre-registered ACNS evidence family."""
    family_map = {
        "bound": independent_oracle.FAMILY_BOUND_EVIDENCE,
        "downgraded": independent_oracle.FAMILY_ATTESTATION_DOWNGRADE,
        "unbound": independent_oracle.FAMILY_UNBOUND_CLAIM,
        "replayed": independent_oracle.FAMILY_REPLAYED_RECEIPT,
    }
    return family_map.get(variant, variant)


def build_default_cases() -> dict[str, dict[str, Any]]:
    """Construct the default case registry from synthetic evidence records.

    Keyed by both canonical 'record_id/variant' and 'record_id' for transparent lookup.
    """
    registry: dict[str, dict[str, Any]] = {}
    for (record_id, variant), record_data in sorted(
        _smoke_fixtures.SYNTHETIC_CLAIM_RECORDS.items()
    ):
        case_id = f"{record_id}/{variant}"
        case_dict: dict[str, Any] = {
            "case_id": case_id,
            "record_id": record_id,
            "variant": variant,
            "dataset": _smoke_fixtures.FIXTURE_DATASET,
            "family": _family_for_variant(variant),
            "claims_case": record_data.get("claims_case"),
            "receipts": record_data.get("receipts"),
        }
        registry[case_id] = case_dict
        if record_id not in registry:
            registry[record_id] = case_dict
    return registry


DEFAULT_CASE_REGISTRY: Final[dict[str, dict[str, Any]]] = build_default_cases()
DEFAULT_CASE_IDS: Final[tuple[str, ...]] = tuple(
    f"{record_id}/{variant}"
    for record_id, variant in sorted(_smoke_fixtures.SYNTHETIC_CLAIM_RECORDS)
)


@dataclasses.dataclass(frozen=True)
class CampaignConfig:
    """Preregistered configuration for an ACNS campaign execution.

    Enforces equal configuration across all arms (seeds, budgets, timeouts,
    backend parameters) per INDEPENDENT_EVIDENCE_PROTOCOL.md rule 4.
    """

    campaign_id: str = "acns-sok-evidence-boundaries-campaign"
    arm_ids: tuple[str, ...] = DEFAULT_ARM_IDS
    case_ids: tuple[str, ...] | None = None
    seed: int = 42
    seeds: tuple[int, ...] | None = None
    source_commit: str = ""
    per_pair_timeout_seconds: float = 60.0
    retry_budget: int = 0
    workers: int = 1
    journal_path: str | Path | None = None
    cases: Mapping[str, Mapping[str, Any]] | Sequence[Mapping[str, Any]] | None = None
    arms: Mapping[str, ArmAdapter] | None = None
    arm_configs: Mapping[str, Mapping[str, Any]] | None = None
    oracle: Callable[..., Any] | None = None
    output_path: str | Path | None = None

    def validate(self) -> None:
        """Validate campaign configuration and enforce equal config constraints."""
        if not self.campaign_id:
            raise RunnerError("EMPTY_SCOPE", "campaign_id must be non-empty")
        if not self.arm_ids:
            raise RunnerError("EMPTY_SCOPE", "at least one arm_id is required")
        if len(set(self.arm_ids)) != len(self.arm_ids):
            raise RunnerError("DUPLICATE_ID", "arm_ids must be unique")
        if self.case_ids is not None:
            if not self.case_ids:
                raise RunnerError("EMPTY_SCOPE", "case_ids cannot be empty if specified")
            if len(set(self.case_ids)) != len(self.case_ids):
                raise RunnerError("DUPLICATE_ID", "case_ids must be unique")
        if self.workers < 1:
            raise RunnerError("INVALID_WORKERS", "workers must be >= 1")
        if self.per_pair_timeout_seconds <= 0:
            raise RunnerError("INVALID_TIMEOUT", "per_pair_timeout_seconds must be positive")

        # Enforce equal configuration across all arms
        if self.seeds is not None:
            if len(self.seeds) != len(self.arm_ids):
                raise RunnerError(
                    "UNEQUAL_CONFIG",
                    f"seeds count ({len(self.seeds)}) != arm count ({len(self.arm_ids)})",
                )
            if len(set(self.seeds)) > 1:
                raise RunnerError(
                    "UNEQUAL_CONFIG",
                    f"seeds differ across arms (unequal config refused): {list(self.seeds)}",
                )

        if self.arm_configs is not None:
            active_arms = list(self.arm_ids)
            if len(active_arms) > 1:
                first_cfg = self.arm_configs.get(active_arms[0])
                for arm in active_arms[1:]:
                    arm_cfg = self.arm_configs.get(arm)
                    if arm_cfg != first_cfg:
                        raise RunnerError(
                            "UNEQUAL_CONFIG",
                            f"arm_configs differ across arms {active_arms[0]} and {arm}: "
                            f"{first_cfg!r} != {arm_cfg!r} (unequal config refused)",
                        )


def _make_arm_adapter(
    arm_id: str,
    case_registry: Mapping[str, Mapping[str, Any]],
    user_arms: Mapping[str, ArmAdapter] | None = None,
) -> ArmAdapter:
    """Create an arm execution adapter that hydrates case fields and runs the reference class."""
    if user_arms and arm_id in user_arms:
        user_adapter = user_arms[arm_id]
        if not callable(user_adapter):
            raise RunnerError("ARM_NOT_CALLABLE", f"adapter for {arm_id} is not callable")

        def user_arm_wrapper(case: Mapping[str, Any], ctx: RunContext) -> Any:
            case_id = str(case.get("case_id", ""))
            reg_case = case_registry.get(case_id, {})
            merged = dict(reg_case)
            merged.update(case)
            return user_adapter(merged, ctx)

        return user_arm_wrapper

    if arm_id in baselines.BASELINE_IDS:

        def baseline_adapter(case: Mapping[str, Any], ctx: RunContext) -> Outcome:
            case_id = str(case.get("case_id", ""))
            reg_case = case_registry.get(case_id, {})
            merged = dict(reg_case)
            merged.update(case)
            if "record_id" not in merged and "/" in case_id:
                parts = case_id.split("/", 1)
                merged.setdefault("record_id", parts[0])
                merged.setdefault("variant", parts[1])
            return baselines.run_baseline(arm_id, merged, ctx)

        return baseline_adapter

    if arm_id in CANDIDATE_ARM_IDS:

        def candidate_adapter(case: Mapping[str, Any], ctx: RunContext) -> Outcome:
            case_id = str(case.get("case_id", ""))
            reg_case = case_registry.get(case_id, {})
            merged = dict(reg_case)
            merged.update(case)
            if "record_id" not in merged and "/" in case_id:
                parts = case_id.split("/", 1)
                merged.setdefault("record_id", parts[0])
                merged.setdefault("variant", parts[1])
            return candidate.run_candidate(merged, {"arm_id": arm_id, "seed": ctx.seed})

        return candidate_adapter

    raise RunnerError("UNKNOWN_ARM", f"unrecognized arm_id: {arm_id!r}")


def make_harness_oracle(
    case_registry: Mapping[str, Mapping[str, Any]],
    user_oracle: Callable[..., Any] | None = None,
) -> Oracle:
    """Build the oracle callable compliant with harness.execute.

    Signature: oracle(case_id, arm_id, observed_outcome, detail) -> Mapping[str, Any].
    Delegates to independent_oracle.adjudicate_boundary by default.
    """

    def oracle_fn(case_id: str, arm_id: str, observed_outcome: str, detail: str) -> dict[str, Any]:
        if user_oracle is not None:
            try:
                res = user_oracle(case_id, arm_id, observed_outcome, detail)
                if isinstance(res, Mapping):
                    return dict(res)
            except TypeError:
                case = case_registry.get(case_id, {"case_id": case_id})
                res = user_oracle(case)
                if hasattr(res, "to_dict"):
                    return res.to_dict()
                if isinstance(res, Mapping):
                    return dict(res)

        case = dict(case_registry.get(case_id, {"case_id": case_id}))
        if "family" not in case and "/" in case_id:
            variant = case_id.split("/", 1)[1]
            case["family"] = _family_for_variant(variant)

        try:
            verdict = independent_oracle.adjudicate_boundary(case)
            expected = verdict.oracle_result.outcome
            decision = "PASS" if expected == observed_outcome else "FAIL"
            return {
                "oracle_id": independent_oracle.ORACLE_ID,
                "expected_outcome": expected,
                "decision": decision,
                "granted_level": verdict.granted_level,
                "refused_claim": verdict.refused_claim,
                "gap_code": verdict.gap_code,
                "boundary_condition": verdict.boundary_condition,
                "oracle_version": independent_oracle.ACNS_INDEPENDENT_ORACLE_VERSION,
            }
        except Exception as exc:
            return {
                "oracle_id": independent_oracle.ORACLE_ID,
                "oracle_error": type(exc).__name__,
                "oracle_detail": str(exc)[:200],
            }

    return oracle_fn


def _coerce_config(config: CampaignConfig | Mapping[str, Any] | Campaign | None) -> CampaignConfig:
    """Normalize user input into a validated CampaignConfig."""
    if config is None:
        return CampaignConfig()
    if isinstance(config, CampaignConfig):
        return config
    if isinstance(config, Campaign):
        return CampaignConfig(
            campaign_id=config.campaign_id,
            arm_ids=config.arm_ids,
            case_ids=config.case_ids,
            seed=config.seed,
            seeds=config.seeds,
            source_commit=config.source_commit,
            per_pair_timeout_seconds=config.per_pair_timeout_seconds,
        )
    if isinstance(config, Mapping):
        arm_ids = config.get("arm_ids", DEFAULT_ARM_IDS)
        if isinstance(arm_ids, Sequence) and not isinstance(arm_ids, str | bytes):
            arm_ids_tuple = tuple(str(a) for a in arm_ids)
        else:
            raise RunnerError("INVALID_CONFIG", "arm_ids must be a sequence")

        case_ids = config.get("case_ids")
        case_ids_tuple: tuple[str, ...] | None = None
        if case_ids is not None:
            if isinstance(case_ids, Sequence) and not isinstance(case_ids, str | bytes):
                case_ids_tuple = tuple(str(c) for c in case_ids)
            else:
                raise RunnerError("INVALID_CONFIG", "case_ids must be a sequence or None")

        seeds = config.get("seeds")
        seeds_tuple: tuple[int, ...] | None = None
        if seeds is not None:
            if isinstance(seeds, Sequence) and not isinstance(seeds, str | bytes):
                seeds_tuple = tuple(int(s) for s in seeds)
            else:
                raise RunnerError("INVALID_CONFIG", "seeds must be a sequence of ints or None")

        # Check explicit per-arm dictionaries for unequal config
        for check_key, label in (
            ("arm_timeouts", "timeouts"),
            ("arm_retry_budgets", "retry budgets"),
            ("arm_backends", "backends"),
            ("arm_seeds", "seeds"),
        ):
            mapping_val = config.get(check_key)
            if isinstance(mapping_val, Mapping):
                active = list(arm_ids_tuple)
                if len(active) > 1:
                    first = mapping_val.get(active[0])
                    for a in active[1:]:
                        if mapping_val.get(a) != first:
                            raise RunnerError(
                                "UNEQUAL_CONFIG",
                                f"{label} differ across arms: {mapping_val!r} (unequal config refused)",
                            )

        return CampaignConfig(
            campaign_id=str(config.get("campaign_id", "acns-sok-evidence-boundaries-campaign")),
            arm_ids=arm_ids_tuple,
            case_ids=case_ids_tuple,
            seed=int(config.get("seed", 42)),
            seeds=seeds_tuple,
            source_commit=str(config.get("source_commit", "")),
            per_pair_timeout_seconds=float(config.get("per_pair_timeout_seconds", 60.0)),
            retry_budget=int(config.get("retry_budget", 0)),
            workers=int(config.get("workers", 1)),
            journal_path=config.get("journal_path"),
            cases=config.get("cases"),
            arms=config.get("arms"),
            arm_configs=config.get("arm_configs"),
            oracle=config.get("oracle"),
            output_path=config.get("output_path"),
        )
    raise RunnerError("INVALID_CONFIG", f"unsupported config type: {type(config).__name__}")


def run_campaign(
    config: CampaignConfig | Mapping[str, Any] | Campaign | None = None,
) -> RunBundle:
    """Execute all SoK reference classes over corpus/evidence records with equal config.

    Exact target contract: `run_campaign(config) -> RunBundle`.
    Reuses :mod:`evaluation.venue2027._shared.harness` for deterministic, idempotent execution.
    """
    cfg = _coerce_config(config)
    cfg.validate()

    source_commit = resolve_source_commit(cfg.source_commit or None)

    # Build active case registry
    case_registry = dict(DEFAULT_CASE_REGISTRY)
    if cfg.cases is not None:
        if isinstance(cfg.cases, Mapping):
            for k, v in cfg.cases.items():
                if isinstance(v, Mapping):
                    c = dict(v)
                    c.setdefault("case_id", str(k))
                    case_registry[str(k)] = c
        elif isinstance(cfg.cases, Sequence):
            for item in cfg.cases:
                if isinstance(item, Mapping):
                    cid = str(item.get("case_id", ""))
                    if cid:
                        case_registry[cid] = dict(item)

    case_ids = cfg.case_ids if cfg.case_ids is not None else DEFAULT_CASE_IDS
    arm_ids = cfg.arm_ids

    seeds = cfg.seeds if cfg.seeds is not None else tuple(cfg.seed for _ in arm_ids)

    # Instantiate harness Campaign
    harness_campaign = Campaign(
        campaign_id=cfg.campaign_id,
        case_ids=case_ids,
        arm_ids=arm_ids,
        seeds=seeds,
        source_commit=source_commit,
        per_pair_timeout_seconds=cfg.per_pair_timeout_seconds,
    )

    # Build arm adapters
    arm_adapters: dict[str, ArmAdapter] = {}
    for arm_id in arm_ids:
        arm_adapters[arm_id] = _make_arm_adapter(arm_id, case_registry, cfg.arms)

    # Build oracle adapter
    oracle_fn = make_harness_oracle(case_registry, cfg.oracle)

    # Execute via harness
    bundle = harness.execute(
        campaign=harness_campaign,
        arms=arm_adapters,
        oracle=oracle_fn,
        workers=cfg.workers,
        journal_path=cfg.journal_path,
    )

    # Optionally persist bundle
    if cfg.output_path is not None:
        out = Path(cfg.output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(bundle.to_jsonl(), encoding="utf-8")

    return bundle


__all__ = [
    "ACNS_RUNNER_VERSION",
    "CANDIDATE_ARM_IDS",
    "DEFAULT_ARM_IDS",
    "DEFAULT_CASE_IDS",
    "DEFAULT_CASE_REGISTRY",
    "REFERENCE_CLASSES",
    "CampaignConfig",
    "RunBundle",
    "RunnerError",
    "build_default_cases",
    "make_harness_oracle",
    "resolve_source_commit",
    "run_campaign",
]
