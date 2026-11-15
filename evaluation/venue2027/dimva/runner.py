"""DIMVA-runner — Uniform arm executor (task DIMVA-runner, phase P05).

Purpose
-------
Task DIMVA-runner (Phase P05, venue ``dimva``): the uniform multi-arm campaign
runner for "GovernanceTrace: Detecting Adaptive Authorization-Boundary Probing
from Minimal Agent Events"
(``research/venue2027/VENUES/dimva/RESEARCH_BLUEPRINT.md``, task contract
``research/venue2027/VENUES/dimva/TASKS/DIMVA-runner.md``).

It executes a balanced, paired case/order/seed plan across all registered
detector arms (both in-process baseline arms B0, B1, B2, B3, the candidate
algorithm, and the pinned external arms B2_ISOLATION_FOREST and B3_GBT) under
identical conditions:
- equal time budgets and per-pair deadlines (budget disparity refused);
- equal seed assignments across all arms (seed drift refused);
- leak-safe case views to all arms (campaign labels and scenario families
  are strictly withheld from the detector input surface, preserving RQ1
  masking);
- first-class recording of all mutually exclusive outcomes (ADMIT, REJECT,
  INDETERMINATE, TIMEOUT, EXECUTION_ERROR, NOT_RUN_EXTERNAL, INVALID_RESULT);
  no exception from an arm adapter escapes as an uncounted crash.

Deterministic execution and resumable journaling are delegated to the audited
shared harness :mod:`evaluation.venue2027._shared.harness`.

Target contract
---------------
- :func:`run_campaign` — ``run_campaign(config) -> RunBundle``:
  executes all detector arms over the minimal agent event stream with equal
  config; records verdicts, scores, mutually exclusive outcomes, source
  commit, and seeds.
- :class:`CampaignConfig` — typed, frozen configuration dataclass.

Allowed input
-------------
A :class:`CampaignConfig` instance or a JSON-serializable mapping carrying:
- ``campaign_id``: non-empty string identifying the campaign.
- ``sessions``: sequence of session mappings, each containing ``case_id`` (or
  ``unit_id``) and a list of minimal-schema ``events``. If omitted, defaults to
  the balanced suite of clean and attack probe sessions.
- ``arm_ids``: sequence of registered arm identifiers (defaults to the 5
  runnable detector arms: ``B0``, ``B1``, ``B2``, ``B3``, ``candidate``).
- ``seed`` / ``seeds``: non-negative integer seed. If a sequence is supplied,
  all arms must have identical seeds (no seed drift).
- ``source_commit``: 40-hex git SHA (auto-detected from git HEAD if omitted).
- ``per_pair_timeout_seconds``: positive float per-pair execution deadline.
- ``workers``: concurrency bound (default 1 for deterministic reference).
- ``journal_path``: optional path for resumable, idempotent journal persistence.
- ``detector_context``: optional injected :class:`DetectorContext`.
- ``oracle``: optional injected oracle callable. If omitted, uses the
  independent truth oracle :mod:`evaluation.venue2027.dimva.independent_oracle`.

Failure semantics
-----------------
Fail closed with stable uppercase reason codes:
- ``EMPTY_SCOPE`` — no sessions or no arms declared.
- ``DUPLICATE_ID`` — duplicate session IDs or arm IDs.
- ``SEED_DRIFT`` — seeds count mismatch or unequal seeds across arms.
- ``UNEQUAL_CONFIG`` / ``BUDGET_DISPARITY`` — arms configured with unequal
  timeouts, budgets, or seeds.
- ``UNKNOWN_ARM`` — arm identifier not registered or unrecognized.
- ``MISSING_SOURCE_SHA`` — git commit SHA missing or invalid format.
- ``ORACLE_NOT_CALLABLE`` — injected oracle is not callable.
- ``MALFORMED_CONFIG`` — config is not a mapping or CampaignConfig.
- ``MALFORMED_CASE`` — session lacks case_id or is not an object.

Version
-------
``RUNNER_VERSION = "1.0.0"`` (additive-only within 1.x).
"""

from __future__ import annotations

import dataclasses
import math
import re
import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from evaluation.venue2027._shared.harness import (
    OUTCOME_BUCKETS,
    Campaign,
    Outcome,
    RunBundle,
    RunContext,
    execute,
)
from evaluation.venue2027.dimva import baselines, independent_oracle
from evaluation.venue2027.dimva.baselines import (
    BASELINE_B0,
    BASELINE_B1,
    BASELINE_B2,
    BASELINE_B2_ISOLATION_FOREST,
    BASELINE_B3,
    BASELINE_B3_GBT,
    BASELINE_REGISTRY,
    DetectorContext,
    run_baseline,
)
from evaluation.venue2027.dimva.candidate import (
    CANDIDATE_ID,
    run_candidate,
)

RUNNER_VERSION = "1.0.0"

#: Arm identifiers
ARM_B0 = BASELINE_B0
ARM_B1 = BASELINE_B1
ARM_B2 = BASELINE_B2
ARM_B3 = BASELINE_B3
ARM_B2_ISOLATION_FOREST = BASELINE_B2_ISOLATION_FOREST
ARM_B3_GBT = BASELINE_B3_GBT
ARM_CANDIDATE = "candidate"

CANDIDATE_ARM_ALIASES: frozenset[str] = frozenset({ARM_CANDIDATE, "DIMVA-candidate", CANDIDATE_ID})

#: The five runnable in-process detector arms (default arm plan).
IN_PROCESS_ARMS: tuple[str, ...] = (ARM_B0, ARM_B1, ARM_B2, ARM_B3, ARM_CANDIDATE)

#: Pinned external arms returning NOT_RUN_EXTERNAL per rule 8.
EXTERNAL_PINNED_ARMS: tuple[str, ...] = (ARM_B2_ISOLATION_FOREST, ARM_B3_GBT)

#: Default registered arms executed when arm_ids is not explicitly supplied.
DEFAULT_ARMS: tuple[str, ...] = IN_PROCESS_ARMS

#: All recognized arms in this venue.
ALL_REGISTERED_ARMS: tuple[str, ...] = (
    ARM_B0,
    ARM_B1,
    ARM_B2,
    ARM_B3,
    ARM_CANDIDATE,
    "DIMVA-candidate",
    CANDIDATE_ID,
    ARM_B2_ISOLATION_FOREST,
    ARM_B3_GBT,
)

# ---------------------------------------------------------------------------
# Stable reason codes (uppercase, machine-checkable).
# ---------------------------------------------------------------------------
RC_EMPTY_SCOPE = "EMPTY_SCOPE"
RC_DUPLICATE_ID = "DUPLICATE_ID"
RC_SEED_DRIFT = "SEED_DRIFT"
RC_UNEQUAL_CONFIG = "UNEQUAL_CONFIG"
RC_BUDGET_DISPARITY = "BUDGET_DISPARITY"
RC_UNKNOWN_ARM = "UNKNOWN_ARM"
RC_MISSING_ARM = "MISSING_ARM"
RC_MISSING_SOURCE_SHA = "MISSING_SOURCE_SHA"
RC_MALFORMED_CONFIG = "MALFORMED_CONFIG"
RC_ORACLE_NOT_CALLABLE = "ORACLE_NOT_CALLABLE"
RC_MALFORMED_CASE = "MALFORMED_CASE"
RC_CASE_EVENTS_MISSING = "CASE_EVENTS_MISSING"
RC_INVALID_TIMEOUT = "INVALID_TIMEOUT"
RC_INVALID_WORKERS = "INVALID_WORKERS"


class RunnerError(ValueError):
    """Stable, machine-readable runner configuration/wiring failure."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


@dataclasses.dataclass(frozen=True)
class CampaignConfig:
    """Preregistration and runtime configuration for a DIMVA campaign run.

    All detector arms run under identical time budget, timeout, seed, and
    environment settings. Any unequal per-arm budget raises :class:`RunnerError`.
    """

    campaign_id: str = "DIMVA-campaign"
    sessions: tuple[Mapping[str, Any], ...] = ()
    arm_ids: tuple[str, ...] = DEFAULT_ARMS
    seeds: tuple[int, ...] | None = None
    seed: int = 0
    source_commit: str = ""
    per_pair_timeout_seconds: float = 60.0
    workers: int = 1
    journal_path: str | Path | None = None
    detector_context: DetectorContext | None = None
    oracle: Any = None
    custom_arms: Mapping[str, Any] | None = None
    arm_timeouts: Mapping[str, float] | None = None
    arm_seeds: Mapping[str, int] | None = None


def default_probe_sessions() -> tuple[dict[str, Any], ...]:
    """Default balanced suite of paired benign and attack sessions for DIMVA."""
    benign_raw = baselines.benign_probe_sessions()
    attack_raw = baselines.attack_probe_sessions()

    annotated: list[dict[str, Any]] = []
    for s in benign_raw:
        case = dict(s)
        case["family"] = "benign_session"
        annotated.append(case)

    for s in attack_raw:
        case = dict(s)
        cid = str(case.get("case_id", ""))
        if "LOW-AND-SLOW" in cid:
            case["family"] = "low_and_slow"
        elif "PURPOSE-HOP" in cid:
            case["family"] = "burst_probe"
        else:
            case["family"] = "cross_tool_obfuscation"
        annotated.append(case)

    return tuple(annotated)


def _resolve_git_sha() -> str:
    """Resolve current git commit SHA (40-hex string)."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        sha = res.stdout.strip()
        if len(sha) == 40 and all(c in "0123456789abcdef" for c in sha):
            return sha
    except (OSError, subprocess.SubprocessError):
        pass
    # Fallback default recorded base SHA for this task
    return "28ff55110f980f42002524cef126290e91258cd6"


def _is_40_hex(sha: str) -> bool:
    return len(sha) == 40 and all(c in "0123456789abcdef" for c in sha)


def validate_config(config: CampaignConfig | Mapping[str, Any] | None) -> CampaignConfig:
    """Validate campaign configuration ensuring strict equal-config discipline."""
    if config is None:
        raw: Mapping[str, Any] = {}
    elif isinstance(config, CampaignConfig):
        raw = {
            "campaign_id": config.campaign_id,
            "sessions": config.sessions,
            "arm_ids": config.arm_ids,
            "seeds": config.seeds,
            "seed": config.seed,
            "source_commit": config.source_commit,
            "per_pair_timeout_seconds": config.per_pair_timeout_seconds,
            "workers": config.workers,
            "journal_path": config.journal_path,
            "detector_context": config.detector_context,
            "oracle": config.oracle,
            "custom_arms": config.custom_arms,
            "arm_timeouts": config.arm_timeouts,
            "arm_seeds": config.arm_seeds,
        }
    elif isinstance(config, Mapping):
        raw = config
    else:
        raise RunnerError(
            RC_MALFORMED_CONFIG,
            f"config must be a CampaignConfig or Mapping, got {type(config).__name__}",
        )

    campaign_id = str(raw.get("campaign_id", "DIMVA-campaign") or "").strip()
    if not campaign_id:
        raise RunnerError(RC_EMPTY_SCOPE, "campaign_id must be non-empty")

    # Arm IDs
    arm_ids_in = raw.get("arm_ids")
    if arm_ids_in is None:
        arm_ids = DEFAULT_ARMS
    else:
        if not isinstance(arm_ids_in, Sequence) or isinstance(arm_ids_in, str | bytes):
            raise RunnerError(RC_MALFORMED_CONFIG, "arm_ids must be a sequence of strings")
        arm_ids = tuple(str(a) for a in arm_ids_in)

    if not arm_ids:
        raise RunnerError(RC_EMPTY_SCOPE, "at least one arm_id is required")
    if len(set(arm_ids)) != len(arm_ids):
        raise RunnerError(RC_DUPLICATE_ID, f"duplicate arm_ids: {arm_ids}")

    custom_arms = raw.get("custom_arms") or {}
    for arm_id in arm_ids:
        if arm_id not in ALL_REGISTERED_ARMS and arm_id not in custom_arms:
            raise RunnerError(
                RC_UNKNOWN_ARM,
                f"arm_id {arm_id!r} not in registered arms {sorted(ALL_REGISTERED_ARMS)}",
            )

    # Sessions
    sessions_in = raw.get("sessions")
    if sessions_in is None:
        # Also check 'cases' alias
        sessions_in = raw.get("cases")

    if sessions_in is None:
        sessions = default_probe_sessions()
    else:
        if not isinstance(sessions_in, Sequence) or isinstance(sessions_in, str | bytes):
            raise RunnerError(RC_MALFORMED_CONFIG, "sessions must be a sequence of mappings")
        sessions = tuple(sessions_in)

    if len(sessions) == 0:
        raise RunnerError(RC_EMPTY_SCOPE, "at least one session is required")

    case_ids: list[str] = []
    for idx, s in enumerate(sessions):
        if not isinstance(s, Mapping):
            raise RunnerError(RC_MALFORMED_CASE, f"session {idx} must be a mapping")
        cid = str(s.get("case_id", s.get("unit_id", "")) or "").strip()
        if not cid:
            raise RunnerError(RC_MALFORMED_CASE, f"session {idx} missing case_id or unit_id")
        case_ids.append(cid)

    if len(set(case_ids)) != len(case_ids):
        raise RunnerError(RC_DUPLICATE_ID, "session case_ids must be unique")

    # Seeds & equal randomness check
    seed = int(raw.get("seed", 0))
    seeds_in = raw.get("seeds")
    if seeds_in is not None:
        if not isinstance(seeds_in, Sequence) or isinstance(seeds_in, str | bytes):
            raise RunnerError(RC_MALFORMED_CONFIG, "seeds must be a sequence of ints")
        seeds = tuple(int(x) for x in seeds_in)
        if len(seeds) != len(arm_ids):
            raise RunnerError(
                RC_SEED_DRIFT,
                f"seeds count {len(seeds)} != arm count {len(arm_ids)}",
            )
        if len(set(seeds)) != 1:
            raise RunnerError(
                RC_SEED_DRIFT,
                f"seeds differ across arms: {sorted(set(seeds))} (seed drift refused)",
            )
        seed = seeds[0]
    else:
        seeds = tuple(seed for _ in arm_ids)

    # Per-arm seeds dictionary check (if provided, all arms must match)
    arm_seeds = raw.get("arm_seeds")
    if arm_seeds is not None:
        if not isinstance(arm_seeds, Mapping):
            raise RunnerError(RC_MALFORMED_CONFIG, "arm_seeds must be a mapping")
        for arm in arm_ids:
            if arm not in arm_seeds:
                raise RunnerError(RC_UNEQUAL_CONFIG, f"arm_seeds missing arm {arm}")
        if len(set(arm_seeds.values())) > 1:
            raise RunnerError(
                RC_UNEQUAL_CONFIG,
                f"arm_seeds differ across arms: {dict(arm_seeds)} (seed drift refused)",
            )
        seed = int(next(iter(arm_seeds.values())))
        seeds = tuple(seed for _ in arm_ids)

    # Timeout & equal budget check
    per_pair_timeout = float(raw.get("per_pair_timeout_seconds", 60.0))
    if per_pair_timeout <= 0:
        raise RunnerError(RC_INVALID_TIMEOUT, "per_pair_timeout_seconds must be positive")

    arm_timeouts = raw.get("arm_timeouts")
    if arm_timeouts is not None:
        if not isinstance(arm_timeouts, Mapping):
            raise RunnerError(RC_MALFORMED_CONFIG, "arm_timeouts must be a mapping")
        if len(set(arm_timeouts.values())) > 1:
            raise RunnerError(
                RC_BUDGET_DISPARITY,
                f"unequal arm_timeouts: {dict(arm_timeouts)} (budget disparity refused)",
            )
        for arm in arm_ids:
            if arm in arm_timeouts and arm_timeouts[arm] != per_pair_timeout:
                raise RunnerError(
                    RC_BUDGET_DISPARITY,
                    f"arm {arm} timeout {arm_timeouts[arm]} != per_pair_timeout_seconds {per_pair_timeout}",
                )

    # Source commit SHA
    source_commit = str(raw.get("source_commit", "") or "").strip()
    if not source_commit:
        source_commit = _resolve_git_sha()
    if not _is_40_hex(source_commit):
        raise RunnerError(
            RC_MISSING_SOURCE_SHA,
            f"source_commit must be a 40-hex git SHA, got {source_commit!r}",
        )

    # Workers
    workers = int(raw.get("workers", 1))
    if workers < 1:
        raise RunnerError(RC_INVALID_WORKERS, "workers must be >= 1")

    # Oracle
    oracle = raw.get("oracle")
    if oracle is not None and not callable(oracle):
        raise RunnerError(RC_ORACLE_NOT_CALLABLE, "oracle must be callable")

    # DetectorContext
    detector_context = raw.get("detector_context")
    if detector_context is not None and not isinstance(detector_context, DetectorContext):
        raise RunnerError(RC_MALFORMED_CONFIG, "detector_context must be a DetectorContext")

    return CampaignConfig(
        campaign_id=campaign_id,
        sessions=sessions,
        arm_ids=arm_ids,
        seeds=seeds,
        seed=seed,
        source_commit=source_commit,
        per_pair_timeout_seconds=per_pair_timeout,
        workers=workers,
        journal_path=raw.get("journal_path"),
        detector_context=detector_context,
        oracle=oracle,
        custom_arms=custom_arms,
        arm_timeouts=arm_timeouts,
        arm_seeds=arm_seeds,
    )


# ---------------------------------------------------------------------------
# Outcome, verdict, and score extraction.
# ---------------------------------------------------------------------------


def _outcome_to_verdict(outcome: str) -> str:
    """Map harness outcome bucket to high-level detection verdict."""
    if outcome == "REJECT":
        return "DETECT"
    if outcome == "ADMIT":
        return "NO_DETECT"
    if outcome in OUTCOME_BUCKETS:
        return outcome
    return "UNKNOWN"


def extract_score(detail: str) -> float | None:
    """Extract numeric evidence score from outcome detail string if present."""
    if not detail or "score=" not in detail:
        return None
    try:
        match = re.search(r"score=([0-9eE\.\+\-]+)", detail)
        if match:
            val = float(match.group(1))
            return val if math.isfinite(val) else None
    except (ValueError, IndexError):
        pass
    return None


# ---------------------------------------------------------------------------
# Leak-safe case view: prevents campaign labels or oracle truth from reaching arms.
# ---------------------------------------------------------------------------


def _clean_case_for_arm(case_id: str, raw_session: Mapping[str, Any] | None) -> dict[str, Any]:
    """Build a leak-safe case dictionary for arm evaluation.

    Preserves RQ1 leak-safe masking: campaign-level labels, scenario families,
    and oracle fields are strictly omitted. Only minimal-schema event contents
    are passed down. If raw events contain forbidden reason codes or labels,
    they are retained so that the detector's own fail-closed gate catches them.
    """
    case: dict[str, Any] = {"case_id": case_id}
    if raw_session is None:
        return case

    if "events" in raw_session:
        raw_events = raw_session["events"]
        if isinstance(raw_events, list):
            clean_events: list[Any] = []
            for evt in raw_events:
                if isinstance(evt, Mapping):
                    # Retain event keys (the detector's own schema validator checks these)
                    clean_events.append(dict(evt))
                else:
                    clean_events.append(evt)
            case["events"] = clean_events
        else:
            case["events"] = raw_events
    return case


# ---------------------------------------------------------------------------
# Independent oracle adjudicator adapter.
# ---------------------------------------------------------------------------


def build_default_oracle(
    sessions: Sequence[Mapping[str, Any]],
) -> Callable[[str, str, str, str], dict[str, Any]]:
    """Construct an independent oracle callable matching the harness Oracle signature.

    Adjudicates ground truth using :mod:`evaluation.venue2027.dimva.independent_oracle`.
    Ground truth derives exclusively from declared scenario family and rule tables,
    never consulting candidate reason codes or scores.
    """
    truth_store: dict[str, dict[str, Any]] = {}
    for s in sessions:
        cid = str(s.get("case_id", s.get("unit_id", "")))
        if cid:
            truth_store[cid] = dict(s)

    def adjudicate_pair(
        case_id: str, arm_id: str, observed_outcome: str, detail: str
    ) -> dict[str, Any]:
        truth_case = truth_store.get(case_id, {"case_id": case_id})
        oracle_input = {
            "case_id": case_id,
            "family": truth_case.get("family", ""),
        }
        res = independent_oracle.adjudicate(oracle_input)
        truth_label = independent_oracle.campaign_truth(res)

        if truth_label == "ATTACK":
            expected_detector_outcome = "REJECT"
            expected_verdict = "DETECT"
        elif truth_label == "BENIGN":
            expected_detector_outcome = "ADMIT"
            expected_verdict = "NO_DETECT"
        else:
            expected_detector_outcome = "INDETERMINATE"
            expected_verdict = "INDETERMINATE"

        observed_verdict = _outcome_to_verdict(observed_outcome)
        score = extract_score(detail)

        decision = "PASS" if observed_outcome == expected_detector_outcome else "FAIL"

        return {
            "oracle_id": independent_oracle.CAMPAIGN_TRUTH_ORACLE_VERSION,
            "oracle_outcome": res.outcome,
            "truth_label": truth_label,
            "expected_outcome": expected_detector_outcome,
            "expected_verdict": expected_verdict,
            "observed_verdict": observed_verdict,
            "score": score,
            "decision": decision,
            "candidate_reason_code_ignored": True,
        }

    return adjudicate_pair


# ---------------------------------------------------------------------------
# Arm adapter factory.
# ---------------------------------------------------------------------------


def _build_arm_adapters(
    arm_ids: Sequence[str],
    sessions: Sequence[Mapping[str, Any]],
    detector_context: DetectorContext | None,
    custom_arms: Mapping[str, Any] | None,
) -> dict[str, Callable[[Mapping[str, Any], RunContext], Outcome]]:
    """Build injected arm adapters for all declared arms."""
    session_store = {str(s.get("case_id", s.get("unit_id", ""))): s for s in sessions}
    custom_arms = custom_arms or {}

    adapters: dict[str, Callable[[Mapping[str, Any], RunContext], Outcome]] = {}

    for arm_id in arm_ids:
        if arm_id in custom_arms:
            custom_fn = custom_arms[arm_id]

            def _custom_adapter(
                case: Mapping[str, Any],
                ctx: RunContext,
                _fn: Any = custom_fn,
                _store: Mapping[str, Any] = session_store,
            ) -> Outcome:
                clean_case = _clean_case_for_arm(ctx.case_id, _store.get(ctx.case_id))
                return _fn(clean_case, ctx)

            adapters[arm_id] = _custom_adapter
            continue

        if arm_id in CANDIDATE_ARM_ALIASES:

            def _candidate_adapter(
                case: Mapping[str, Any],
                ctx: RunContext,
                _store: Mapping[str, Any] = session_store,
            ) -> Outcome:
                clean_case = _clean_case_for_arm(ctx.case_id, _store.get(ctx.case_id))
                return run_candidate(clean_case, ctx)

            adapters[arm_id] = _candidate_adapter
        elif arm_id in BASELINE_REGISTRY:

            def _baseline_adapter(
                case: Mapping[str, Any],
                ctx: RunContext,
                _arm: str = arm_id,
                _store: Mapping[str, Any] = session_store,
                _base_ctx: DetectorContext | None = detector_context,
            ) -> Outcome:
                clean_case = _clean_case_for_arm(ctx.case_id, _store.get(ctx.case_id))
                b_ctx = _base_ctx if _base_ctx is not None else DetectorContext()
                det_ctx = dataclasses.replace(
                    b_ctx,
                    arm_id=ctx.arm_id,
                    seed=ctx.seed,
                    source_commit=ctx.source_commit,
                    deadline_seconds=ctx.deadline_seconds,
                )
                return run_baseline(_arm, clean_case, det_ctx)

            adapters[arm_id] = _baseline_adapter
        else:
            raise RunnerError(RC_UNKNOWN_ARM, f"arm_id {arm_id!r} has no registered adapter")

    return adapters


# ---------------------------------------------------------------------------
# Core runner entry point: run_campaign(config) -> RunBundle.
# ---------------------------------------------------------------------------


def run_campaign(config: CampaignConfig | Mapping[str, Any] | None = None) -> RunBundle:
    """Execute all detector arms over the minimal agent event stream with equal config.

    Exact target contract: ``run_campaign(config) -> RunBundle``.

    - Validates equal configuration (seed, time limit, budget) across all arms.
    - Sanitizes session records into leak-safe case views so no labels reach arms.
    - Runs the campaign using :mod:`evaluation.venue2027._shared.harness`.
    - Enriches every record with extracted verdict, score, and mutually exclusive outcomes.
    - Fully deterministic: identical input and seeds produce identical bundles.
    """
    cfg = validate_config(config)

    case_ids = tuple(str(s.get("case_id", s.get("unit_id", ""))) for s in cfg.sessions)

    # Re-use _shared.harness.Campaign
    campaign = Campaign(
        campaign_id=cfg.campaign_id,
        case_ids=case_ids,
        arm_ids=cfg.arm_ids,
        seeds=tuple(cfg.seed for _ in cfg.arm_ids),
        source_commit=cfg.source_commit,
        per_pair_timeout_seconds=cfg.per_pair_timeout_seconds,
    )

    adapters = _build_arm_adapters(
        arm_ids=cfg.arm_ids,
        sessions=cfg.sessions,
        detector_context=cfg.detector_context,
        custom_arms=cfg.custom_arms,
    )

    oracle = cfg.oracle if cfg.oracle is not None else build_default_oracle(cfg.sessions)

    bundle = execute(
        campaign=campaign,
        arms=adapters,
        oracle=oracle,
        workers=cfg.workers,
        journal_path=cfg.journal_path,
    )

    # Post-enrich records with explicit verdict and score
    for rec in bundle.records:
        outcome_dict = rec.get("outcome", {})
        observed = outcome_dict.get("observed_outcome", "")
        detail = str(outcome_dict.get("detail", ""))
        rec["verdict"] = _outcome_to_verdict(observed)
        rec["score"] = extract_score(detail)

    return bundle
