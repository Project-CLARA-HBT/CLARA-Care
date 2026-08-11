"""Secret-free deterministic FHIR fixtures for Phase-A local validation."""

from __future__ import annotations

import json
from typing import Any

from evaluation.commitloop.provider import expected_reported_model_id


def synthetic_bundle(patient_id: str, suffix: str) -> dict[str, Any]:
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": patient_id}},
            {
                "resource": {
                    "resourceType": "ServiceRequest",
                    "id": f"request-{suffix}",
                    "status": "active",
                    "subject": {"reference": f"Patient/{patient_id}"},
                    "authoredOn": "2026-01-01T00:00:00Z",
                    "occurrencePeriod": {"end": "2026-01-20T00:00:00Z"},
                    "code": {
                        "coding": [
                            {"system": "http://loinc.org", "code": f"test-{suffix}"}
                        ]
                    },
                }
            },
            {
                "resource": {
                    "resourceType": "Observation",
                    "id": f"observation-{suffix}",
                    "status": "final",
                    "subject": {"reference": f"Patient/{patient_id}"},
                    "effectiveDateTime": "2026-01-10T00:00:00Z",
                    "meta": {"lastUpdated": "2026-01-11T00:00:00Z"},
                    "code": {
                        "coding": [
                            {"system": "http://loinc.org", "code": f"test-{suffix}"}
                        ]
                    },
                }
            },
        ],
    }


def _controlled_bundle(
    *,
    suffix: str,
    due_time: str | None,
    observations: list[dict[str, str]],
) -> dict[str, Any]:
    """Build one declared, PII-free R4 software-evaluation fixture."""

    patient_id = f"controlled-{suffix}"
    request: dict[str, Any] = {
        "resourceType": "ServiceRequest",
        "id": f"request-{suffix}",
        "status": "active",
        "subject": {"reference": f"Patient/{patient_id}"},
        "authoredOn": "2026-01-01T00:00:00Z",
        "code": {
            "coding": [{"system": "http://loinc.org", "code": f"test-{suffix}"}]
        },
    }
    if due_time is not None:
        request["occurrencePeriod"] = {"end": due_time}
    entries: list[dict[str, Any]] = [
        {"resource": {"resourceType": "Patient", "id": patient_id}},
        {"resource": request},
    ]
    for index, spec in enumerate(observations, start=1):
        observation: dict[str, Any] = {
            "resourceType": "Observation",
            "id": f"observation-{suffix}-{index}",
            "status": spec["status"],
            "subject": {"reference": f"Patient/{patient_id}"},
            "effectiveDateTime": spec["valid_at"],
            "meta": {"lastUpdated": spec.get("known_at", spec["valid_at"])},
            "code": {
                "coding": [
                    {"system": "http://loinc.org", "code": f"test-{suffix}"}
                ]
            },
        }
        if "relation" in spec:
            observation["relation"] = spec["relation"]
        entries.append({"resource": observation})
    return {"resourceType": "Bundle", "type": "collection", "entry": entries}


def controlled_benchmark_bundles() -> tuple[dict[str, Any], ...]:
    """Frozen mechanism-coverage cohort; synthetic software evidence only.

    The cases cover completion before due, partial completion in grace,
    contradiction, late knowledge, unresolved overdue, no due date, historical
    status competition, and retrieval-depth pressure.  These are declared
    mechanism tests, not clinical records or Synthea-derived evidence.
    """

    before = {"status": "final", "valid_at": "2026-01-10T00:00:00Z"}
    return (
        _controlled_bundle(
            suffix="before",
            due_time="2026-01-20T00:00:00Z",
            observations=[before],
        ),
        _controlled_bundle(
            suffix="grace",
            due_time="2026-01-05T00:00:00Z",
            observations=[
                {"status": "preliminary", "valid_at": "2026-01-10T00:00:00Z"}
            ],
        ),
        _controlled_bundle(
            suffix="conflict",
            due_time="2026-01-20T00:00:00Z",
            observations=[{**before, "relation": "contradicts"}],
        ),
        _controlled_bundle(
            suffix="late",
            due_time="2026-01-20T00:00:00Z",
            observations=[
                {
                    **before,
                    "known_at": "2026-02-02T00:00:00Z",
                }
            ],
        ),
        _controlled_bundle(
            suffix="overdue",
            due_time="2026-01-10T00:00:00Z",
            observations=[],
        ),
        _controlled_bundle(suffix="undated", due_time=None, observations=[]),
        _controlled_bundle(
            suffix="history",
            due_time="2026-01-20T00:00:00Z",
            observations=[
                {"status": "revoked", "valid_at": "2026-01-05T00:00:00Z"},
                {"status": "final", "valid_at": "2026-01-10T00:00:00Z"},
            ],
        ),
        _controlled_bundle(
            suffix="depth",
            due_time="2026-01-20T00:00:00Z",
            observations=[
                {
                    "status": "preliminary",
                    "valid_at": f"2026-01-0{day}T00:00:00Z",
                }
                for day in range(2, 7)
            ]
            + [{"status": "replaced", "valid_at": "2026-01-08T00:00:00Z"}],
        ),
    )


class DeterministicFakeTransport:
    """Injected transport that performs no I/O and reports the exact requested model."""

    def __init__(self) -> None:
        self.call_count = 0

    def __call__(
        self, path: str, headers: dict[str, str], payload: dict[str, Any], timeout: float
    ) -> dict[str, Any]:
        del path, headers, timeout
        self.call_count += 1
        messages = payload["messages"]
        stage = messages[0]["content"] if len(messages) > 1 else "solver"
        source = json.loads(messages[-1]["content"])
        if stage.startswith("commitloop-generation-candidate.v1"):
            content = source["anchor"]
        elif stage.startswith("commitloop-generation-predicate.v2"):
            content = {"predicate": source["allowed_predicate_projection"]}
        elif stage.startswith("commitloop-generation-anchor-note.v1"):
            content = {"note": source["allowed_note_projection"]}
        elif stage.startswith("commitloop-review-"):
            content = {
                "faithful": True,
                "executable": True,
                "future_leakage": False,
                "issues": [],
            }
        else:
            content = {
                "lifecycle_state": "SATISFIED",
                "evidence_state": "CLEAR",
                "timeliness_state": "OVERDUE",
                "escalation_state": "NO_ESCALATION",
            }
        return {
            "model": expected_reported_model_id(payload["model"]),
            "choices": [
                {
                    "message": {
                        "content": json.dumps(content, sort_keys=True)
                    }
                }
            ],
            "usage": {"prompt_tokens": 8, "completion_tokens": 4, "total_tokens": 12},
        }
