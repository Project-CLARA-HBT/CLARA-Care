from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from evaluation.comparator_studies.official_graphrag.contract import (
    SCHEMA_VERSION,
    GraphRAGContractError,
    GraphRAGExecutionContract,
    build_settings,
    materialize_visible_evidence,
    validate_execution_manifest,
)


def _sha(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def test_materializes_only_visible_evidence_deterministically(tmp_path: Path) -> None:
    output = tmp_path / "input" / "events.jsonl"
    metadata = materialize_visible_evidence(
        [
            {
                "evidence_id": "z",
                "resource_type": "Observation",
                "status": "final",
                "codes": [["loinc", "123"]],
                "valid_at": "2025-01-02T00:00:00+00:00",
                "known_at": "2025-01-03T00:00:00+00:00",
                "encounter_reference": None,
                "relation": None,
            },
            {
                "evidence_id": "a",
                "resource_type": "ServiceRequest",
                "status": "active",
                "codes": [["snomed", "456"]],
                "valid_at": "2025-01-01T00:00:00+00:00",
                "known_at": "2025-01-01T00:00:00+00:00",
                "encounter_reference": None,
                "relation": "supports",
            },
        ],
        output_path=output,
    )

    rows = [json.loads(line) for line in output.read_text().splitlines()]
    assert [row["id"] for row in rows] == ["a", "z"]
    assert metadata["document_count"] == 2
    assert "target" not in output.read_text()
    assert "predicate" not in output.read_text()


def test_settings_enforce_global_router_concurrency() -> None:
    settings = build_settings(
        completion_model="claude-sonnet-4.6", embedding_model="embedding-model"
    )
    assert settings["concurrent_requests"] == 5


def test_rejects_label_or_future_like_packet_fields(tmp_path: Path) -> None:
    with pytest.raises(GraphRAGContractError, match="unapproved_fields"):
        materialize_visible_evidence(
            [
                {
                    "evidence_id": "x",
                    "resource_type": "Observation",
                    "status": "final",
                    "codes": [],
                    "valid_at": None,
                    "known_at": "2025-01-01T00:00:00+00:00",
                    "encounter_reference": None,
                    "relation": None,
                    "gold_label": "FULFILLED",
                }
            ],
            output_path=tmp_path / "events.jsonl",
        )


def test_manifest_fails_closed_before_upstream_verification(tmp_path: Path) -> None:
    input_path = tmp_path / "input.jsonl"
    materialize_visible_evidence([], output_path=input_path)
    settings = build_settings(
        completion_model="claude-sonnet-4.6", embedding_model="embedding-model"
    )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "contract_sha256": GraphRAGExecutionContract().sha256(),
        "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "settings_sha256": _sha(settings),
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(GraphRAGContractError, match="source_layout_invalid"):
        validate_execution_manifest(
            manifest_path,
            input_path=input_path,
            settings=settings,
            upstream_checkout=tmp_path / "not-a-graphrag-checkout",
        )
