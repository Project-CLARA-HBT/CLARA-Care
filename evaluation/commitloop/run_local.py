"""Bounded, resumable local CommitLoop run using an injected provider client."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from csv import DictWriter
from dataclasses import replace
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any, Literal

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
)
from evaluation.commitloop.schema import ConstructedCase, TimelineEvent
from evaluation.commitloop.score import (
    score_adversarial_variants,
    score_generation,
    score_outputs,
)
from evaluation.commitloop.solver_packets import CONDITIONS, build_solver_packets
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
_PREDICTION_SCHEMA_RAW = (
    _MODULE_ROOT / "schemas" / "prediction.schema.json"
).read_text(encoding="utf-8")
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


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _write_jsonl(path: Path, values: Sequence[object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(_json(item) + "\n" for item in values), encoding="utf-8")


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
        if path.name == "checksums.sha256":
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(root)}")
    (root / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _expand_adversarial_cases(
    base_cases: list[ConstructedCase],
    base_events: dict[str, tuple[TimelineEvent, ...]],
    *,
    valid_cutoff: datetime,
    max_cases: int,
) -> tuple[
    list[ConstructedCase],
    dict[str, tuple[TimelineEvent, ...]],
    list[dict[str, Any]],
]:
    """Materialize bounded opaque variants from fulfillment evidence only."""

    selected_base_cases = list(base_cases[:max_cases])
    events_by_case = {
        case.case_id: base_events[case.case_id] for case in selected_base_cases
    }
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
                    edited_event
                    if item.evidence_id == fulfillment.evidence_id
                    else item
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
    selected_variants = sorted(pending_variants, key=lambda item: item[0])[
        : max(0, max_cases - len(selected_base_cases))
    ]
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


def run_local_e2e(
    *,
    bundles: list[tuple[dict[str, Any], str]],
    output_dir: Path,
    clients: dict[str, EvaluationClient],
    construction_clients: tuple[EvaluationClient, EvaluationClient] | None = None,
    valid_cutoff: datetime,
    known_cutoff: datetime,
    limits: RunLimits,
    execution_mode: Literal["phase_a_fake", "phase_b_router"] = "phase_a_fake",
    phase_a_freeze_sha: str | None = None,
    provider_probe_sha256: str | None = None,
    provider_approval_sha256: str | None = None,
    source_cohort: str = "injected_fhir_bundles",
    conditions: tuple[str, ...] = CONDITIONS,
    primary_model: str | None = None,
    primary_reference_condition: str = "glhs_hybrid_thss_strict",
    primary_comparator_condition: str = "full_authorized_history",
) -> dict[str, Any]:
    if not conditions or len(conditions) != len(set(conditions)):
        raise ValueError("benchmark_conditions_invalid")
    if not set(conditions).issubset(CONDITIONS):
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
        token, events = ingest_bundle(
            bundle, fhir_version=version, ingested_at=known_cutoff
        )
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
            case, events, valid_cutoff=valid_cutoff, known_cutoff=known_cutoff
        ).items():
            if condition not in packets_by_condition:
                continue
            validate_solver_packet(packet, known_cutoff=known_cutoff)
            packets_by_condition[condition].append(packet)
    generation_outputs = list(_read_json(output_dir / "model_generation.json", []))
    generation_errors = list(
        _read_json(output_dir / "generation_error_ledger.json", [])
    )
    generated_case_ids = {
        str(item["case_id"])
        for item in [*generation_outputs, *generation_errors]
        if isinstance(item, dict) and isinstance(item.get("case_id"), str)
    }
    generation_request_count = sum(
        len(item.get("stages", [])) for item in generation_outputs
    ) + sum(
        int(item.get("request_count", 0))
        for item in generation_errors
        if isinstance(item, dict)
    )
    generation_budget_exhausted = False
    if construction_clients is not None:
        generator, reviewer = construction_clients
        for case in base_cases:
            if case.case_id in generated_case_ids:
                continue
            if (
                limits.max_requests - generation_request_count
                < REQUESTS_PER_ACCEPTED_CASE
            ):
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
                            generator.attempt_count
                            + reviewer.attempt_count
                            - attempts_before
                        ),
                        "requested_models": [GENERATOR_MODEL, REVIEWER_MODEL],
                    }
                )
            generation_request_count += (
                generator.request_count + reviewer.request_count - before
            )
            _write_json(output_dir / "generation_error_ledger.json", generation_errors)
            _write_json(output_dir / "model_generation.json", generation_outputs)
    _write_json(output_dir / "model_generation.json", generation_outputs)
    _write_jsonl(output_dir / "model_generation.jsonl", generation_outputs)
    _write_json(output_dir / "generation_error_ledger.json", generation_errors)
    outputs = list(_read_json(output_dir / "solver_outputs.json", []))
    errors = list(_read_json(output_dir / "error_ledger.json", []))
    attempted_keys = {
        str(item["key"])
        for item in [*outputs, *errors]
        if isinstance(item, dict) and isinstance(item.get("key"), str)
    }
    # The durable output/error ledgers are authoritative if a process crashes
    # after persisting a response but before the next checkpoint write.
    completed.update(attempted_keys)
    request_budget = max(
        0, limits.max_requests - generation_request_count - len(attempted_keys)
    )
    budget_exhausted = generation_budget_exhausted
    for model, client in clients.items():
        if budget_exhausted:
            break
        for condition in conditions:
            for packet in packets_by_condition[condition]:
                key = f"{model}:{condition}:{packet['case_id']}"
                if key in attempted_keys:
                    continue
                if request_budget <= 0:
                    budget_exhausted = True
                    break
                request_budget -= 1
                attempts_before = client.attempt_count
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
                    prediction = _validate_solver_prediction(json.loads(result.content))
                    outputs.append(
                        {
                            "key": key,
                            "case_id": packet["case_id"],
                            "condition": condition,
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
                        }
                    )
                except (
                    ProviderError,
                    json.JSONDecodeError,
                    OSError,
                    TimeoutError,
                    TypeError,
                    ValueError,
                ) as exc:
                    errors.append(
                        {
                            "key": key,
                            "case_id": packet["case_id"],
                            "condition": condition,
                            "requested_model_id": model,
                            "reported_model_id": None,
                            "error": type(exc).__name__,
                            "attempts": client.attempt_count - attempts_before,
                            "usage": {},
                        }
                    )
                completed.add(key)
                attempted_keys.add(key)
                if len(completed) % limits.checkpoint_every == 0:
                    _write_json(checkpoint_path, {"completed": sorted(completed)})
                    _write_json(output_dir / "solver_outputs.json", outputs)
                    _write_json(output_dir / "error_ledger.json", errors)
            if budget_exhausted:
                break
        if budget_exhausted:
            break
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
    partitions = split_subjects(subject_tokens, seed="commitloop-v1")
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
                            prediction.get("lifecycle_state")
                            == expected.get("lifecycle_state")
                        ),
                        "evidence_correct": int(
                            prediction.get("evidence_state")
                            == expected.get("evidence_state")
                        ),
                        "timeliness_correct": int(
                            prediction.get("timeliness_state")
                            == expected.get("timeliness_state")
                        ),
                        "escalation_correct": int(
                            prediction.get("escalation_state")
                            == expected.get("escalation_state")
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
            "fhir_versions": sorted(
                {version for _, version in bundles[: limits.max_subjects]}
            ),
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
            "execution_mode": execution_mode,
            "solver_prompt_sha256": _SOLVER_PROMPT_SHA256,
            "prediction_schema_sha256": _PREDICTION_SCHEMA_SHA256,
            "endpoint_sha256": {
                model: clients[model].base_url_sha256 for model in sorted(clients)
            },
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
    }
    _write_json(
        output_dir / "protocol_manifest.json",
        {
            **protocol_payload,
            "protocol_sha256": hashlib.sha256(
                _json(protocol_payload).encode()
            ).hexdigest(),
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
        "phase_a_freeze_sha": phase_a_freeze_sha,
        "provider_probe_sha256": provider_probe_sha256,
        "provider_approval_sha256": provider_approval_sha256,
        "router_calls_before_freeze": 0,
        "clinical_adjudication": "NOT_RUN",
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
        report_title
        + f"Status: `{manifest['run_status']}`. Clinical adjudication: `NOT_RUN`. "
        f"{execution_note}\n",
        encoding="utf-8",
    )
    seal_artifacts(output_dir)
    return manifest
