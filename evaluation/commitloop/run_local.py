"""Bounded, resumable local CommitLoop run using an injected provider client."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import sys
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from csv import DictWriter
from dataclasses import replace
from datetime import UTC, datetime
from functools import wraps
from io import StringIO
from pathlib import Path
from typing import Any, Literal, Protocol

# Ensure proper python runtime and sys.path
_REPO_ROOT = Path(__file__).resolve().parents[2]
_API_SRC = _REPO_ROOT / "services" / "api" / "src"
_ML_SRC = _REPO_ROOT / "services" / "ml" / "src"
_VENV_PY = _REPO_ROOT / "services" / "api" / ".venv" / "bin" / "python"

if (sys.version_info < (3, 11) or sys.version_info >= (3, 12)) and _VENV_PY.is_file():
    _script_args = sys.argv[1:] if len(sys.argv) > 1 else []
    os.execv(str(_VENV_PY), [str(_VENV_PY), "-m", "evaluation.commitloop.run_local", *_script_args])

for _p in (str(_REPO_ROOT), str(_API_SRC), str(_ML_SRC)):
    if _p not in sys.path and Path(_p).exists():
        sys.path.insert(0, _p)

from evaluation.commitloop.candidate_mining import mine_candidates
from evaluation.commitloop.fhir_ingest import ingest_bundle
from evaluation.commitloop.generation import (
    REQUESTS_PER_ACCEPTED_CASE,
    construct_with_model_review,
)
from evaluation.commitloop.leakage import validate_solver_packet
from evaluation.commitloop.note_generation import render_anchor_note
from evaluation.commitloop.oracle import compile_construction_gold, grace_end_for_case
from evaluation.commitloop.perturbations import (
    generate_adversarial_perturbations,
    materialize_timeline_perturbation,
)
from evaluation.commitloop.provider import (
    GENERATOR_MODEL,
    REPORTED_MODEL_ID_BY_REQUESTED,
    REVIEWER_MODEL,
    EvaluationClient,
    ProviderError,
    RunLimits,
    parse_json_object_content,
)
from evaluation.commitloop.schema import ConstructedCase, TimelineEvent
from evaluation.commitloop.score import (
    score_adversarial_variants,
    score_generation,
    score_outputs,
)
from evaluation.commitloop.solver_packets import (
    CONDITIONS,
    EXPLORATORY_V7_CONDITIONS,
    build_solver_packets,
)
from evaluation.commitloop.splits import split_subjects
from evaluation.commitloop.statistics import (
    paired_condition_statistics,
    paired_primary_statistics,
    per_case_rows_with_subject,
)

_MODULE_ROOT = Path(__file__).parent
_SOLVER_SYSTEM = (
    (_MODULE_ROOT / "prompts" / "solver_system.txt").read_text(encoding="utf-8").strip()
)
_PREDICTION_SCHEMA_RAW = (_MODULE_ROOT / "schemas" / "prediction.schema.json").read_text(
    encoding="utf-8"
)
_SOLVER_RESPONSE_SCHEMA = {
    "name": "commitloop_prediction_v2",
    "schema": json.loads(_PREDICTION_SCHEMA_RAW),
    "strict": True,
}
_SOLVER_PROMPT_SHA256 = hashlib.sha256(_SOLVER_SYSTEM.encode()).hexdigest()
_PREDICTION_SCHEMA_SHA256 = hashlib.sha256(_PREDICTION_SCHEMA_RAW.encode()).hexdigest()
_PREDICTION_ENUMS = {
    key: frozenset(value["enum"])
    for key, value in _SOLVER_RESPONSE_SCHEMA["schema"]["properties"].items()
    if "enum" in value
}
SOLVER_BATCH_SIZE = 5
GLHS_BENCH_GLOBAL_CONCURRENCY = 5


class SolverFormatError(ValueError):
    """A response-shape failure with a sanitized, non-content diagnostic."""

    def __init__(self, detail: str, signature: dict[str, object]) -> None:
        super().__init__(detail)
        self.signature = signature


def _content_shape_signature(content: str) -> dict[str, object]:
    """Describe a failed response without retaining provider-generated text."""

    length = len(content)
    if length == 0:
        length_bucket = "empty"
    elif length <= 64:
        length_bucket = "1_64"
    elif length <= 256:
        length_bucket = "65_256"
    else:
        length_bucket = "257_plus"
    stripped = content.strip()
    return {
        "kind": "non_json_object",
        "length_bucket": length_bucket,
        "starts_object": stripped.startswith("{"),
        "ends_object": stripped.endswith("}"),
        "markdown_fence": stripped.startswith("```") and stripped.endswith("```"),
    }


def _prediction_shape_signature(value: object) -> dict[str, object]:
    """Describe schema conformance using only closed, non-sensitive fields."""

    expected_fields = {*_PREDICTION_ENUMS, "confidence"}
    if not isinstance(value, dict):
        return {"kind": "non_object", "python_type": type(value).__name__}
    missing = sorted(expected_fields - set(value))
    unexpected_count = len(set(value) - expected_fields)
    enum_status = {
        field: (
            "missing" if field not in value else "valid" if value[field] in allowed else "invalid"
        )
        for field, allowed in sorted(_PREDICTION_ENUMS.items())
    }
    confidence = value.get("confidence")
    confidence_status = (
        "missing"
        if "confidence" not in value
        else "valid"
        if isinstance(confidence, (int, float))
        and not isinstance(confidence, bool)
        and 0 <= confidence <= 1
        else "invalid"
    )
    return {
        "kind": "object",
        "missing_expected_fields": missing,
        "unexpected_field_count": unexpected_count,
        "enum_status": enum_status,
        "confidence_status": confidence_status,
    }


class StrictContextBuilder(Protocol):
    def __call__(
        self,
        case: ConstructedCase,
        events: tuple[TimelineEvent, ...],
        *,
        valid_cutoff: datetime,
        known_cutoff: datetime,
    ) -> dict[str, Any]: ...


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _validate_solver_prediction(value: object) -> dict[str, str | float]:
    expected_fields = {*_PREDICTION_ENUMS, "confidence"}
    if not isinstance(value, dict) or set(value) != expected_fields:
        raise ValueError("prediction_schema_invalid")
    if any(value[key] not in allowed for key, allowed in _PREDICTION_ENUMS.items()):
        raise ValueError("prediction_schema_invalid")
    confidence = value["confidence"]
    if (
        not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or not 0 <= confidence <= 1
    ):
        raise ValueError("prediction_schema_invalid")
    return {
        **{key: str(value[key]) for key in _PREDICTION_ENUMS},
        "confidence": float(confidence),
    }


def _read_json(path: Path, default: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _safe_error_detail(exc: Exception) -> str:
    """Return a closed taxonomy label without retaining provider content."""

    if isinstance(exc, ProviderError):
        return str(exc)
    if isinstance(exc, json.JSONDecodeError):
        return "provider_json_decode_error"
    if isinstance(exc, ValueError) and str(exc) == "prediction_schema_invalid":
        return "prediction_schema_invalid"
    if isinstance(exc, TimeoutError):
        return "provider_timeout"
    if isinstance(exc, OSError):
        return "provider_transport_error"
    return f"{type(exc).__name__}_terminal"


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, values: Sequence[object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(_json(item) + "\n" for item in values), encoding="utf-8")


def _append_jsonl_durable(path: Path, values: Sequence[object]) -> None:
    """Append one completed worker batch before its checkpoint is advanced."""

    if not values:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write("".join(_json(item) + "\n" for item in values))
        stream.flush()
        os.fsync(stream.fileno())


def _write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    stream = StringIO()
    writer = DictWriter(stream, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stream.getvalue(), encoding="utf-8")


def seal_artifacts(root: Path) -> None:
    lines = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.name in {"checksums.sha256", ".run.lock"}:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(root)}")
    (root / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _exclusive_output_directory(func):
    """Refuse concurrent resume processes for one mutable artifact directory."""

    @wraps(func)
    def wrapped(*args: Any, **kwargs: Any):
        output_dir = kwargs.get("output_dir")
        if not isinstance(output_dir, Path):
            raise TypeError("output_dir_keyword_path_required")
        output_dir.mkdir(parents=True, exist_ok=True)
        lock_path = output_dir / ".run.lock"
        with lock_path.open("a+", encoding="utf-8") as stream:
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError("benchmark_output_dir_in_use") from exc
            try:
                return func(*args, **kwargs)
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
                lock_path.unlink(missing_ok=True)

    return wrapped


def _expand_adversarial_cases(
    base_cases: list[ConstructedCase],
    base_events: dict[str, tuple[TimelineEvent, ...]],
    *,
    valid_cutoff: datetime,
    max_cases: int,
    include_all_adversarial_variants: bool = False,
) -> tuple[
    list[ConstructedCase],
    dict[str, tuple[TimelineEvent, ...]],
    list[dict[str, Any]],
]:
    """Materialize bounded opaque variants from fulfillment evidence only."""

    selected_base_cases = list(base_cases[:max_cases])
    events_by_case = {case.case_id: base_events[case.case_id] for case in selected_base_cases}
    pending_variants: list[
        tuple[str, ConstructedCase, tuple[TimelineEvent, ...], dict[str, Any]]
    ] = []
    for source_case in base_cases:
        if source_case.target is None:
            continue
        target_pair = (source_case.target["system"], source_case.target["code"])
        source_events = base_events[source_case.case_id]
        fulfillment_candidates = [
            event
            for event in source_events
            if event.evidence_id != source_case.anchor_evidence_id
            and target_pair in event.codes
            and event.valid_at is not None
            and event.status is not None
        ]
        # A one-field edit is only interpretable when exactly one fulfillment
        # event exists. Rich multi-event histories remain unmodified base cases.
        if len(fulfillment_candidates) != 1:
            continue
        fulfillment = fulfillment_candidates[0]
        manifests = generate_adversarial_perturbations(
            {
                "evidence_id": fulfillment.evidence_id,
                "status": fulfillment.status,
                "valid_at": fulfillment.valid_at,
                "known_at": fulfillment.known_at,
            },
            cutoff=valid_cutoff,
            seed=0,
        )
        for manifest in manifests:
            opaque_digest = hashlib.sha256(
                _json(
                    {
                        "source_case_id": source_case.case_id,
                        "before_sha256": manifest["before_sha256"],
                        "after_sha256": manifest["after_sha256"],
                        "seed": manifest["seed"],
                    }
                ).encode()
            ).hexdigest()
            variant_case = replace(source_case, case_id=f"case-{opaque_digest[:24]}")
            edited_event = materialize_timeline_perturbation(
                fulfillment,
                manifest=manifest,
            )
            if manifest["operation"] == "duplicate":
                variant_events = (*source_events, edited_event)
            else:
                variant_events = tuple(
                    edited_event if item.evidence_id == fulfillment.evidence_id else item
                    for item in source_events
                )
            pending_variants.append(
                (
                    opaque_digest,
                    variant_case,
                    variant_events,
                    {
                        "case_id": variant_case.case_id,
                        "source_case_id": source_case.case_id,
                        **manifest,
                    },
                )
            )
    selected_variants = sorted(pending_variants, key=lambda item: item[0])
    if not include_all_adversarial_variants:
        selected_variants = selected_variants[: max(0, max_cases - len(selected_base_cases))]
    for _, variant_case, variant_events, _ in selected_variants:
        events_by_case[variant_case.case_id] = variant_events
    cases = sorted(
        [*selected_base_cases, *(item[1] for item in selected_variants)],
        key=lambda case: hashlib.sha256(case.case_id.encode()).hexdigest(),
    )
    perturbations = sorted(
        (item[3] for item in selected_variants),
        key=lambda item: str(item["case_id"]),
    )
    return cases, events_by_case, perturbations


def expected_solver_case_count(
    *,
    bundles: list[tuple[dict[str, Any], str]],
    valid_cutoff: datetime,
    known_cutoff: datetime,
    max_subjects: int,
    max_base_cases: int,
) -> int:
    """Return the complete prespecified base-plus-adversarial case inventory.

    This uses the same deterministic construction as the runner so a frozen
    request budget cannot exclude adversarial variants by accident.
    """

    base_cases: list[ConstructedCase] = []
    base_events: dict[str, tuple[TimelineEvent, ...]] = {}
    for bundle, version in bundles[:max_subjects]:
        token, events = ingest_bundle(bundle, fhir_version=version, ingested_at=known_cutoff)
        for case in mine_candidates(token, events):
            if case.status != "ELIGIBLE" or len(base_cases) >= max_base_cases:
                continue
            base_cases.append(case)
            base_events[case.case_id] = events
    cases, _events, _perturbations = _expand_adversarial_cases(
        base_cases,
        base_events,
        valid_cutoff=valid_cutoff,
        max_cases=max_base_cases,
        include_all_adversarial_variants=True,
    )
    return len(cases)


@_exclusive_output_directory
def run_local_e2e(
    *,
    bundles: list[tuple[dict[str, Any], str]],
    output_dir: Path,
    clients: dict[str, EvaluationClient],
    construction_clients: tuple[EvaluationClient, EvaluationClient] | None = None,
    valid_cutoff: datetime,
    known_cutoff: datetime,
    limits: RunLimits,
    execution_mode: Literal["phase_a_fake", "phase_b_router", "glhs_bench_router"] = "phase_a_fake",
    phase_a_freeze_sha: str | None = None,
    provider_probe_sha256: str | None = None,
    provider_approval_sha256: str | None = None,
    source_cohort: str = "injected_fhir_bundles",
    conditions: tuple[str, ...] = CONDITIONS,
    primary_model: str | None = None,
    primary_reference_condition: str = "glhs_hybrid_thss_strict",
    primary_comparator_condition: str = "full_authorized_history",
    production_strict_context_builder: StrictContextBuilder | None = None,
    subject_splits: dict[str, str] | None = None,
    include_all_adversarial_variants: bool = False,
    model_order: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    if not conditions or len(conditions) != len(set(conditions)):
        raise ValueError("benchmark_conditions_invalid")
    # The default remains the legacy frozen V5/V6 inventory.  V7 must pass its
    # own explicit inventory from a newly sealed protocol; no old run can gain
    # a comparator by importing newer code.
    if not set(conditions).issubset(EXPLORATORY_V7_CONDITIONS):
        raise ValueError("benchmark_condition_undeclared")
    if primary_model is not None and (
        primary_model not in clients
        or primary_reference_condition not in conditions
        or primary_comparator_condition not in conditions
    ):
        raise ValueError("primary_analysis_grid_invalid")
    if execution_mode == "phase_b_router":
        if not isinstance(phase_a_freeze_sha, str) or len(phase_a_freeze_sha) not in {
            40,
            64,
        }:
            raise ValueError("phase_b_freeze_sha_required")
        provenance_hashes = [
            value
            for value in (provider_probe_sha256, provider_approval_sha256)
            if isinstance(value, str) and len(value) == 64
        ]
        if len(provenance_hashes) != 1:
            raise ValueError("phase_b_single_cost_gate_sha_required")
    if execution_mode == "glhs_bench_router":
        if limits.max_concurrency != GLHS_BENCH_GLOBAL_CONCURRENCY:
            raise ValueError("glhs_bench_requires_exact_global_concurrency_5")
        if limits.max_retries < 1:
            raise ValueError("glhs_bench_requires_retry_policy")
        if not isinstance(phase_a_freeze_sha, str) or len(phase_a_freeze_sha) not in {
            40,
            64,
        }:
            raise ValueError("glhs_bench_freeze_sha_required")
        if not isinstance(provider_probe_sha256, str) or len(provider_probe_sha256) != 64:
            raise ValueError("glhs_bench_provider_probe_required")
        if production_strict_context_builder is None:
            raise ValueError("glhs_bench_production_thss_context_required")
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / "checkpoint.json"
    completed = set(_read_json(checkpoint_path, {"completed": []})["completed"])
    base_cases: list[ConstructedCase] = []
    gold: list[dict[str, Any]] = []
    timeline: list[dict[str, Any]] = []
    commitments: list[dict[str, Any]] = []
    notes: list[dict[str, str]] = []
    base_case_events: dict[str, tuple[TimelineEvent, ...]] = {}
    packets_by_condition: dict[str, list[dict[str, Any]]] = {
        condition: [] for condition in conditions
    }
    subject_tokens = set()
    for bundle, version in bundles[: limits.max_subjects]:
        token, events = ingest_bundle(bundle, fhir_version=version, ingested_at=known_cutoff)
        subject_tokens.add(token)
        timeline.extend(
            {
                "subject_token": token,
                "evidence_id": item.evidence_id,
                "resource_type": item.resource_type,
                "status": item.status,
                "codes": [list(code) for code in item.codes],
                "valid_at": item.valid_at.isoformat() if item.valid_at else None,
                "known_at": item.known_at.isoformat(),
                "encounter_reference": item.encounter_reference,
            }
            for item in events
        )
        for case in mine_candidates(token, events):
            if case.status != "ELIGIBLE" or len(base_cases) >= limits.max_cases:
                continue
            base_cases.append(case)
            base_case_events[case.case_id] = events
    cases, case_events, perturbations = _expand_adversarial_cases(
        base_cases,
        base_case_events,
        valid_cutoff=valid_cutoff,
        max_cases=limits.max_cases,
        include_all_adversarial_variants=include_all_adversarial_variants,
    )
    for case in cases:
        events = case_events[case.case_id]
        commitments.append(
            {
                "case_id": case.case_id,
                "subject_token": case.subject_token,
                "domain": case.domain,
                "action": case.action,
                "target": case.target,
                "anchor_evidence_id": case.anchor_evidence_id,
                "anchor_valid_time": case.anchor_valid_time,
                "anchor_known_time": case.anchor_known_time,
                "due_time": case.due_time,
                "grace_end": grace_end_for_case(case),
                "fulfillment_predicate": case.fulfillment_predicate,
            }
        )
        note = render_anchor_note(case)
        if note is not None:
            notes.append(
                {
                    "case_id": case.case_id,
                    "subject_token": case.subject_token,
                    "note": note,
                }
            )
        gold.append(
            compile_construction_gold(
                case, events, valid_cutoff=valid_cutoff, known_cutoff=known_cutoff
            )
        )
        for condition, packet in build_solver_packets(
            case,
            events,
            valid_cutoff=valid_cutoff,
            known_cutoff=known_cutoff,
            production_strict_context=production_strict_context_builder,
            conditions=conditions,
        ).items():
            if condition not in packets_by_condition:
                continue
            validate_solver_packet(packet, known_cutoff=known_cutoff)
            packets_by_condition[condition].append(packet)
    if subject_splits is not None and (
        set(subject_splits) != subject_tokens
        or not set(subject_splits.values()).issubset({"development", "validation", "sealed_test"})
    ):
        raise ValueError("preassigned_subject_split_inventory_invalid")
    generation_outputs = list(_read_json(output_dir / "model_generation.json", []))
    generation_errors = list(_read_json(output_dir / "generation_error_ledger.json", []))
    generated_case_ids = {
        str(item["case_id"])
        for item in [*generation_outputs, *generation_errors]
        if isinstance(item, dict) and isinstance(item.get("case_id"), str)
    }
    generation_request_count = sum(
        len(item.get("stages", [])) for item in generation_outputs
    ) + sum(
        int(item.get("request_count", 0)) for item in generation_errors if isinstance(item, dict)
    )
    generation_budget_exhausted = False
    if construction_clients is not None:
        generator, reviewer = construction_clients
        for case in base_cases:
            if case.case_id in generated_case_ids:
                continue
            if limits.max_requests - generation_request_count < REQUESTS_PER_ACCEPTED_CASE:
                generation_budget_exhausted = True
                break
            before = generator.request_count + reviewer.request_count
            attempts_before = generator.attempt_count + reviewer.attempt_count
            try:
                generation_outputs.append(
                    construct_with_model_review(
                        case=case,
                        events=case_events[case.case_id],
                        generator=generator,
                        reviewer=reviewer,
                    )
                )
            except (
                ProviderError,
                json.JSONDecodeError,
                OSError,
                TimeoutError,
                TypeError,
                ValueError,
            ) as exc:
                consumed = generator.request_count + reviewer.request_count - before
                generation_errors.append(
                    {
                        "case_id": case.case_id,
                        "error": type(exc).__name__,
                        "request_count": consumed,
                        "attempt_count": (
                            generator.attempt_count + reviewer.attempt_count - attempts_before
                        ),
                        "requested_models": [GENERATOR_MODEL, REVIEWER_MODEL],
                    }
                )
            generation_request_count += generator.request_count + reviewer.request_count - before
            _write_json(output_dir / "generation_error_ledger.json", generation_errors)
            _write_json(output_dir / "model_generation.json", generation_outputs)
    _write_json(output_dir / "model_generation.json", generation_outputs)
    _write_jsonl(output_dir / "model_generation.jsonl", generation_outputs)
    _write_json(output_dir / "generation_error_ledger.json", generation_errors)
    # The append ledgers are the crash-safe source of truth between final
    # materializations.  Legacy JSON ledgers remain accepted for old and
    # interrupted runs, then keys deduplicate an overlap safely.
    output_ledger = [
        *_read_json(output_dir / "solver_outputs.json", []),
        *_read_jsonl(output_dir / "solver_outputs.append.jsonl"),
    ]
    error_ledger = [
        *_read_json(output_dir / "error_ledger.json", []),
        *_read_jsonl(output_dir / "error_ledger.append.jsonl"),
    ]
    outputs = list(
        {
            str(item["key"]): item
            for item in output_ledger
            if isinstance(item, dict) and "key" in item
        }.values()
    )
    errors = list(
        {
            str(item["key"]): item
            for item in error_ledger
            if isinstance(item, dict) and "key" in item
        }.values()
    )
    attempted_keys = {
        str(item["key"])
        for item in [*outputs, *errors]
        if isinstance(item, dict) and isinstance(item.get("key"), str)
    }
    # The durable output/error ledgers are authoritative if a process crashes
    # after persisting a response but before the next checkpoint write.
    completed.update(attempted_keys)
    request_budget = max(0, limits.max_requests - generation_request_count - len(attempted_keys))
    budget_exhausted = generation_budget_exhausted
    pending: list[tuple[str, str, dict[str, Any], EvaluationClient]] = []
    ordered_models = tuple(model_order) if model_order is not None else tuple(clients.keys())
    if not ordered_models or set(ordered_models) != set(clients):
        raise ValueError("benchmark_model_order_invalid")
    for model in ordered_models:
        client = clients[model]
        for condition in conditions:
            for packet in packets_by_condition[condition]:
                key = f"{model}:{condition}:{packet['case_id']}"
                if key in attempted_keys:
                    continue
                if request_budget <= 0:
                    budget_exhausted = True
                    break
                request_budget -= 1
                pending.append((key, model, packet, client))
            if budget_exhausted:
                break
        if budget_exhausted:
            break

    def solve_one(
        item: tuple[str, str, dict[str, Any], EvaluationClient],
    ) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None]:
        key, model, packet, client = item
        try:
            result = client.complete(
                model=model,
                messages=[
                    {"role": "system", "content": _SOLVER_SYSTEM},
                    {"role": "user", "content": _json(packet)},
                ],
                response_schema=_SOLVER_RESPONSE_SCHEMA,
                max_tokens=256,
            )
            try:
                parsed = parse_json_object_content(result.content)
            except json.JSONDecodeError as exc:
                raise SolverFormatError(
                    "provider_json_decode_error",
                    _content_shape_signature(result.content),
                ) from exc
            try:
                prediction = _validate_solver_prediction(parsed)
            except (TypeError, ValueError) as exc:
                raise SolverFormatError(
                    "prediction_schema_invalid",
                    _prediction_shape_signature(parsed),
                ) from exc
            return (
                key,
                {
                    "key": key,
                    "case_id": packet["case_id"],
                    "condition": packet["condition"],
                    "requested_model_id": result.requested_model_id,
                    "reported_model_id": result.reported_model_id,
                    "prediction": prediction,
                    "usage": result.usage,
                    "latency_ms": result.latency_ms,
                    "request_sha256": result.request_sha256,
                    "response_sha256": result.response_sha256,
                    "attempts": result.attempts,
                    "prompt_sha256": _SOLVER_PROMPT_SHA256,
                    "schema_sha256": _PREDICTION_SCHEMA_SHA256,
                },
                None,
            )
        except SolverFormatError as exc:
            return (
                key,
                None,
                {
                    "key": key,
                    "case_id": packet["case_id"],
                    "condition": packet["condition"],
                    "requested_model_id": result.requested_model_id,
                    "reported_model_id": result.reported_model_id,
                    "error": type(exc).__name__,
                    "error_detail": str(exc),
                    "response_format_signature": exc.signature,
                    "attempts": result.attempts,
                    "usage": result.usage,
                    "latency_ms": result.latency_ms,
                    "request_sha256": result.request_sha256,
                    "response_sha256": result.response_sha256,
                },
            )
        except (
            ProviderError,
            json.JSONDecodeError,
            OSError,
            TimeoutError,
            TypeError,
            ValueError,
        ) as exc:
            return (
                key,
                None,
                {
                    "key": key,
                    "case_id": packet["case_id"],
                    "condition": packet["condition"],
                    "requested_model_id": model,
                    "reported_model_id": None,
                    "error": type(exc).__name__,
                    "error_detail": _safe_error_detail(exc),
                    "attempts": max(1, int(getattr(exc, "attempts", 1))),
                    "usage": {},
                },
            )

    completed_since_checkpoint = 0
    # Submit bounded batches so durable ledgers/checkpoints are flushed after
    # each worker batch. This preserves resumability without changing the
    # frozen request order, model mapping, retry policy or cohort.
    batch_size = min(SOLVER_BATCH_SIZE, limits.max_concurrency)
    for offset in range(0, len(pending), batch_size):
        batch = pending[offset : offset + batch_size]
        with ThreadPoolExecutor(max_workers=batch_size) as executor:
            futures = [executor.submit(solve_one, item) for item in batch]
            results = [future.result() for future in as_completed(futures)]
        batch_outputs: list[dict[str, Any]] = []
        batch_errors: list[dict[str, Any]] = []
        for key, output, error in sorted(results, key=lambda item: item[0]):
            if output is not None:
                outputs.append(output)
                batch_outputs.append(output)
            if error is not None:
                errors.append(error)
                batch_errors.append(error)
            completed.add(key)
            attempted_keys.add(key)
            completed_since_checkpoint += 1
        _append_jsonl_durable(output_dir / "solver_outputs.append.jsonl", batch_outputs)
        _append_jsonl_durable(output_dir / "error_ledger.append.jsonl", batch_errors)
        _write_json(checkpoint_path, {"completed": sorted(completed)})
        completed_since_checkpoint = 0
    _write_json(checkpoint_path, {"completed": sorted(completed)})
    _write_json(output_dir / "solver_outputs.json", outputs)
    _write_json(output_dir / "error_ledger.json", errors)
    outputs_by_cell: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for output in outputs:
        cell = (str(output["requested_model_id"]), str(output["condition"]))
        outputs_by_cell.setdefault(cell, []).append(output)
    for (model, condition), cell_outputs in outputs_by_cell.items():
        safe_model = model.replace("/", "__")
        _write_jsonl(
            output_dir / "solver_outputs" / safe_model / f"{condition}.jsonl",
            cell_outputs,
        )
    _write_jsonl(output_dir / "construction_gold.jsonl", gold)
    _write_jsonl(output_dir / "timeline.jsonl", timeline)
    _write_jsonl(output_dir / "commitments.jsonl", commitments)
    _write_jsonl(output_dir / "synthetic_notes.jsonl", notes)
    _write_jsonl(output_dir / "perturbation_manifest.jsonl", perturbations)
    for condition, packets in packets_by_condition.items():
        _write_jsonl(output_dir / "solver_packets" / f"{condition}.jsonl", packets)
    partitions = (
        dict(subject_splits)
        if subject_splits is not None
        else split_subjects(subject_tokens, seed="commitloop-v1")
    )
    _write_json(output_dir / "partition_manifest.json", partitions)
    metrics = score_outputs(
        {item["case_id"]: item for item in gold},
        outputs,
        errors=errors,
        models=sorted(clients),
        conditions=list(conditions),
    )
    metrics["generation"] = (
        score_generation(
            generation_outputs,
            generation_errors,
            expected_cases=len(base_cases),
            expected_candidates={
                case.case_id: {
                    "anchor_evidence_id": case.anchor_evidence_id,
                    "action": case.action,
                    "target": case.target,
                    "due_time": case.due_time.isoformat() if case.due_time else None,
                }
                for case in base_cases
            },
        )
        if construction_clients is not None or primary_model is None
        else {
            "mode": "deterministic_construction_only",
            "expected_case_count": len(base_cases),
            "model_review_request_count": 0,
            "clinical_adjudication": "NOT_RUN",
        }
    )
    metrics["adversarial_variants"] = score_adversarial_variants(
        {item["case_id"]: item for item in gold},
        outputs,
        perturbations,
        models=sorted(clients),
        conditions=list(conditions),
    )
    metrics["context_volume_bytes"] = {
        condition: sum(len(_json(packet).encode()) for packet in packets)
        for condition, packets in packets_by_condition.items()
    }
    _write_json(output_dir / "metrics.json", metrics)
    gold_by_case = {item["case_id"]: item for item in gold}
    outputs_by_key = {
        (
            str(output["case_id"]),
            str(output["requested_model_id"]),
            str(output["condition"]),
        ): output
        for output in outputs
    }
    errors_by_key = {
        (
            str(error["case_id"]),
            str(error["requested_model_id"]),
            str(error["condition"]),
        ): error
        for error in errors
    }
    subject_by_case = {case.case_id: case.subject_token for case in cases}
    per_case_rows = []
    for case_id in sorted(subject_by_case):
        expected = gold_by_case.get(case_id, {})
        for model in sorted(clients):
            for condition in conditions:
                output = outputs_by_key.get((case_id, model, condition))
                error = errors_by_key.get((case_id, model, condition))
                prediction = (
                    output["prediction"]
                    if output is not None and isinstance(output.get("prediction"), dict)
                    else {}
                )
                per_case_rows.append(
                    {
                        "case_id": case_id,
                        "subject_token": subject_by_case[case_id],
                        "model": model,
                        "condition": condition,
                        "output_present": int(output is not None),
                        "failure": str(error.get("error", "")) if error else "",
                        "lifecycle_correct": int(
                            prediction.get("lifecycle_state") == expected.get("lifecycle_state")
                        ),
                        "evidence_correct": int(
                            prediction.get("evidence_state") == expected.get("evidence_state")
                        ),
                        "timeliness_correct": int(
                            prediction.get("timeliness_state") == expected.get("timeliness_state")
                        ),
                        "escalation_correct": int(
                            prediction.get("escalation_state") == expected.get("escalation_state")
                        ),
                        "all_axes_exact": int(
                            all(
                                prediction.get(axis) == expected.get(axis)
                                for axis in (
                                    "lifecycle_state",
                                    "evidence_state",
                                    "timeliness_state",
                                )
                            )
                        ),
                    }
                )
    _write_csv(
        output_dir / "per_case_metrics.csv",
        per_case_rows,
        [
            "case_id",
            "subject_token",
            "model",
            "condition",
            "output_present",
            "failure",
            "lifecycle_correct",
            "evidence_correct",
            "timeliness_correct",
            "escalation_correct",
            "all_axes_exact",
        ],
    )
    _write_csv(
        output_dir / "error_ledger.csv",
        errors,
        [
            "key",
            "case_id",
            "condition",
            "requested_model_id",
            "reported_model_id",
            "error",
            "error_detail",
            "response_format_signature",
            "attempts",
            "usage",
        ],
    )
    subject_rows = per_case_rows_with_subject(
        outputs=outputs,
        gold_by_case=gold_by_case,
        subject_by_case=subject_by_case,
        models=sorted(clients),
        conditions=list(conditions),
    )
    statistical_results = (
        paired_primary_statistics(
            subject_rows,
            primary_model=primary_model,
            reference_condition=primary_reference_condition,
            comparator_condition=primary_comparator_condition,
        )
        if primary_model is not None
        else paired_condition_statistics(subject_rows)
    )
    _write_json(
        output_dir / "statistical_results.json",
        {
            **statistical_results,
            "status": "DESCRIPTIVE_SYNTHETIC_ONLY",
            "clinical_adjudication": "NOT_RUN",
            "reason": (
                "router_backed_synthetic_not_clinical_evidence"
                if execution_mode == "phase_b_router"
                else "fake_transport_validation_not_clinical_evidence"
            ),
        },
    )
    _write_json(
        output_dir / "source_manifest.json",
        {
            "source": source_cohort,
            "fhir_versions": sorted({version for _, version in bundles[: limits.max_subjects]}),
            "subject_identity": "sha256_pseudonymized",
            "raw_patient_resources_persisted": False,
            "bundle_payload_sha256": sorted(
                hashlib.sha256(_json(bundle).encode()).hexdigest()
                for bundle, _ in bundles[: limits.max_subjects]
            ),
        },
    )
    _write_json(
        output_dir / "model_manifest.json",
        {
            "requested_models": sorted(clients),
            "reported_model_policy": "must_match_declared_mapping",
            "reported_model_mapping": REPORTED_MODEL_ID_BY_REQUESTED,
            "fallback": False,
            "temperature": 0,
            "response_format": "json_object_with_frozen_local_schema_validation",
            "execution_mode": execution_mode,
            "solver_prompt_sha256": _SOLVER_PROMPT_SHA256,
            "prediction_schema_sha256": _PREDICTION_SCHEMA_SHA256,
            "endpoint_sha256": {model: clients[model].base_url_sha256 for model in sorted(clients)},
        },
    )
    protocol_payload = {
        "schema_version": "commitloop-protocol.v2",
        "conditions": list(conditions),
        "split_seed": "commitloop-v1",
        "construction_gold": "deterministic_predicate_oracle",
        "timeliness_oracle": "decisive_event_else_cutoff_with_domain_default_grace",
        "solver_contract": "commitloop-solver.v5",
        "primary_analysis": (
            {
                "model": primary_model,
                "reference_condition": primary_reference_condition,
                "comparator_condition": primary_comparator_condition,
                "endpoint": "all_axes_exact_match",
                "unit": "subject",
            }
            if primary_model is not None
            else None
        ),
        "clinical_adjudication": "NOT_RUN",
        "max_concurrency": limits.max_concurrency,
        "batch_size": batch_size,
    }
    _write_json(
        output_dir / "protocol_manifest.json",
        {
            **protocol_payload,
            "protocol_sha256": hashlib.sha256(_json(protocol_payload).encode()).hexdigest(),
        },
    )
    manifest = {
        "schema_version": "commitloop-run.v1",
        "subject_count": len(subject_tokens),
        "case_count": len(cases),
        "source_case_count": len(base_cases),
        "variant_case_count": len(cases) - len(base_cases),
        "request_count": len(outputs) + len(errors) + generation_request_count,
        "solver_request_count": len(outputs) + len(errors),
        "generation_request_count": generation_request_count,
        "generation_case_count": len(generation_outputs) + len(generation_errors),
        "generation_error_count": len(generation_errors),
        "completed_cell_count": len(completed),
        "expected_cell_count": len(cases) * len(conditions) * len(clients),
        "run_status": "BOUNDED_INCOMPLETE" if budget_exhausted else "COMPLETE",
        "conditions": list(conditions),
        "models": sorted(clients),
        "primary_model": primary_model,
        "execution_mode": execution_mode,
        "source_cohort": source_cohort,
        "phase_a_freeze_sha": phase_a_freeze_sha,
        "provider_probe_sha256": provider_probe_sha256,
        "provider_approval_sha256": provider_approval_sha256,
        "router_calls_before_freeze": 0,
        "clinical_adjudication": "NOT_RUN",
        "max_concurrency": limits.max_concurrency,
        "batch_size": batch_size,
    }
    _write_json(output_dir / "run_manifest.json", manifest)
    _write_json(
        output_dir / "validation_report.json",
        {
            "schema_version": "commitloop-validation.v1",
            "status": "PASS_PENDING_SEAL_VERIFICATION",
            "subject_count": len(subject_tokens),
            "case_count": len(cases),
            "completed_cell_count": len(completed),
            "external_calls": (
                "ROUTER_PHASE_B"
                if execution_mode == "phase_b_router"
                else (
                    0
                    if all(client.request_count == 0 for client in clients.values())
                    else "INJECTED_TRANSPORT_ONLY"
                )
            ),
        },
    )
    report_title = (
        "# CommitLoop Phase-B synthetic benchmark\n\n"
        if execution_mode == "phase_b_router"
        else "# CommitLoop local validation\n\n"
    )
    execution_note = (
        "This run uses the post-freeze evaluation router on synthetic inputs."
        if execution_mode == "phase_b_router"
        else "This run uses injected transports and synthetic protocol-oracle labels."
    )
    (output_dir / "report.md").write_text(
        report_title + f"Status: `{manifest['run_status']}`. Clinical adjudication: `NOT_RUN`. "
        f"{execution_note}\n",
        encoding="utf-8",
    )
    seal_artifacts(output_dir)
    return manifest


def _format_summary_report(output_dir: Path, manifest: dict[str, Any]) -> str:
    """Format an honest, structured terminal evaluation report."""

    metrics_path = output_dir / "metrics.json"
    metrics = _read_json(metrics_path, {})
    outputs = _read_json(output_dir / "solver_outputs.json", [])
    errors = _read_json(output_dir / "error_ledger.json", [])
    stats = _read_json(output_dir / "statistical_results.json", {})

    lines: list[str] = []
    lines.append("=" * 80)
    lines.append(" COMMITLOOP EVALUATION REPORT")
    lines.append("=" * 80)
    lines.append(f"Status: {manifest.get('run_status', 'UNKNOWN')}")
    lines.append(f"Execution Mode: {manifest.get('execution_mode', 'UNKNOWN')}")
    lines.append(f"Output Directory: {output_dir}")
    lines.append(f"Cohort Subjects: {manifest.get('subject_count', 0)} (Base Cases: {manifest.get('source_case_count', 0)}, Variant Cases: {manifest.get('variant_case_count', 0)}, Total Cases: {manifest.get('case_count', 0)})")
    lines.append(f"Completed Cells: {manifest.get('completed_cell_count', 0)} / {manifest.get('expected_cell_count', 0)}")
    lines.append(f"Total Requests: {manifest.get('request_count', 0)} (Outputs: {len(outputs)}, Format/Transport Errors: {len(errors)})")
    lines.append("")

    # --- ALL-AXIS EXACT MATCH ACCURACY ---
    lines.append("-" * 80)
    lines.append(" ALL-AXIS EXACT MATCH ACCURACY ACROSS MODELS & CONDITIONS")
    lines.append("-" * 80)

    overall_exact = metrics.get("all_axes_exact_match", {})
    overall_acc = overall_exact.get("accuracy", 0.0)
    overall_cor = overall_exact.get("correct", 0)
    overall_den = overall_exact.get("denominator", 0)
    lines.append(f"Overall Exact Match Accuracy: {overall_acc * 100:.2f}% ({overall_cor}/{overall_den})")
    lines.append("")

    lines.append("Model-Level Summary:")
    by_model = metrics.get("by_model", {})
    for model_name, model_metrics in sorted(by_model.items()):
        m_exact = model_metrics.get("all_axes_exact", {})
        m_axes = model_metrics.get("axes", {})
        lc_acc = m_axes.get("lifecycle_state", {}).get("accuracy", 0.0)
        ev_acc = m_axes.get("evidence_state", {}).get("accuracy", 0.0)
        tm_acc = m_axes.get("timeliness_state", {}).get("accuracy", 0.0)
        esc_acc = m_axes.get("escalation_state", {}).get("accuracy", 0.0)
        lines.append(
            f"  * {model_name:24s}: Exact Match = {m_exact.get('accuracy', 0.0) * 100:6.2f}% "
            f"({m_exact.get('correct', 0)}/{m_exact.get('denominator', 0)}) | "
            f"Lifecycle: {lc_acc * 100:5.1f}% | Evidence: {ev_acc * 100:5.1f}% | "
            f"Timeliness: {tm_acc * 100:5.1f}% | Escalation: {esc_acc * 100:5.1f}%"
        )
    lines.append("")

    lines.append("Condition Breakdown (All-Axis Exact Match Accuracy):")
    lines.append(f"  {'Condition':<35s} | {'Gemini':<12s} | {'Claude':<12s} | {'Overall':<12s}")
    lines.append("  " + "-" * 75)

    # Compute per-cell exact match
    cell_accuracy: dict[tuple[str, str], tuple[int, int]] = {}
    cond_accuracy: dict[str, tuple[int, int]] = {}
    gold_by_case = {item["case_id"]: item for item in _read_jsonl(output_dir / "construction_gold.jsonl")}
    for output in outputs:
        model = str(output["requested_model_id"])
        cond = str(output["condition"])
        case_id = str(output["case_id"])
        pred = output.get("prediction", {})
        gold_case = gold_by_case.get(case_id, {})
        exact = int(
            all(
                pred.get(axis) == gold_case.get(axis)
                for axis in ("lifecycle_state", "evidence_state", "timeliness_state")
            )
        )
        c_cor, c_den = cell_accuracy.get((model, cond), (0, 0))
        cell_accuracy[(model, cond)] = (c_cor + exact, c_den + 1)
        o_cor, o_den = cond_accuracy.get(cond, (0, 0))
        cond_accuracy[cond] = (o_cor + exact, o_den + 1)

    conditions_list = list(manifest.get("conditions", CONDITIONS))
    for cond in conditions_list:
        gemini_cor, gemini_den = cell_accuracy.get(("gemini-3.6-flash-high", cond), (0, 0))
        claude_cor, claude_den = cell_accuracy.get(("claude-sonnet-4.6", cond), (0, 0))
        all_cor, all_den = cond_accuracy.get(cond, (0, 0))

        gem_str = f"{gemini_cor / gemini_den * 100:5.1f}% ({gemini_cor}/{gemini_den})" if gemini_den else "N/A"
        cla_str = f"{claude_cor / claude_den * 100:5.1f}% ({claude_cor}/{claude_den})" if claude_den else "N/A"
        all_str = f"{all_cor / all_den * 100:5.1f}% ({all_cor}/{all_den})" if all_den else "N/A"
        lines.append(f"  {cond:<35s} | {gem_str:<12s} | {cla_str:<12s} | {all_str:<12s}")
    lines.append("")

    # Adversarial Variants
    adv_variants = metrics.get("adversarial_variants", {}).get("by_variant", {})
    if adv_variants:
        lines.append("Adversarial Perturbation Robustness:")
        for v_name, v_metrics in sorted(adv_variants.items()):
            v_exact = v_metrics.get("all_axes_exact", {})
            lines.append(
                f"  * Variant '{v_name}': {v_exact.get('accuracy', 0.0) * 100:5.1f}% exact match "
                f"({v_exact.get('correct', 0)}/{v_exact.get('denominator', 0)})"
            )
        lines.append("")

    # --- TOKEN MINIMIZATION METRICS ---
    lines.append("-" * 80)
    lines.append(" TOKEN MINIMIZATION METRICS")
    lines.append("-" * 80)

    prompt_tokens_by_cond: dict[str, list[int]] = {}
    compl_tokens_by_cond: dict[str, list[int]] = {}
    total_tokens_by_cond: dict[str, list[int]] = {}
    latencies_by_cond: dict[str, list[float]] = {}
    latencies_by_model: dict[str, list[float]] = {}
    latencies_by_model_cond: dict[tuple[str, str], list[float]] = {}

    for output in outputs:
        cond = str(output["condition"])
        model = str(output["requested_model_id"])
        usage = output.get("usage", {})
        pt = usage.get("prompt_tokens")
        ct = usage.get("completion_tokens")
        tt = usage.get("total_tokens")
        lat = output.get("latency_ms")

        if isinstance(pt, (int, float)):
            prompt_tokens_by_cond.setdefault(cond, []).append(int(pt))
        if isinstance(ct, (int, float)):
            compl_tokens_by_cond.setdefault(cond, []).append(int(ct))
        if isinstance(tt, (int, float)):
            total_tokens_by_cond.setdefault(cond, []).append(int(tt))
        if isinstance(lat, (int, float)) and lat > 0:
            latencies_by_cond.setdefault(cond, []).append(float(lat))
            latencies_by_model.setdefault(model, []).append(float(lat))
            latencies_by_model_cond.setdefault((model, cond), []).append(float(lat))

    lines.append(f"  {'Condition':<35s} | {'Mean Prompt':<12s} | {'Mean Compl':<12s} | {'Mean Total':<12s} | {'Context Bytes':<12s}")
    lines.append("  " + "-" * 90)

    ctx_bytes = metrics.get("context_volume_bytes", {})
    full_prompt_mean = (
        sum(prompt_tokens_by_cond.get("full_authorized_history", [1]))
        / max(1, len(prompt_tokens_by_cond.get("full_authorized_history", [1])))
    )

    for cond in conditions_list:
        pts = prompt_tokens_by_cond.get(cond, [])
        cts = compl_tokens_by_cond.get(cond, [])
        tts = total_tokens_by_cond.get(cond, [])
        mean_pt = f"{sum(pts) / len(pts):.1f}" if pts else "N/A"
        mean_ct = f"{sum(cts) / len(cts):.1f}" if cts else "N/A"
        mean_tt = f"{sum(tts) / len(tts):.1f}" if tts else "N/A"
        bytes_str = f"{ctx_bytes.get(cond, 0):,d} B"
        lines.append(f"  {cond:<35s} | {mean_pt:<12s} | {mean_ct:<12s} | {mean_tt:<12s} | {bytes_str:<12s}")
    lines.append("")

    strict_pts = prompt_tokens_by_cond.get("glhs_hybrid_thss_strict", [])
    if strict_pts and full_prompt_mean > 0:
        strict_prompt_mean = sum(strict_pts) / len(strict_pts)
        prompt_reduction = (full_prompt_mean - strict_prompt_mean) / full_prompt_mean * 100
        full_bytes = ctx_bytes.get("full_authorized_history", 1)
        strict_bytes = ctx_bytes.get("glhs_hybrid_thss_strict", 0)
        bytes_reduction = (full_bytes - strict_bytes) / max(1, full_bytes) * 100
        lines.append(f"  Strict THSS Prompt Token Reduction vs Full History: {prompt_reduction:.1f}% savings "
                     f"({strict_prompt_mean:.1f} vs {full_prompt_mean:.1f} tokens)")
        lines.append(f"  Strict THSS Context Byte Reduction vs Full History: {bytes_reduction:.1f}% savings "
                     f"({strict_bytes:,d} vs {full_bytes:,d} bytes)")
    lines.append("")

    # --- LATENCY METRICS ---
    lines.append("-" * 80)
    lines.append(" LATENCY METRICS (MILLISECONDS)")
    lines.append("-" * 80)

    lines.append("Latency by Model:")
    for model_name, lats in sorted(latencies_by_model.items()):
        if not lats:
            continue
        sorted_lats = sorted(lats)
        mean_lat = sum(lats) / len(lats)
        p50_lat = sorted_lats[int(len(sorted_lats) * 0.50)]
        p95_lat = sorted_lats[int(len(sorted_lats) * 0.95)]
        lines.append(f"  * {model_name:24s}: Mean = {mean_lat:6.1f} ms | p50 = {p50_lat:6.1f} ms | p95 = {p95_lat:6.1f} ms")
    lines.append("")

    lines.append("Latency by Condition:")
    lines.append(f"  {'Condition':<35s} | {'Mean Latency':<14s} | {'p50 (Median)':<14s} | {'p95 Latency':<14s}")
    lines.append("  " + "-" * 80)

    full_lat_mean = 0.0
    strict_lat_mean = 0.0

    for cond in conditions_list:
        lats = latencies_by_cond.get(cond, [])
        if not lats:
            lines.append(f"  {cond:<35s} | {'N/A':<14s} | {'N/A':<14s} | {'N/A':<14s}")
            continue
        sorted_lats = sorted(lats)
        mean_lat = sum(lats) / len(lats)
        p50_lat = sorted_lats[int(len(sorted_lats) * 0.50)]
        p95_lat = sorted_lats[int(len(sorted_lats) * 0.95)]
        if cond == "full_authorized_history":
            full_lat_mean = mean_lat
        elif cond == "glhs_hybrid_thss_strict":
            strict_lat_mean = mean_lat
        lines.append(f"  {cond:<35s} | {mean_lat:8.1f} ms    | {p50_lat:8.1f} ms    | {p95_lat:8.1f} ms")
    lines.append("")

    if full_lat_mean > 0 and strict_lat_mean > 0:
        lat_reduction = (full_lat_mean - strict_lat_mean) / full_lat_mean * 100
        lines.append(f"  Strict THSS Latency Reduction vs Full History: {lat_reduction:.1f}% "
                     f"({strict_lat_mean:.1f} ms vs {full_lat_mean:.1f} ms)")
    lines.append("")

    # --- PAIRED STATISTICAL COMPARISON ---
    if "primary_model" in stats or "wins" in stats or "ties" in stats:
        lines.append("-" * 80)
        lines.append(" PAIRED COMPARISON: Strict THSS vs. Full Authorized History")
        lines.append("-" * 80)
        wins = stats.get("wins", "N/A")
        losses = stats.get("losses", "N/A")
        ties = stats.get("ties", "N/A")
        sign_p = stats.get("sign_test_p_value")
        p_str = f"{sign_p:.4f}" if isinstance(sign_p, (int, float)) else str(sign_p)
        lines.append(f"  Subject-level Decision Deltas: Wins = {wins}, Losses = {losses}, Ties = {ties}")
        lines.append(f"  Exact Sign Test p-value: {p_str}")
        lines.append("")

    lines.append("=" * 80)
    lines.append(" Artifacts sealed and verified with SHA-256 in " + str(output_dir))
    lines.append("=" * 80)
    return "\n".join(lines)


def main() -> int:
    """CLI entrypoint for running CommitLoop evaluations."""

    import argparse
    from evaluation.commitloop.fixtures import (
        DeterministicFakeTransport,
        controlled_benchmark_bundles,
    )
    from evaluation.commitloop.http_transport import UrllibJsonTransport
    from evaluation.commitloop.validate import validate_run

    parser = argparse.ArgumentParser(
        description="Run CommitLoop evaluation with live providers or offline fixtures"
    )
    parser.add_argument(
        "--output", type=Path, default=None, help="Output directory for evaluation artifacts"
    )
    parser.add_argument("--base-url", default=None, help="Provider router base URL")
    parser.add_argument("--api-key", default=None, help="Provider router API key")
    parser.add_argument("--max-subjects", type=int, default=None, help="Max subject count")
    parser.add_argument("--max-cases", type=int, default=None, help="Max case count")
    parser.add_argument("--max-requests", type=int, default=None, help="Max request budget")
    parser.add_argument("--max-concurrency", type=int, default=None, help="Max worker concurrency")
    parser.add_argument("--fake", action="store_true", help="Force deterministic fake transport")
    args = parser.parse_args()

    base_url = (
        args.base_url
        or os.environ.get("ROUTER_BASE_URL")
        or os.environ.get("DEEPSEEK_BASE_URL")
        or "https://router.theclaracare.com/v1"
    )
    api_key = (
        args.api_key
        or os.environ.get("ROUTER_API_KEY")
        or os.environ.get("CLARA_ROUTER_API_KEY")
        or os.environ.get("DEEPSEEK_API_KEY")
        or ""
    )
    output_dir = args.output or Path(
        os.environ.get("COMMITLOOP_RUN_DIR", "artifacts/commitloop/live_evaluation")
    )

    live_mode = bool(api_key and base_url.startswith("https://") and not args.fake)
    transport = UrllibJsonTransport() if live_mode else DeterministicFakeTransport()

    max_subjects = args.max_subjects or int(os.environ.get("COMMITLOOP_MAX_SUBJECTS", "8"))
    max_cases = args.max_cases or int(os.environ.get("COMMITLOOP_MAX_CASES", "50"))
    max_requests = args.max_requests or int(os.environ.get("COMMITLOOP_MAX_REQUESTS", "1000"))
    max_concurrency = args.max_concurrency or int(
        os.environ.get("COMMITLOOP_MAX_CONCURRENCY", "5" if live_mode else "2")
    )

    limits = RunLimits(
        max_subjects=min(max_subjects, 1000),
        max_cases=min(max_cases, 5000),
        max_requests=min(max_requests, 20000),
        max_concurrency=min(max_concurrency, 16),
        timeout_seconds=float(os.environ.get("COMMITLOOP_TIMEOUT_SECONDS", "60.0")),
        checkpoint_every=int(os.environ.get("COMMITLOOP_CHECKPOINT_EVERY", "5")),
        max_retries=int(os.environ.get("COMMITLOOP_MAX_RETRIES", "3" if live_mode else "0")),
        retry_backoff_seconds=float(
            os.environ.get("COMMITLOOP_RETRY_BACKOFF_SECONDS", "1.0" if live_mode else "0.0")
        ),
    )

    clients = {
        model: EvaluationClient(
            base_url=base_url if live_mode else "https://offline.invalid/v1",
            api_key=api_key if live_mode else "offline-fixture-token",
            transport=transport,
            limits=limits,
        )
        for model in (GENERATOR_MODEL, REVIEWER_MODEL)
    }

    cutoff = datetime(2026, 2, 1, tzinfo=UTC)
    bundles = [(bundle, "R4") for bundle in controlled_benchmark_bundles()[: limits.max_subjects]]

    print(
        f"[CommitLoop] Initializing evaluation in {'LIVE ROUTER' if live_mode else 'OFFLINE_FAKE'} mode..."
    )
    print(f"[CommitLoop] Target Models: {sorted(clients.keys())}")
    print(f"[CommitLoop] Output Directory: {output_dir}")
    print(
        f"[CommitLoop] Subjects: {len(bundles)}, Max Requests: {limits.max_requests}, Concurrency: {limits.max_concurrency}"
    )

    manifest = run_local_e2e(
        bundles=bundles,
        output_dir=output_dir,
        clients=clients,
        valid_cutoff=cutoff,
        known_cutoff=cutoff,
        limits=limits,
        conditions=CONDITIONS,
        include_all_adversarial_variants=True,
        model_order=(GENERATOR_MODEL, REVIEWER_MODEL),
    )

    validate_run(output_dir)

    report_text = _format_summary_report(output_dir, manifest)
    print("\n" + report_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

