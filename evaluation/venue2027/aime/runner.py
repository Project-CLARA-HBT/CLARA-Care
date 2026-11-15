"""AIME-runner (Phase P05, venue ``aime``) — uniform arm execution runner.

Purpose
-------
Uniform execution runner for the AIME 2027 study "Counterfactual Clinical
Workflow Safety under Changing Consent and Medication Histories"
(``research/venue2027/VENUES/aime/RESEARCH_BLUEPRINT.md``; task contract
``research/venue2027/VENUES/aime/TASKS/AIME-runner.md``).

Executes a preregistered campaign across all study arms (baselines B0-B5 and
candidate C0) over balanced synthetic clinical vignettes under strictly equal
configuration (identical seed, identical timeout, identical environment, no
seed drift, no unequal arm budgets).

Isolation & Evidence Contract
-----------------------------
- Reuses the shared deterministic multi-arm execution harness
  (:mod:`evaluation.venue2027._shared.harness`).
- Adjudication is delegated to the independent truth oracle
  (:mod:`evaluation.venue2027.aime.independent_oracle`).
- Pure, deterministic, offline execution over **synthetic vignettes only**:
  NO real PHI/PII (refused fail-closed per ``data_ethics_and_irb.md``).
- **NO LLM calls**: synthetic evaluation only. Provider-dependent arms
  without a configured provider yield ``NOT_RUN_EXTERNAL`` (never a fake
  pass or safe rejection).
- Every planned arm x vignette pair is recorded in theDenominator; nothing is
  ever silently dropped. An arm adapter that crashes is recorded as
  ``EXECUTION_ERROR`` with its exception class and counted in the full
  denominator.

Allowed input
-------------
A :class:`CampaignConfig` instance or mapping with:
- ``campaign_id``: non-empty string.
- ``arm_ids``: sequence of registered arm identifiers.
- ``seed`` / ``seeds``: non-negative integer(s); seeds MUST be identical across
  all arms (any drift is refused as ``UNEQUAL_CONFIG_REFUSED``).
- ``source_commit``: 40-character lowercase hex git SHA.
- ``vignettes``: sequence of synthetic clinical vignettes (or ``n_vignettes``
  to generate a balanced synthetic set across the 5 AIME update families).
- ``per_pair_timeout_seconds``: positive float timeout per pair.
- ``custom_adapters``: optional injected arm adapters for testing/ablation.
- ``arm_configs``: optional per-arm config dicts; must be identical across arms.
- ``provider_dependent_arms``: arms that require a live provider; if
  ``has_live_provider`` is False, they return ``NOT_RUN_EXTERNAL``.

Failure semantics
-----------------
Fail closed with stable uppercase reason codes (:class:`RunnerError`):
- ``UNEQUAL_CONFIG_REFUSED``: seeds, timeouts, or arm configurations differ
  between arms.
- ``EMPTY_SCOPE``: missing campaign_id, arm_ids, or vignettes.
- ``DUPLICATE_ID``: duplicate arm_ids or case_ids.
- ``UNKNOWN_ARM``: arm not found in the baseline or candidate registry.
- ``MISSING_SOURCE_SHA``: source_commit is not a 40-hex string.
- ``INVALID_TIMEOUT``: per_pair_timeout_seconds <= 0.
- ``INVALID_WORKERS``: workers < 1.
- ``MALFORMED_VIGNETTE``: vignette missing required case_id or fields.

Version
-------
``RUNNER_VERSION = "1.0.0"`` (additive-only within 1.x).
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from evaluation.venue2027._shared import harness
from evaluation.venue2027._shared.harness import (
    ArmAdapter,
    Campaign,
    HarnessError,
    RunBundle,
    RunContext,
)
from evaluation.venue2027._shared.harness import (
    Outcome as HarnessOutcome,
)
from evaluation.venue2027.aime import baselines, candidate, independent_oracle
from evaluation.venue2027.aime.baselines import (
    BASELINE_B0,
    BASELINE_B1,
    BASELINE_B2,
    BASELINE_B3,
    BASELINE_B4,
    BASELINE_B5,
    BASELINE_REGISTRY,
    REASON_PROVIDER_DEPENDENT,
)
from evaluation.venue2027.aime.candidate import CANDIDATE_ARM_ID

RUNNER_VERSION: Final[str] = "1.0.0"
DEFAULT_SOURCE_COMMIT: Final[str] = "28ff55110f980f42002524cef126290e91258cd6"
DEFAULT_CAMPAIGN_ID: Final[str] = "aime-study-2027"

DEFAULT_ARM_IDS: Final[tuple[str, ...]] = (
    BASELINE_B0,
    BASELINE_B1,
    BASELINE_B2,
    BASELINE_B3,
    BASELINE_B4,
    BASELINE_B5,
)

AIME_FAMILIES: Final[tuple[str, ...]] = (
    "stable_history",
    "consent_change",
    "medication_withdrawal",
    "allergy_update",
    "reconciliation",
)

SYNTHETIC_MEDICATIONS: Final[tuple[str, ...]] = (
    "metformin",
    "lisinopril",
    "atorvastatin",
    "amlodipine",
    "levothyroxine",
)

SYNTHETIC_PURPOSES: Final[tuple[str, ...]] = (
    "self_care",
    "care_summary",
    "medication_review",
)


class RunnerError(HarnessError):
    """Stable, machine-readable runner configuration/execution failure."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(reason_code, detail)


@dataclasses.dataclass(frozen=True)
class CampaignConfig:
    """Preregistered campaign execution configuration for the AIME study."""

    campaign_id: str = DEFAULT_CAMPAIGN_ID
    arm_ids: tuple[str, ...] = DEFAULT_ARM_IDS
    seeds: tuple[int, ...] | None = None
    seed: int = 2027
    source_commit: str = DEFAULT_SOURCE_COMMIT
    per_pair_timeout_seconds: float = 60.0
    vignettes: tuple[dict[str, Any], ...] | None = None
    n_vignettes: int = 5
    workers: int = 1
    journal_path: str | Path | None = None
    custom_adapters: Mapping[str, ArmAdapter] | None = None
    arm_configs: Mapping[str, Mapping[str, Any]] | None = None
    provider_dependent_arms: tuple[str, ...] = ()
    has_live_provider: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "arm_ids": list(self.arm_ids),
            "seeds": list(self.seeds) if self.seeds is not None else None,
            "seed": self.seed,
            "source_commit": self.source_commit,
            "per_pair_timeout_seconds": self.per_pair_timeout_seconds,
            "n_vignettes": self.n_vignettes,
            "workers": self.workers,
            "journal_path": str(self.journal_path) if self.journal_path is not None else None,
            "has_live_provider": self.has_live_provider,
            "provider_dependent_arms": list(self.provider_dependent_arms),
            "arm_configs": (
                {k: dict(v) for k, v in self.arm_configs.items()}
                if self.arm_configs is not None
                else None
            ),
        }


def validate_config(cfg: CampaignConfig) -> tuple[int, ...]:
    """Validate campaign configuration ensuring strictly equal configuration across arms."""
    if not cfg.campaign_id:
        raise RunnerError("EMPTY_SCOPE", "campaign_id must be non-empty")
    if not cfg.arm_ids:
        raise RunnerError("EMPTY_SCOPE", "arm_ids must be non-empty")
    if len(set(cfg.arm_ids)) != len(cfg.arm_ids):
        raise RunnerError("DUPLICATE_ID", "arm_ids must be unique")

    resolved_seeds = cfg.seeds if cfg.seeds is not None else tuple(cfg.seed for _ in cfg.arm_ids)
    if len(resolved_seeds) != len(cfg.arm_ids):
        raise RunnerError(
            "UNEQUAL_CONFIG_REFUSED",
            f"seeds count {len(resolved_seeds)} != arm count {len(cfg.arm_ids)}",
        )
    if len(set(resolved_seeds)) != 1:
        raise RunnerError(
            "UNEQUAL_CONFIG_REFUSED",
            f"seeds differ across arms (seed drift): {sorted(set(resolved_seeds))}",
        )

    # Check arm_configs for equal configuration
    if cfg.arm_configs is not None:
        missing_configs = [arm for arm in cfg.arm_ids if arm not in cfg.arm_configs]
        if missing_configs:
            raise RunnerError(
                "UNEQUAL_CONFIG_REFUSED",
                f"arm_configs missing entries for arms: {missing_configs}",
            )
        first_arm = cfg.arm_ids[0]
        ref_cfg_json = json.dumps(cfg.arm_configs[first_arm], sort_keys=True)
        for arm_id in cfg.arm_ids[1:]:
            arm_cfg_json = json.dumps(cfg.arm_configs[arm_id], sort_keys=True)
            if arm_cfg_json != ref_cfg_json:
                raise RunnerError(
                    "UNEQUAL_CONFIG_REFUSED",
                    f"arm configuration for {arm_id} differs from {first_arm}: {arm_cfg_json} != {ref_cfg_json}",
                )

    if len(cfg.source_commit) != 40 or any(c not in "0123456789abcdef" for c in cfg.source_commit):
        raise RunnerError("MISSING_SOURCE_SHA", "source_commit must be a 40-hex git SHA")
    if cfg.per_pair_timeout_seconds <= 0:
        raise RunnerError("INVALID_TIMEOUT", "per_pair_timeout_seconds must be positive")
    if cfg.workers < 1:
        raise RunnerError("INVALID_WORKERS", "workers must be >= 1")

    if cfg.vignettes is not None:
        if not cfg.vignettes:
            raise RunnerError("EMPTY_SCOPE", "vignettes sequence must be non-empty")
        case_ids = [v.get("case_id") for v in cfg.vignettes if isinstance(v, Mapping)]
        if any(not isinstance(cid, str) or not cid for cid in case_ids):
            raise RunnerError("MALFORMED_VIGNETTE", "all vignettes must have a non-empty case_id")
        if len(set(case_ids)) != len(case_ids):
            raise RunnerError("DUPLICATE_ID", "case_ids in vignettes must be unique")
    else:
        if cfg.n_vignettes <= 0:
            raise RunnerError("INVALID_N", "n_vignettes must be positive")

    return resolved_seeds


def parse_config(config: CampaignConfig | Mapping[str, Any]) -> CampaignConfig:
    """Coerce input mapping or CampaignConfig into a validated CampaignConfig."""
    if isinstance(config, CampaignConfig):
        validate_config(config)
        return config
    if not isinstance(config, Mapping):
        raise RunnerError(
            "INVALID_CONFIG",
            f"config must be CampaignConfig or Mapping, got {type(config).__name__}",
        )

    seeds_val = config.get("seeds")
    seeds_tuple = tuple(seeds_val) if seeds_val is not None else None
    arm_ids_val = config.get("arm_ids", config.get("arms", DEFAULT_ARM_IDS))
    arm_ids_tuple = tuple(arm_ids_val)
    vignettes_val = config.get("vignettes")
    vignettes_tuple = tuple(vignettes_val) if vignettes_val is not None else None

    cfg = CampaignConfig(
        campaign_id=str(config.get("campaign_id", DEFAULT_CAMPAIGN_ID)),
        arm_ids=arm_ids_tuple,
        seeds=seeds_tuple,
        seed=int(config.get("seed", 2027)),
        source_commit=str(config.get("source_commit", DEFAULT_SOURCE_COMMIT)),
        per_pair_timeout_seconds=float(config.get("per_pair_timeout_seconds", 60.0)),
        vignettes=vignettes_tuple,
        n_vignettes=int(config.get("n_vignettes", 5)),
        workers=int(config.get("workers", 1)),
        journal_path=config.get("journal_path"),
        custom_adapters=config.get("custom_adapters", config.get("custom_arms")),
        arm_configs=config.get("arm_configs"),
        provider_dependent_arms=tuple(config.get("provider_dependent_arms", ())),
        has_live_provider=bool(config.get("has_live_provider", False)),
    )
    validate_config(cfg)
    return cfg


def generate_synthetic_vignettes(n: int = 5, seed: int = 2027) -> list[dict[str, Any]]:
    """Generate balanced synthetic clinical vignettes across the 5 AIME update families."""
    if n <= 0:
        raise RunnerError("INVALID_N", "n must be a positive integer")
    vignettes: list[dict[str, Any]] = []
    for i in range(n):
        family = AIME_FAMILIES[i % len(AIME_FAMILIES)]
        case_id = f"AIME-SYNTH-{seed:04d}-{i:04d}"
        med = SYNTHETIC_MEDICATIONS[(seed + i) % len(SYNTHETIC_MEDICATIONS)]
        purpose = SYNTHETIC_PURPOSES[(seed + i) % len(SYNTHETIC_PURPOSES)]

        if family == "stable_history":
            snapshot = {"medications": [med], "consent": {"granted_purposes": [purpose]}}
            current = {"medications": [med], "consent": {"granted_purposes": [purpose]}}
            timeline = [
                {"order": 0, "event_kind": "INITIAL_STATE", "logical_time": 0, "payload": None},
                {
                    "order": 1,
                    "event_kind": "UNRELATED_NOTE_EDIT",
                    "logical_time": 1,
                    "payload": {"note": "routine review"},
                },
            ]
            output = {"text": f"Continue {med} per current plan."}
        elif family == "consent_change":
            snapshot = {"medications": [med], "consent": {"granted_purposes": [purpose]}}
            current = {"medications": [med], "consent": {"granted_purposes": []}}
            timeline = [
                {"order": 0, "event_kind": "INITIAL_STATE", "logical_time": 0, "payload": None},
                {
                    "order": 1,
                    "event_kind": "CONSENT_REVOKED",
                    "logical_time": 1,
                    "payload": {"purpose": purpose},
                },
            ]
            output = {"text": f"Continue {med}."}
        elif family == "medication_withdrawal":
            snapshot = {"medications": [med], "consent": {"granted_purposes": [purpose]}}
            current = {"medications": [], "consent": {"granted_purposes": [purpose]}}
            timeline = [
                {"order": 0, "event_kind": "INITIAL_STATE", "logical_time": 0, "payload": None},
                {
                    "order": 1,
                    "event_kind": "MEDICATION_WITHDRAWN",
                    "logical_time": 1,
                    "payload": {"medication": med},
                },
            ]
            output = {"text": f"Information regarding {med} in previous history."}
        elif family == "allergy_update":
            snapshot = {
                "medications": [med],
                "consent": {"granted_purposes": [purpose]},
                "allergies": [],
            }
            current = {
                "medications": [med],
                "consent": {"granted_purposes": [purpose]},
                "allergies": [med],
            }
            timeline = [
                {"order": 0, "event_kind": "INITIAL_STATE", "logical_time": 0, "payload": None},
                {
                    "order": 1,
                    "event_kind": "MEDICATION_ADDED",
                    "logical_time": 1,
                    "payload": {"medication": med},
                },
            ]
            output = {"text": f"Check status of {med}."}
        else:  # reconciliation
            other_med = SYNTHETIC_MEDICATIONS[(seed + i + 1) % len(SYNTHETIC_MEDICATIONS)]
            snapshot = {"medications": [med], "consent": {"granted_purposes": [purpose]}}
            current = {"medications": [med, other_med], "consent": {"granted_purposes": [purpose]}}
            timeline = [
                {"order": 0, "event_kind": "INITIAL_STATE", "logical_time": 0, "payload": None},
                {
                    "order": 1,
                    "event_kind": "MEDICATION_ADDED",
                    "logical_time": 1,
                    "payload": {"medication": other_med},
                },
            ]
            output = {"text": f"Review {med} and {other_med}."}

        vignette: dict[str, Any] = {
            "case_id": case_id,
            "purpose": purpose,
            "snapshot": snapshot,
            "current": current,
            "timeline": timeline,
            "task": {"drug": med, "kind": "recommendation"},
            "output": output,
            "family": family,
            "synthetic_only": True,
        }
        vignettes.append(vignette)
    return vignettes


def _map_decision_to_harness(
    decision: str,
    reason_code: str,
    detail: str,
) -> HarnessOutcome:
    """Map candidate / baseline 4-valued decisions to harness outcome buckets."""
    if decision == "SAFE":
        return HarnessOutcome(
            observed_outcome="ADMIT",
            counted_as_success=True,
            detail=f"{reason_code}: {detail}",
        )
    if decision == "UNSAFE":
        return HarnessOutcome(
            observed_outcome="REJECT",
            counted_as_success=False,
            detail=f"{reason_code}: {detail}",
        )
    if decision == "INDETERMINATE":
        return HarnessOutcome(
            observed_outcome="INDETERMINATE",
            counted_as_success=False,
            detail=f"{reason_code}: {detail}",
        )
    if decision == "NOT_RUN_EXTERNAL":
        return HarnessOutcome(
            observed_outcome="NOT_RUN_EXTERNAL",
            counted_as_success=False,
            detail=f"{reason_code}: {detail}",
        )
    return HarnessOutcome(
        observed_outcome="INVALID_RESULT",
        counted_as_success=False,
        detail=f"UNKNOWN_DECISION:{decision}",
    )


def _build_arm_adapter(
    arm_id: str,
    vignettes_by_id: Mapping[str, Mapping[str, Any]],
    cfg: CampaignConfig,
) -> ArmAdapter:
    """Construct an arm adapter enforcing honest execution and provider constraints."""
    # 1. Custom adapter if injected
    if cfg.custom_adapters and arm_id in cfg.custom_adapters:
        custom_fn = cfg.custom_adapters[arm_id]

        def custom_adapter_wrapper(
            case_stub: Mapping[str, Any], ctx: RunContext
        ) -> HarnessOutcome | dict[str, Any] | str:
            cid = str(case_stub.get("case_id", ""))
            vignette = vignettes_by_id.get(cid, {})
            full_case = {**vignette, **case_stub}
            raw = custom_fn(full_case, ctx)
            if isinstance(raw, HarnessOutcome):
                return raw
            if isinstance(raw, Mapping):
                if "decision" in raw and "observed_outcome" not in raw:
                    return _map_decision_to_harness(
                        str(raw["decision"]),
                        str(raw.get("reason_code", "OK")),
                        str(raw.get("detail", "")),
                    )
            return raw

        return custom_adapter_wrapper

    # 2. Provider-dependent arm without a provider -> NOT_RUN_EXTERNAL
    if not cfg.has_live_provider and (
        arm_id in cfg.provider_dependent_arms or arm_id == BASELINE_B2
    ):

        def provider_dependent_stub(
            case_stub: Mapping[str, Any], ctx: RunContext
        ) -> HarnessOutcome:
            return HarnessOutcome(
                observed_outcome="NOT_RUN_EXTERNAL",
                counted_as_success=False,
                detail=f"{REASON_PROVIDER_DEPENDENT}: live model provider not configured",
            )

        return provider_dependent_stub

    # 3. Candidate arm
    if arm_id == CANDIDATE_ARM_ID:

        def candidate_adapter(case_stub: Mapping[str, Any], ctx: RunContext) -> HarnessOutcome:
            cid = str(case_stub.get("case_id", ""))
            vignette = vignettes_by_id.get(cid)
            if vignette is None:
                return HarnessOutcome(
                    observed_outcome="INDETERMINATE",
                    detail=f"VIGNETTE_NOT_FOUND:{cid}",
                )
            c_ctx = candidate.CandidateContext(
                arm_id=arm_id,
                source_sha=ctx.source_commit,
                step_logical_time=1,
                purpose=str(vignette.get("purpose", "self_care")),
            )
            out = candidate.run_candidate(vignette, c_ctx)
            return _map_decision_to_harness(out.decision, out.reason_code, out.detail)

        return candidate_adapter

    # 4. Registered baseline arms
    if arm_id in BASELINE_REGISTRY:

        def baseline_adapter(case_stub: Mapping[str, Any], ctx: RunContext) -> HarnessOutcome:
            cid = str(case_stub.get("case_id", ""))
            vignette = vignettes_by_id.get(cid)
            if vignette is None:
                return HarnessOutcome(
                    observed_outcome="INDETERMINATE",
                    detail=f"VIGNETTE_NOT_FOUND:{cid}",
                )
            b_ctx = baselines.BaselineContext(
                arm_id=arm_id,
                source_sha=ctx.source_commit,
                step_logical_time=1,
                purpose=str(vignette.get("purpose", "self_care")),
            )
            out = baselines.run_baseline(arm_id, vignette, b_ctx)
            return _map_decision_to_harness(out.decision, out.reason_code, out.detail)

        return baseline_adapter

    raise RunnerError("UNKNOWN_ARM", f"arm_id {arm_id!r} is not registered")


def make_oracle(vignettes_by_id: Mapping[str, Mapping[str, Any]]) -> harness.Oracle:
    """Build the independent oracle callable for campaign adjudication."""

    def adjudicate(case_id: str, arm_id: str, observed: str, detail: str) -> dict[str, Any]:
        vignette = vignettes_by_id.get(case_id)
        if vignette is None:
            return {
                "oracle_id": independent_oracle.ORACLE_ID,
                "expected_outcome": "INDETERMINATE",
                "truth_outcome": "INDETERMINATE",
                "decision": "FAIL",
                "reason_code": "VIGNETTE_NOT_FOUND",
                "blinded_review_required": True,
            }
        res = independent_oracle.adjudicate(vignette)
        return {
            "oracle_id": res.oracle_id,
            "expected_outcome": res.outcome,
            "truth_outcome": res.outcome,
            "decision": "PASS" if res.outcome == observed else "FAIL",
            "reason_code": res.reason_code,
            "blinded_review_required": independent_oracle.requires_human_review(vignette),
        }

    return adjudicate


def run_campaign(config: CampaignConfig | Mapping[str, Any]) -> RunBundle:
    """Execute all arms over the synthetic vignette set with strictly equal config.

    Reuses ``evaluation.venue2027._shared.harness`` for deterministic,
    journal-backed, resumable multi-arm execution. Returns an aggregated
    :class:`RunBundle`.
    """
    cfg = parse_config(config)
    resolved_seeds = validate_config(cfg)

    vignettes: Sequence[Mapping[str, Any]]
    if cfg.vignettes is not None:
        vignettes = cfg.vignettes
    else:
        vignettes = generate_synthetic_vignettes(n=cfg.n_vignettes, seed=cfg.seed)

    vignettes_by_id = {str(v["case_id"]): v for v in vignettes}
    case_ids = tuple(str(v["case_id"]) for v in vignettes)

    campaign = Campaign(
        campaign_id=cfg.campaign_id,
        case_ids=case_ids,
        arm_ids=cfg.arm_ids,
        seeds=resolved_seeds,
        source_commit=cfg.source_commit,
        per_pair_timeout_seconds=cfg.per_pair_timeout_seconds,
    )

    arms: dict[str, ArmAdapter] = {
        arm_id: _build_arm_adapter(arm_id, vignettes_by_id, cfg) for arm_id in cfg.arm_ids
    }
    oracle = make_oracle(vignettes_by_id)

    bundle = harness.execute(
        campaign,
        arms,
        oracle,
        workers=cfg.workers,
        journal_path=cfg.journal_path,
    )
    return bundle
