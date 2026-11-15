"""CLARA-Care 2027 POPETS task POPETS-runner — uniform multi-arm execution runner.

Purpose
-------
Execute a *preregistered* comparative evaluation for the PoPETs 2027 study
"Revocation-Complete Future Disclosure for Cached Longitudinal AI Contexts"
(``research/venue2027/VENUES/popets/RESEARCH_BLUEPRINT.md``; task contract
``research/venue2027/VENUES/popets/TASKS/POPETS-runner.md``).

The runner executes a BALANCED PAIRED case/order/seed plan across ALL declared
arms under identical conditions:
- Same per-pair time limit
- Same retry budget
- Same execution backend
- Same randomness (deterministic frozen seed across all arms; seed drift refused)
- Same compiler/runtime and model versions

Execution delegates directly to the audited shared harness
(:mod:`evaluation.venue2027._shared.harness`), ensuring that:
1. Every planned arm x case pair is recorded (full denominator, no drops).
2. Failures and crashes are recorded as first-class outcomes (``EXECUTION_ERROR``),
   never uncounted exceptions or false zeroes.
3. Mutually exclusive outcome categories match
   ``research/venue2027/GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md`` rules 3-4.
4. Resumable execution is idempotent via journal binding.

Arms (blueprint arms B0-B4 + design references):
- ``B0`` / ``ttl-only-cache``: weak lower bound (honestly ``NOT_RUN_EXTERNAL``)
- ``B1`` / ``coarse-cache-purge-on-revocation``: full purge on revocation
- ``B2`` / ``always-recompute-authorized-projection``: zero caching upper bound
- ``B3`` / ``zanzibar-like-consistency-token-cache``: zookie-style (honestly ``NOT_RUN_EXTERNAL``)
- ``B4`` / ``candidate`` / ``popets-revocation-complete-future-disclosure``:
  proposed transitive provenance-label invalidation (reverse-edge closure)
- ``ablation`` / ``popets-ablation-no-reverse-edges``: mechanism-isolation ablation
- ``purpose-bound-cache-keying``: key-rotated epoch miss comparator
- ``purpose-aware-cache-x06``: explicit fetch(key, epoch, purpose) with accounting

Allowed input
-------------
- ``config``: :class:`CampaignConfig` dataclass or mapping with configuration fields.
- Cases: provided via ``cases``, ``case_ids``, or defaults to the ex-ante frozen
  :data:`evaluation.venue2027.popets.privacy_cases.PRIVACY_CASES`.

Failure semantics
-----------------
Fail closed with stable uppercase reason codes:
- ``UNEQUAL_ARM_CONFIG`` — arms have different seeds, timeouts, retry budgets,
  backends, or versions (anti-tamper / balanced pairing enforcement).
- ``UNKNOWN_ARM`` — requested arm is not registered and has no custom adapter.
- ``EMPTY_SCOPE`` — no arms or cases configured.
- ``CONFIG_MALFORMED`` — config object is not a mapping or CampaignConfig.

Version
-------
``POPETS_RUNNER_VERSION = "1.0.0"``
"""

from __future__ import annotations

import dataclasses
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from evaluation.venue2027._shared import harness
from evaluation.venue2027._shared.harness import (
    ArmAdapter,
    Campaign,
    HarnessError,
    Oracle,
    Outcome,
    RunBundle,
    RunContext,
)
from evaluation.venue2027.popets import baselines as bl
from evaluation.venue2027.popets import candidate as cand
from evaluation.venue2027.popets import independent_oracle
from evaluation.venue2027.popets import privacy_cases as pc

__all__ = [
    "ARM_ALIASES",
    "CampaignConfig",
    "DEFAULT_ARMS",
    "DEFAULT_BACKEND",
    "DEFAULT_RETRY_BUDGET",
    "DEFAULT_SEED",
    "DEFAULT_TIMEOUT_SECONDS",
    "POPETS_RUNNER_VERSION",
    "RunnerError",
    "build_arm_adapters",
    "build_popets_oracle",
    "case_to_cache_ops",
    "case_to_workload",
    "resolve_source_commit",
    "run_campaign",
    "validate_arm_parity",
]

POPETS_RUNNER_VERSION = "1.0.0"

DEFAULT_SEED = 42
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_RETRY_BUDGET = 0
DEFAULT_BACKEND = "in_process"

DEFAULT_ARMS: tuple[str, ...] = ("B0", "B1", "B2", "B3", "B4")

ARM_ALIASES: dict[str, str] = {
    "B0": "ttl-only-cache",
    "ttl-only-cache": "ttl-only-cache",
    "B1": "coarse-cache-purge-on-revocation",
    "coarse-cache-purge-on-revocation": "coarse-cache-purge-on-revocation",
    "B2": "always-recompute-authorized-projection",
    "always-recompute-authorized-projection": "always-recompute-authorized-projection",
    "B3": "zanzibar-like-consistency-token-cache",
    "zanzibar-like-consistency-token-cache": "zanzibar-like-consistency-token-cache",
    "B4": "popets-revocation-complete-future-disclosure",
    "candidate": "popets-revocation-complete-future-disclosure",
    "popets-revocation-complete-future-disclosure": "popets-revocation-complete-future-disclosure",
    "ablation": "popets-ablation-no-reverse-edges",
    "popets-ablation-no-reverse-edges": "popets-ablation-no-reverse-edges",
    "purpose-bound-cache-keying": "purpose-bound-cache-keying",
    "purpose-aware-cache-x06": "purpose-aware-cache-x06",
}

FAMILY_MAP: dict[str, str] = {
    "fresh_dispatch": "fresh",
    "post_revocation_dispatch": "revoked_then_dispatch",
    "cross_purpose": "cross_purpose",
    "transitive_gap": "transitive_gap",
    "already_delivered": "already_delivered",
}


class RunnerError(HarnessError):
    """Stable, machine-readable runner configuration failure."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(reason_code, detail)


@dataclasses.dataclass(frozen=True)
class CampaignConfig:
    """Configuration for a balanced paired POPETS campaign."""

    campaign_id: str = "popets-campaign"
    arm_ids: tuple[str, ...] = DEFAULT_ARMS
    cases: tuple[Mapping[str, Any], ...] | None = None
    case_ids: tuple[str, ...] | None = None
    seed: int = DEFAULT_SEED
    seeds: tuple[int, ...] | Mapping[str, int] | None = None
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
    source_commit: str | None = None
    workers: int = 1
    journal_path: str | Path | None = None
    custom_arms: Mapping[str, ArmAdapter] | None = None
    custom_oracle: Oracle | None = None


def resolve_source_commit(explicit_sha: str | None = None) -> str:
    """Resolve the 40-hex git source commit, failing closed if unavailable."""
    if explicit_sha:
        clean = explicit_sha.strip().lower()
        if len(clean) == 40 and all(c in "0123456789abcdef" for c in clean):
            return clean
        raise RunnerError(
            "MISSING_SOURCE_SHA", f"source_commit must be a 40-hex SHA, got {explicit_sha!r}"
        )
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        sha = res.stdout.strip().lower()
        if len(sha) == 40 and all(c in "0123456789abcdef" for c in sha):
            return sha
    except Exception:
        pass
    raise RunnerError("MISSING_SOURCE_SHA", "could not resolve live 40-hex source commit")


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


def case_to_workload(case: Mapping[str, Any], seed: int = DEFAULT_SEED) -> dict[str, Any]:
    """Extract or synthesize a valid workload dictionary for baseline adapters."""
    del seed
    if "workload" in case and isinstance(case["workload"], Mapping):
        return dict(case["workload"])
    if "scenario" in case and isinstance(case["scenario"], Mapping):
        sc = case["scenario"]
        revs = [
            {
                "subject": str(r["principal"]),
                "grant": "g-med",
                "purpose": str(r["purpose"]),
                "at_seconds": int(r["revoked_at"]),
            }
            for r in sc.get("ledger", {}).get("revocations", [])
            if isinstance(r, Mapping) and "principal" in r and "purpose" in r and "revoked_at" in r
        ]
        principal = str(sc.get("principal", "s1"))
        grants = sc.get("ledger", {}).get("grants", {})
        principal_grant = grants.get(principal, {}) if isinstance(grants, Mapping) else {}
        labels = principal_grant.get("lineage_labels", {})
        if not isinstance(labels, Mapping) or not labels:
            labels = {"src_vitals": "BP 128/84"}
        snapshot = {str(k): f"val_{k}" for k in labels}
        raw_lin = sc.get("item", {}).get("lineage", [])
        lineage = [str(x) for x in raw_lin] if isinstance(raw_lin, list | tuple) else ["src_vitals"]
        disps = [
            {
                "dispatch_id": "d-query",
                "subject": principal,
                "grant": "g-med",
                "purpose": str(sc.get("purpose", "clinical")),
                "lineage": lineage,
                "at_seconds": int(sc.get("time", 10)),
            }
        ]
        return {
            "source_snapshot": snapshot,
            "revocations": revs,
            "dispatches": disps,
        }
    return {
        "source_snapshot": {
            "vitals_2026_01": "BP 128/84, HR 72",
            "med_list_2026_02": "metformin 1000mg",
            "admin_note_2026_01": "billing tier B",
        },
        "revocations": [
            {"subject": "subj-1", "grant": "g-med", "purpose": "analytics", "at_seconds": 100},
        ],
        "dispatches": [
            {
                "dispatch_id": "d1-pre-revocation",
                "subject": "subj-1",
                "grant": "g-med",
                "purpose": "clinical",
                "lineage": ["vitals_2026_01"],
                "at_seconds": 10,
            },
            {
                "dispatch_id": "d2-post-revocation-direct",
                "subject": "subj-1",
                "grant": "g-med",
                "purpose": "analytics",
                "lineage": ["med_list_2026_02"],
                "at_seconds": 200,
            },
            {
                "dispatch_id": "d3-post-revocation-transitive",
                "subject": "subj-1",
                "grant": "g-med",
                "purpose": "analytics",
                "lineage": ["summary_cache_1", "retry_payload_1", "vitals_2026_01"],
                "at_seconds": 300,
            },
            {
                "dispatch_id": "d4-unaffected-grant",
                "subject": "subj-1",
                "grant": "g-admin",
                "purpose": "clinical",
                "lineage": ["admin_note_2026_01"],
                "at_seconds": 400,
            },
        ],
    }


def case_to_cache_ops(case: Mapping[str, Any], seed: int = DEFAULT_SEED) -> list[dict[str, Any]]:
    """Extract or synthesize a valid cache_ops array for candidate / ablation arms."""
    del seed
    if "cache_ops" in case and isinstance(case["cache_ops"], list):
        return list(case["cache_ops"])
    if "scenario" in case and isinstance(case["scenario"], Mapping):
        sc = case["scenario"]
        principal = str(sc.get("principal", "s1"))
        grants = sc.get("ledger", {}).get("grants", {})
        principal_grant = grants.get(principal, {}) if isinstance(grants, Mapping) else {}
        grant_purposes = [str(p) for p in principal_grant.get("purposes", ["clinical"])]
        epoch = int(principal_grant.get("consent_epoch", 0))
        labels = principal_grant.get("lineage_labels", {})
        if not isinstance(labels, Mapping) or not labels:
            labels = {"src_vitals": "BP 128/84"}

        ops: list[dict[str, Any]] = []
        for k in labels:
            deps = [[principal, p, epoch] for p in grant_purposes]
            ops.append({"op": "put", "key": str(k), "value": f"val_{k}", "deps": deps})

        raw_lin = sc.get("item", {}).get("lineage", [])
        item_lineage = (
            [str(x) for x in raw_lin] if isinstance(raw_lin, list | tuple) else ["src_vitals"]
        )
        for lin in item_lineage:
            if lin not in labels:
                ops.append(
                    {
                        "op": "put",
                        "key": lin,
                        "value": f"derived_{lin}",
                        "deps": [[principal, grant_purposes[0], epoch]],
                        "derived_from": list(labels.keys()),
                    }
                )

        for r in sc.get("ledger", {}).get("revocations", []):
            if isinstance(r, Mapping):
                ops.append(
                    {
                        "op": "revoke",
                        "subject": str(r.get("principal", principal)),
                        "purpose": str(r.get("purpose", "analytics")),
                        "epoch": epoch,
                    }
                )

        query_purpose = str(sc.get("purpose", "clinical"))
        for lin in item_lineage:
            ops.append(
                {
                    "op": "get",
                    "key": lin,
                    "purpose": query_purpose,
                    "epoch": epoch,
                }
            )
        return ops

    return [
        {
            "op": "put",
            "key": "vitals_2026_01",
            "value": "BP 128/84, HR 72",
            "deps": [["subj-1", "clinical", 0]],
        },
        {
            "op": "put",
            "key": "summary_cache_1",
            "value": "summary of vitals",
            "deps": [["subj-1", "analytics", 0]],
            "derived_from": ["vitals_2026_01"],
        },
        {
            "op": "put",
            "key": "retry_payload_1",
            "value": "retry of summary",
            "deps": [["subj-1", "analytics", 0]],
            "derived_from": ["summary_cache_1"],
        },
        {
            "op": "put",
            "key": "admin_note_2026_01",
            "value": "billing tier B",
            "deps": [["subj-1", "clinical", 0]],
        },
        {
            "op": "revoke",
            "subject": "subj-1",
            "purpose": "analytics",
            "epoch": 0,
        },
        {
            "op": "get",
            "key": "vitals_2026_01",
            "purpose": "clinical",
            "epoch": 0,
        },
        {
            "op": "get",
            "key": "summary_cache_1",
            "purpose": "analytics",
            "epoch": 0,
        },
        {
            "op": "get",
            "key": "retry_payload_1",
            "purpose": "analytics",
            "epoch": 0,
        },
        {
            "op": "get",
            "key": "admin_note_2026_01",
            "purpose": "clinical",
            "epoch": 0,
        },
    ]


def _make_arm_adapter(
    canonical_id: str,
    cases_by_id: Mapping[str, Mapping[str, Any]],
) -> ArmAdapter:
    """Construct an arm adapter with full case lookup and format adaptation."""

    def adapter(case: Mapping[str, Any], ctx: RunContext) -> Outcome:
        case_id = str(case.get("case_id", ""))
        full_case = dict(cases_by_id.get(case_id, case))
        seed = ctx.seed

        if canonical_id in bl.BASELINE_REGISTRY:
            workload = case_to_workload(full_case, seed)
            case_for_baseline = {**full_case, "workload": workload}
            return bl.run_baseline(canonical_id, case_for_baseline, ctx)
        if canonical_id == "popets-revocation-complete-future-disclosure":
            ops = case_to_cache_ops(full_case, seed)
            case_for_cand = {**full_case, "mode": "candidate", "cache_ops": ops}
            return cand.run_candidate(case_for_cand, ctx)
        if canonical_id == "popets-ablation-no-reverse-edges":
            ops = case_to_cache_ops(full_case, seed)
            case_for_cand = {**full_case, "mode": "ablation", "cache_ops": ops}
            return cand.run_candidate(case_for_cand, ctx)
        raise RunnerError("UNKNOWN_ARM", f"unsupported canonical arm id {canonical_id!r}")

    return adapter


def build_arm_adapters(
    arm_ids: Sequence[str],
    cases_by_id: Mapping[str, Mapping[str, Any]],
    custom_arms: Mapping[str, ArmAdapter] | None = None,
) -> dict[str, ArmAdapter]:
    """Build and bind adapters for all requested arm identifiers."""
    adapters: dict[str, ArmAdapter] = {}
    custom = custom_arms or {}
    for arm_id in arm_ids:
        if arm_id in custom:
            adapters[arm_id] = custom[arm_id]
            continue
        canonical_id = ARM_ALIASES.get(arm_id)
        if canonical_id is None:
            raise RunnerError("UNKNOWN_ARM", f"arm {arm_id!r} not found in POPETS registry")
        adapters[arm_id] = _make_arm_adapter(canonical_id, cases_by_id)
    return adapters


def build_popets_oracle(cases_by_id: Mapping[str, Mapping[str, Any]]) -> Oracle:
    """Build the independent oracle callable complying with harness.Oracle."""

    def adjudicate_pair(
        case_id: str,
        arm_id: str,
        observed_outcome: str,
        detail: str,
    ) -> dict[str, Any]:
        del detail
        raw_case = cases_by_id.get(case_id, {"case_id": case_id})
        case = dict(raw_case)
        if "family" not in case:
            sc_class = case.get("scenario_class")
            if sc_class in FAMILY_MAP:
                case["family"] = FAMILY_MAP[sc_class]
            elif "scenario_family" in case:
                case["family"] = case["scenario_family"]
            elif (
                "payload" in case
                and isinstance(case["payload"], Mapping)
                and "scenario_family" in case["payload"]
            ):
                case["family"] = case["payload"]["scenario_family"]
        try:
            verdict = independent_oracle.adjudicate(case)
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
    """Execute a balanced paired campaign across all configured arms."""
    cfg = _coerce_config(config)

    if not cfg.arm_ids:
        raise RunnerError("EMPTY_SCOPE", "at least one arm_id is required")

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
        case_ids = tuple(case_ids_list)
    elif cfg.case_ids is not None:
        if not cfg.case_ids:
            raise RunnerError("EMPTY_SCOPE", "case_ids list cannot be empty")
        case_ids = tuple(str(cid) for cid in cfg.case_ids)
        for cid in case_ids:
            if cid in pc.PRIVACY_CASE_IDS:
                cases_by_id[cid] = pc.case_by_id(cid).to_dict()
            else:
                cases_by_id[cid] = {"case_id": cid}
    else:
        case_ids = pc.PRIVACY_CASE_IDS
        for case_obj in pc.PRIVACY_CASES:
            cases_by_id[case_obj.case_id] = case_obj.to_dict()

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

    arm_adapters = build_arm_adapters(
        cfg.arm_ids,
        cases_by_id,
        custom_arms=cfg.custom_arms,
    )

    oracle = (
        cfg.custom_oracle if cfg.custom_oracle is not None else build_popets_oracle(cases_by_id)
    )

    return harness.execute(
        campaign=campaign,
        arms=arm_adapters,
        oracle=oracle,
        workers=cfg.workers,
        journal_path=cfg.journal_path,
    )
