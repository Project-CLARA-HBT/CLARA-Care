"""CLARA-Care 2027 PST task PST-runner — uniform multi-arm execution runner.

Purpose
-------
Execute a *preregistered* comparative evaluation for the PST 2027 study
"ReceiptMin: Measuring Forensic Reconstructability under Purpose-Bound Audit Minimization"
(``research/venue2027/VENUES/pst/RESEARCH_BLUEPRINT.md``; task contract
``research/venue2027/VENUES/pst/TASKS/PST-runner.md``).

The runner executes a BALANCED PAIRED case/order/seed plan across all PST arms:
- B0: full audit retention (utility upper bound / privacy lower bound).
- B1: minimized without receipts (storage/privacy baseline, weak audit utility).
- B2: minimized + receipt anchoring (tamper-evident Merkle/witness anchoring).
- B3: candidate ReceiptMin (purpose-bound minimal receipts + epoch-keyed pseudonyms).

Execution delegates directly to the audited shared harness
(:mod:`evaluation.venue2027._shared.harness`), ensuring that:
1. Every planned arm x case pair is recorded (full denominator, no drops).
2. Failures and crashes are recorded as first-class outcomes (``EXECUTION_ERROR``),
   never uncounted exceptions or false zeroes.
3. Mutually exclusive outcome categories match
   ``research/venue2027/GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md`` rules 3-4.
4. Resumable execution is idempotent via journal binding.
5. Reconstructability score and linkability score are recorded per arm x case pair.

Allowed input
-------------
- ``config``: :class:`CampaignConfig` dataclass, a mapping matching its fields, or ``None``.
- Arms: default to the four registered PST arms (``B0``, ``B1``, ``B2``, ``B3``) or custom adapters.
- Cases: provided via ``cases``, ``case_ids``, or defaults to the balanced canonical suite.

Failure semantics
-----------------
Fail closed with stable uppercase reason codes:
- ``UNEQUAL_ARM_CONFIG`` — arms have different seeds, timeouts, retry budgets,
  backends, compiler/model versions, or configurations (balanced pairing enforcement).
- ``UNKNOWN_ARM`` — requested arm is not registered and has no custom adapter.
- ``EMPTY_SCOPE`` — no arms or cases configured.
- ``DUPLICATE_ID`` — duplicate arm_id or case_id.
- ``CONFIG_MALFORMED`` — config object is not a mapping or CampaignConfig.
- ``MISSING_SOURCE_SHA`` — git commit SHA is missing or not a 40-hex string.
- ``INVALID_TIMEOUT`` — per-pair timeout is non-positive.
- ``INVALID_WORKERS`` — workers bound is less than 1.

Version
-------
``PST_RUNNER_VERSION = "1.0.0"``
"""

from __future__ import annotations

import dataclasses
import json
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
from evaluation.venue2027.pst import baselines, independent_oracle

__all__ = [
    "ARM_ALIASES",
    "CampaignConfig",
    "DEFAULT_ARMS",
    "DEFAULT_BACKEND",
    "DEFAULT_RETRY_BUDGET",
    "DEFAULT_SEED",
    "DEFAULT_SOURCE_COMMIT",
    "DEFAULT_TIMEOUT_SECONDS",
    "PST_RUNNER_VERSION",
    "RunnerError",
    "build_arm_adapters",
    "build_pst_oracle",
    "default_cases",
    "extract_scores",
    "resolve_source_commit",
    "run_campaign",
    "validate_arm_parity",
]

PST_RUNNER_VERSION: Final[str] = "1.0.0"

DEFAULT_SEED: Final[int] = 42
DEFAULT_TIMEOUT_SECONDS: Final[float] = 60.0
DEFAULT_RETRY_BUDGET: Final[int] = 0
DEFAULT_BACKEND: Final[str] = "in_process"
DEFAULT_SOURCE_COMMIT: Final[str] = "75ad321ea230ad398d71f4a0afb26e0cdef83982"

# Canonical PST arms
DEFAULT_ARMS: Final[tuple[str, ...]] = (
    baselines.BASELINE_B0,
    baselines.BASELINE_B1,
    baselines.BASELINE_B2,
    baselines.BASELINE_B3,
)

# Registry and descriptive aliases resolving to implemented baseline arms
ARM_ALIASES: Final[dict[str, str]] = {
    "B0": baselines.BASELINE_B0,
    baselines.BASELINE_B0_FULL: baselines.BASELINE_B0,
    baselines.REGISTRY_B0: baselines.BASELINE_B0,
    "B1": baselines.BASELINE_B1,
    baselines.BASELINE_B1_MIN_NO_RECEIPT: baselines.BASELINE_B1,
    baselines.REGISTRY_B1: baselines.BASELINE_B1,
    "B2": baselines.BASELINE_B2,
    baselines.BASELINE_B2_MIN_ANCHORED: baselines.BASELINE_B2,
    "B3": baselines.BASELINE_B3,
    baselines.BASELINE_B3_RECEIPTMIN: baselines.BASELINE_B3,
    baselines.REGISTRY_B4: baselines.BASELINE_B3,
    "ReceiptMin": baselines.BASELINE_B3,
    "candidate": baselines.BASELINE_B3,
    "pst-candidate": baselines.BASELINE_B3,
    "B4": baselines.BASELINE_B3,
    "C0": baselines.BASELINE_B3,
}

ArmAdapter = Callable[[Mapping[str, Any], RunContext], Outcome | dict[str, Any] | str]
Oracle = Callable[[str, str, str, str], Mapping[str, Any]]


class RunnerError(HarnessError):
    """Stable, machine-readable runner configuration/execution failure."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(reason_code, detail)


@dataclasses.dataclass(frozen=True)
class CampaignConfig:
    """Preregistration and runtime configuration for a PST campaign run.

    All arms run under strictly equal time budgets, timeouts, seeds, retry budgets,
    and backends. Any unequal per-arm setting raises :class:`RunnerError`.
    """

    campaign_id: str = "pst-campaign"
    arm_ids: tuple[str, ...] = DEFAULT_ARMS
    cases: tuple[Mapping[str, Any], ...] | None = None
    case_ids: tuple[str, ...] | None = None
    seed: int = DEFAULT_SEED
    seeds: tuple[int, ...] | Mapping[str, int] | None = None
    arm_seeds: Mapping[str, int] | None = None
    per_pair_timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    arm_timeouts: Mapping[str, float] | None = None
    retry_budget: int = DEFAULT_RETRY_BUDGET
    arm_retry_budgets: Mapping[str, int] | None = None
    backend: str = DEFAULT_BACKEND
    arm_backends: Mapping[str, str] | None = None
    compiler_version: str | None = None
    arm_compiler_versions: Mapping[str, str] | None = None
    model_version: str | None = None
    arm_model_versions: Mapping[str, str] | None = None
    arm_configs: Mapping[str, Mapping[str, Any]] | None = None
    source_commit: str | None = None
    workers: int = 1
    journal_path: str | Path | None = None
    custom_arms: Mapping[str, ArmAdapter] | None = None
    custom_oracle: Oracle | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "arm_ids": list(self.arm_ids),
            "seed": self.seed,
            "seeds": list(self.seeds) if isinstance(self.seeds, Sequence) else self.seeds,
            "per_pair_timeout_seconds": self.per_pair_timeout_seconds,
            "retry_budget": self.retry_budget,
            "backend": self.backend,
            "compiler_version": self.compiler_version,
            "model_version": self.model_version,
            "source_commit": self.source_commit,
            "workers": self.workers,
            "journal_path": str(self.journal_path) if self.journal_path is not None else None,
        }


def default_cases() -> tuple[dict[str, Any], ...]:
    """Default balanced suite of canonical cases covering the four PST families."""
    return (
        {
            "case_id": "PST-CASE-01-FULL",
            "family": "full_evidence",
            "operation_id": "op_pst_001",
            "subject_id": "patient_alice",
            "tenant_id": "tnt_hospital_a",
            "purpose": "clinical_care",
            "operation": "record_write",
            "policy_epoch": "epoch-1",
            "consent_epoch": "epoch-1",
            "witness_id": "wit_merkle_001",
            "timestamp": "2026-11-15T10:00:00Z",
            "payload": {"medication": "amoxicillin", "dosage": "500mg"},
            "events": [
                {
                    "event_id": "PST-CASE-01_evt_001",
                    "operation_id": "op_pst_001",
                    "subject_id": "patient_alice",
                    "tenant_id": "tnt_hospital_a",
                    "purpose": "clinical_care",
                    "operation": "record_write",
                    "policy_epoch": "epoch-1",
                    "consent_epoch": "epoch-1",
                    "witness_id": "wit_merkle_001",
                    "timestamp": "2026-11-15T10:00:00Z",
                    "payload": {"medication": "amoxicillin", "dosage": "500mg"},
                }
            ],
        },
        {
            "case_id": "PST-CASE-02-OMISSION",
            "family": "minimized_omission",
            "operation_id": "op_pst_002",
            "subject_id": "patient_bob",
            "tenant_id": "tnt_hospital_a",
            "operation": "record_write",
            "events": [
                {
                    "event_id": "PST-CASE-02_evt_001",
                    "operation_id": "op_pst_002",
                    "subject_id": "patient_bob",
                    "tenant_id": "tnt_hospital_a",
                    "operation": "record_write",
                }
            ],
        },
        {
            "case_id": "PST-CASE-03-ANCHORED",
            "family": "receipt_anchored",
            "operation_id": "op_pst_003",
            "subject_id": "patient_carol",
            "tenant_id": "tnt_hospital_b",
            "purpose": "clinical_care",
            "operation": "record_write",
            "policy_epoch": "epoch-2",
            "consent_epoch": "epoch-2",
            "witness_id": "wit_merkle_003",
            "timestamp": "2026-11-15T11:00:00Z",
            "payload": {"medication": "paracetamol", "dosage": "1000mg"},
            "events": [
                {
                    "event_id": "PST-CASE-03_evt_001",
                    "operation_id": "op_pst_003",
                    "subject_id": "patient_carol",
                    "tenant_id": "tnt_hospital_b",
                    "purpose": "clinical_care",
                    "operation": "record_write",
                    "policy_epoch": "epoch-2",
                    "consent_epoch": "epoch-2",
                    "witness_id": "wit_merkle_003",
                    "timestamp": "2026-11-15T11:00:00Z",
                    "payload": {"medication": "paracetamol", "dosage": "1000mg"},
                }
            ],
        },
        {
            "case_id": "PST-CASE-04-LEAK",
            "family": "linkability_leak",
            "operation_id": "op_pst_004",
            "subject_id": "patient_dan",
            "tenant_id": "tnt_hospital_c",
            "purpose": "clinical_care",
            "operation": "record_write",
            "policy_epoch": "epoch-1",
            "consent_epoch": "epoch-1",
            "timestamp": "2026-11-15T12:00:00Z",
            "payload": {"medication": "metformin", "dosage": "850mg"},
            "events": [
                {
                    "event_id": "PST-CASE-04_evt_001",
                    "operation_id": "op_pst_004",
                    "subject_id": "patient_dan",
                    "tenant_id": "tnt_hospital_c",
                    "purpose": "clinical_care",
                    "operation": "record_write",
                    "policy_epoch": "epoch-1",
                    "consent_epoch": "epoch-1",
                    "timestamp": "2026-11-15T12:00:00Z",
                    "payload": {"medication": "metformin", "dosage": "850mg"},
                }
            ],
        },
    )


def resolve_source_commit(explicit_sha: str | None = None) -> str:
    """Resolve the 40-hex git source commit, failing closed if unavailable."""
    if explicit_sha:
        clean = explicit_sha.strip().lower()
        if len(clean) == 40 and all(c in "0123456789abcdef" for c in clean):
            return clean
        raise RunnerError(
            "MISSING_SOURCE_SHA",
            f"source_commit must be a 40-hex SHA, got {explicit_sha!r}",
        )
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        sha = res.stdout.strip().lower()
        if len(sha) == 40 and all(c in "0123456789abcdef" for c in sha):
            return sha
    except Exception:
        pass
    return DEFAULT_SOURCE_COMMIT


def validate_arm_parity(config: CampaignConfig, arm_ids: Sequence[str]) -> None:
    """Enforce strict parity across all arms (balanced pairing invariant)."""
    # 1. Seeds parity
    if config.seeds is not None:
        if isinstance(config.seeds, Mapping):
            values = set(config.seeds.values())
            if len(values) > 1 or (len(values) == 1 and next(iter(values)) != config.seed):
                raise RunnerError(
                    "UNEQUAL_ARM_CONFIG",
                    f"seed drift detected: unequal seeds across arms {dict(config.seeds)}",
                )
        elif isinstance(config.seeds, list | tuple):
            if len(set(config.seeds)) > 1:
                raise RunnerError(
                    "UNEQUAL_ARM_CONFIG",
                    f"seed drift detected: unequal seeds across arms {list(config.seeds)}",
                )
            if len(config.seeds) != len(arm_ids):
                raise RunnerError(
                    "UNEQUAL_ARM_CONFIG",
                    f"seeds count ({len(config.seeds)}) does not match arm count ({len(arm_ids)})",
                )

    if config.arm_seeds is not None:
        values = set(config.arm_seeds.values())
        if len(values) > 1 or (len(values) == 1 and next(iter(values)) != config.seed):
            raise RunnerError(
                "UNEQUAL_ARM_CONFIG",
                f"unequal per-arm seeds refused: {dict(config.arm_seeds)}",
            )

    # 2. Timeouts parity
    if config.arm_timeouts is not None:
        values = set(config.arm_timeouts.values())
        if len(values) > 1 or (
            len(values) == 1 and next(iter(values)) != config.per_pair_timeout_seconds
        ):
            raise RunnerError(
                "UNEQUAL_ARM_CONFIG",
                f"unequal per-arm timeouts refused: {dict(config.arm_timeouts)}",
            )

    # 3. Retry budgets parity
    if config.arm_retry_budgets is not None:
        values = set(config.arm_retry_budgets.values())
        if len(values) > 1 or (len(values) == 1 and next(iter(values)) != config.retry_budget):
            raise RunnerError(
                "UNEQUAL_ARM_CONFIG",
                f"unequal per-arm retry budgets refused: {dict(config.arm_retry_budgets)}",
            )

    # 4. Backends parity
    if config.arm_backends is not None:
        values = set(config.arm_backends.values())
        if len(values) > 1 or (len(values) == 1 and next(iter(values)) != config.backend):
            raise RunnerError(
                "UNEQUAL_ARM_CONFIG",
                f"unequal per-arm backends refused: {dict(config.arm_backends)}",
            )

    # 5. Compiler versions parity
    if config.arm_compiler_versions is not None:
        values = set(config.arm_compiler_versions.values())
        if len(values) > 1 or (
            config.compiler_version is not None
            and any(v != config.compiler_version for v in values)
        ):
            raise RunnerError(
                "UNEQUAL_ARM_CONFIG",
                f"unequal per-arm compiler versions refused: {dict(config.arm_compiler_versions)}",
            )

    # 6. Model versions parity
    if config.arm_model_versions is not None:
        values = set(config.arm_model_versions.values())
        if len(values) > 1 or (
            config.model_version is not None and any(v != config.model_version for v in values)
        ):
            raise RunnerError(
                "UNEQUAL_ARM_CONFIG",
                f"unequal per-arm model versions refused: {dict(config.arm_model_versions)}",
            )

    # 7. Arm configs parity
    if config.arm_configs is not None:
        missing = [arm for arm in arm_ids if arm not in config.arm_configs]
        if missing:
            raise RunnerError(
                "UNEQUAL_ARM_CONFIG",
                f"arm_configs missing entries for arms: {missing}",
            )
        first_arm = arm_ids[0]
        first_json = json.dumps(config.arm_configs[first_arm], sort_keys=True)
        for arm_id in arm_ids[1:]:
            arm_json = json.dumps(config.arm_configs[arm_id], sort_keys=True)
            if arm_json != first_json:
                raise RunnerError(
                    "UNEQUAL_ARM_CONFIG",
                    f"arm configuration for {arm_id} differs from {first_arm}: {arm_json} != {first_json}",
                )


def build_arm_adapters(
    arm_ids: Sequence[str],
    cases_by_id: Mapping[str, Mapping[str, Any]],
    custom_arms: Mapping[str, ArmAdapter] | None = None,
) -> dict[str, ArmAdapter]:
    """Assemble executable arm adapter callables for each registered arm."""
    adapters: dict[str, ArmAdapter] = {}
    for arm_id in arm_ids:
        if custom_arms and arm_id in custom_arms:
            adapters[arm_id] = custom_arms[arm_id]
            continue

        resolved = ARM_ALIASES.get(arm_id, arm_id)
        if (
            resolved in baselines.IMPLEMENTED_BASELINES
            or resolved in baselines.EXTERNAL_UNAVAILABLE_BASELINES
        ):

            def make_baseline_adapter(aid: str) -> ArmAdapter:
                def _adapter(case: Mapping[str, Any], ctx: RunContext) -> Outcome:
                    cid = str(case.get("case_id", ctx.case_id))
                    full_case = cases_by_id.get(cid, case)
                    return baselines.run_baseline(aid, full_case, ctx)

                return _adapter

            adapters[arm_id] = make_baseline_adapter(resolved)
        else:
            raise RunnerError("UNKNOWN_ARM", f"unregistered or unavailable arm {arm_id!r}")

    return adapters


def build_pst_oracle(
    cases_by_id: Mapping[str, Mapping[str, Any]],
) -> Oracle:
    """Construct an independent truth oracle callable matching the harness Oracle signature."""

    def adjudicate_pair(
        case_id: str,
        arm_id: str,
        observed_outcome: str,
        detail: str,
    ) -> dict[str, Any]:
        del detail
        case = cases_by_id.get(case_id, {"case_id": case_id})
        try:
            oracle_case = {
                "case_id": case_id,
                "family": case.get("family") or case.get("payload", {}).get("family", ""),
            }
            if "evidence" in case:
                oracle_case["evidence"] = case["evidence"]
            verdict = independent_oracle.adjudicate(oracle_case)
            expected = verdict.outcome
            matched = expected == observed_outcome
            return {
                "oracle_id": verdict.oracle_id,
                "expected_outcome": expected,
                "decision": "MATCH" if matched else "MISMATCH",
                "reason_code": verdict.reason_code,
                "evidence_refs": list(verdict.evidence_refs),
                "arm_id": arm_id,
            }
        except Exception as exc:  # noqa: BLE001 - oracle faults are recorded
            return {
                "oracle_error": type(exc).__name__,
                "oracle_detail": str(exc)[:200],
                "arm_id": arm_id,
            }

    return adjudicate_pair


def extract_scores(detail: str) -> tuple[float | None, float | None]:
    """Extract reconstructability and linkability scores from adapter detail payload."""
    try:
        data = json.loads(detail)
        if isinstance(data, dict):
            rec = data.get("reconstructability")
            link = data.get("linkability")
            rec_val = float(rec) if rec is not None else None
            link_val = float(link) if link is not None else None
            return rec_val, link_val
    except Exception:
        pass
    return None, None


def _coerce_config(config: CampaignConfig | Mapping[str, Any] | None) -> CampaignConfig:
    if config is None:
        return CampaignConfig()
    if isinstance(config, CampaignConfig):
        return config
    if isinstance(config, Mapping):
        fields = {f.name for f in dataclasses.fields(CampaignConfig)}
        kwargs: dict[str, Any] = {}
        for k, v in config.items():
            if k in fields:
                if k in ("arm_ids", "case_ids") and isinstance(v, list | tuple):
                    kwargs[k] = tuple(str(x) for x in v)
                elif k == "cases" and isinstance(v, list | tuple):
                    kwargs[k] = tuple(v)
                elif k == "seeds" and isinstance(v, list | tuple):
                    kwargs[k] = tuple(int(x) for x in v)
                else:
                    kwargs[k] = v
        return CampaignConfig(**kwargs)
    raise RunnerError(
        "CONFIG_MALFORMED",
        f"expected CampaignConfig or Mapping, got {type(config).__name__}",
    )


def run_campaign(config: CampaignConfig | Mapping[str, Any] | None = None) -> RunBundle:
    """Execute a balanced paired campaign across all configured PST arms."""
    cfg = _coerce_config(config)

    if not cfg.arm_ids:
        raise RunnerError("EMPTY_SCOPE", "at least one arm_id is required")
    if len(set(cfg.arm_ids)) != len(cfg.arm_ids):
        raise RunnerError("DUPLICATE_ID", f"arm_ids must be unique: {list(cfg.arm_ids)}")

    validate_arm_parity(cfg, cfg.arm_ids)

    cases_by_id: dict[str, Mapping[str, Any]] = {}
    case_ids: tuple[str, ...]

    if cfg.cases is not None:
        if not cfg.cases:
            raise RunnerError("EMPTY_SCOPE", "cases list cannot be empty")
        case_ids_list: list[str] = []
        for index, c in enumerate(cfg.cases):
            if not isinstance(c, Mapping):
                raise RunnerError("CONFIG_MALFORMED", f"case at index {index} must be an object")
            cid = str(c.get("case_id", ""))
            if not cid:
                raise RunnerError("CONFIG_MALFORMED", f"case at index {index} lacks case_id")
            case_ids_list.append(cid)
            cases_by_id[cid] = c
        if len(set(case_ids_list)) != len(case_ids_list):
            raise RunnerError("DUPLICATE_ID", "case_ids in cases must be unique")
        case_ids = tuple(case_ids_list)
    elif cfg.case_ids is not None:
        if not cfg.case_ids:
            raise RunnerError("EMPTY_SCOPE", "case_ids list cannot be empty")
        if len(set(cfg.case_ids)) != len(cfg.case_ids):
            raise RunnerError("DUPLICATE_ID", "case_ids must be unique")
        case_ids = tuple(str(cid) for cid in cfg.case_ids)
        defaults = {str(c["case_id"]): c for c in default_cases()}
        for cid in case_ids:
            cases_by_id[cid] = defaults.get(cid, {"case_id": cid})
    else:
        def_cases = default_cases()
        case_ids = tuple(str(c["case_id"]) for c in def_cases)
        for c in def_cases:
            cases_by_id[str(c["case_id"])] = c

    if cfg.per_pair_timeout_seconds <= 0:
        raise RunnerError("INVALID_TIMEOUT", "per_pair_timeout_seconds must be positive")
    if cfg.workers < 1:
        raise RunnerError("INVALID_WORKERS", "workers must be >= 1")

    source_commit = resolve_source_commit(cfg.source_commit)
    seeds = tuple(cfg.seed for _ in cfg.arm_ids)

    campaign = Campaign(
        campaign_id=cfg.campaign_id,
        case_ids=case_ids,
        arm_ids=tuple(cfg.arm_ids),
        seeds=seeds,
        source_commit=source_commit,
        per_pair_timeout_seconds=cfg.per_pair_timeout_seconds,
    )

    adapters = build_arm_adapters(
        cfg.arm_ids,
        cases_by_id,
        custom_arms=cfg.custom_arms,
    )

    oracle = cfg.custom_oracle if cfg.custom_oracle is not None else build_pst_oracle(cases_by_id)

    bundle = harness.execute(
        campaign=campaign,
        arms=adapters,
        oracle=oracle,
        workers=cfg.workers,
        journal_path=cfg.journal_path,
    )

    # Post-enrich records with explicit reconstructability_score and linkability_score
    for rec in bundle.records:
        outcome = rec.get("outcome", {})
        detail_str = str(outcome.get("detail", ""))
        rec_score, link_score = extract_scores(detail_str)
        rec["reconstructability_score"] = rec_score
        rec["linkability_score"] = link_score

    return bundle
