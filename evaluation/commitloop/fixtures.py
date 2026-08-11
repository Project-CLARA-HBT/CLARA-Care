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
        elif stage.startswith("commitloop-generation-predicate.v1"):
            content = {
                "predicate": {
                    "op": "event",
                    "equals": {
                        "resource_type": "Observation",
                        "system": source["candidate"]["target"]["system"],
                        "code": source["candidate"]["target"]["code"],
                        "status": "final",
                    },
                }
            }
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
